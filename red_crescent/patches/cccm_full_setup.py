import re
import frappe
from frappe import _

# -----------------------------
# Helpers (name validation etc.)
# -----------------------------
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]*$")

def _sanitize_doctype_name(raw: str) -> str:
    if not raw:
        return "D_Untitled"
    name = " ".join(raw.strip().split())               # collapse spaces
    name = re.sub(r"[^A-Za-z0-9 _-]", "_", name)       # replace bad chars
    if not name[0].isalpha():
        name = f"D_{name}"
    return name

def upsert_doctype(props: dict, *, auto_sanitize_name: bool = True):
    """Create or update a (custom=1) DocType safely (idempotent)."""
    if "name" not in props or not props["name"]:
        raise ValueError("DocType 'name' is required in props.")
    name = props["name"]
    if not _NAME_RE.match(name or ""):
        if auto_sanitize_name:
            fixed = _sanitize_doctype_name(name)
            print(f"⚠️  Sanitized DocType name: '{name}' → '{fixed}'")
            name = fixed
            props = {**props, "name": name}
        else:
            raise ValueError(
                f"Invalid DocType name '{name}'. Must match ^[A-Za-z][A-Za-z0-9 _-]*$"
            )

    exists = frappe.db.exists("DocType", name)
    if exists:
        dt = frappe.get_doc("DocType", name)
        for k in ("module", "custom", "istable", "autoname", "title_field", "track_changes", "search_fields"):
            if k in props and props[k] is not None:
                setattr(dt, k, props[k])

        # Upsert fields by fieldname
        wanted = {f["fieldname"]: f for f in props.get("fields", []) if f.get("fieldname")}
        current = {f.fieldname: f for f in dt.fields}
        for fn, fdef in wanted.items():
            if fn in current:
                row = current[fn]
                for k, v in fdef.items():
                    setattr(row, k, v)
            else:
                dt.append("fields", fdef)

        # Ensure permissions (additive)
        if props.get("permissions"):
            have = {(p.role, p.read, p.write, p.create, p.delete) for p in dt.permissions}
            for p in props["permissions"]:
                key = (p.get("role"), p.get("read",0), p.get("write",0), p.get("create",0), p.get("delete",0))
                if key not in have:
                    dt.append("permissions", p)

        dt.save()
        print(f"ℹ️ Updated: {name}")
        return dt

    payload = {
        "doctype": "DocType",
        **props,
        "custom": 1 if "custom" not in props else props["custom"],
    }
    dt = frappe.get_doc(payload).insert()
    print(f"✅ Created: {name}")
    return dt

def ensure_server_script(name, doctype, event, code):
    exists = frappe.db.exists("Server Script", name)
    if exists:
        ss = frappe.get_doc("Server Script", name)
        ss.script = code
        ss.doctype_event = event
        ss.reference_doctype = doctype
        ss.enabled = 1
        ss.save()
        print(f"ℹ️ Updated Server Script: {name}")
    else:
        frappe.get_doc({
            "doctype": "Server Script",
            "name": name,
            "script_type": "DocType Event",
            "reference_doctype": doctype,
            "doctype_event": event,
            "script": code,
            "enabled": 1
        }).insert()
        print(f"✅ Created Server Script: {name}")

# ---------------
# Patch entrypoint
# ---------------
def run():
    frappe.only_for("System Manager")

    # -----------------------------
    # Resolve module
    # -----------------------------
    MODULE = "Yemen Red Crescent Society"
    if not frappe.db.exists("Module Def", MODULE):
        mods = frappe.get_all("Module Def", filters={"app_name": "red_crescent"}, pluck="name")
        if mods:
            MODULE = mods[0]
            print(f"ℹ️ Using module: {MODULE}")
        else:
            raise Exception("No Module found for app 'red_crescent'. Create a Module or fix the name.")

    # -----------------------------
    # Child: CCCM Service Line
    # -----------------------------
    service_fields = [
        {"fieldname":"sector","label":"Sector","fieldtype":"Select","options":"Shelter\nWASH\nHealth\nNutrition\nProtection\nEducation\nCamp Management\nFood Security\nLogistics\nOther","in_list_view":1},
        {"fieldname":"service_type","label":"Service Type","fieldtype":"Data","in_list_view":1},
        {"fieldname":"availability","label":"Availability","fieldtype":"Select","options":"Available\nPartial\nNot Available"},
        {"fieldname":"frequency","label":"Frequency","fieldtype":"Data"},
        {"fieldname":"provider","label":"Provider","fieldtype":"Data"},
        {"fieldname":"notes","label":"Notes","fieldtype":"Small Text"},
    ]
    if frappe.db.exists("DocType", "Partners"):
        service_fields[4] = {"fieldname":"provider","label":"Provider","fieldtype":"Link","options":"Partners","in_list_view":1}
    upsert_doctype({
        "name":"CCCM Service Line","module":MODULE,"istable":1,
        "fields": service_fields,
        "permissions":[{"role":"System Manager","read":1,"write":1,"create":1,"delete":1}]
    })

    # -----------------------------
    # Child: CCCM Population Snapshot
    # -----------------------------
    pop_fields = [
        {"fieldname":"snapshot_date","label":"Snapshot Date","fieldtype":"Date","reqd":1,"in_list_view":1},
        {"fieldname":"households","label":"Households","fieldtype":"Int","in_list_view":1},
        {"fieldname":"individuals","label":"Individuals","fieldtype":"Int","in_list_view":1},
        {"fieldname":"female_percent","label":"Female %","fieldtype":"Percent"},
        {"fieldname":"children_percent","label":"Children %","fieldtype":"Percent"},
        {"fieldname":"pwd_percent","label":"PwD %","fieldtype":"Percent"},
        {"fieldname":"notes","label":"Notes","fieldtype":"Small Text"},
    ]
    upsert_doctype({
        "name":"CCCM Population Snapshot","module":MODULE,"istable":1,
        "fields": pop_fields,
        "permissions":[{"role":"System Manager","read":1,"write":1,"create":1,"delete":1}]
    })

    # -----------------------------
    # Child: CCCM Facility Line
    # -----------------------------
    facility_fields = [
        {"fieldname":"facility_type","label":"Facility Type","fieldtype":"Select","options":"Water Point\nLatrine\nBath/Shower\nShelter\nHealth Post\nSchool Tent\nDistribution Point\nSecurity Post\nOther","reqd":1,"in_list_view":1},
        {"fieldname":"count_total","label":"Count (Total)","fieldtype":"Int","in_list_view":1},
        {"fieldname":"count_functional","label":"Count (Functional)","fieldtype":"Int"},
        {"fieldname":"condition","label":"Condition","fieldtype":"Select","options":"Good\nFair\nPoor"},
        {"fieldname":"notes","label":"Notes","fieldtype":"Small Text"},
    ]
    upsert_doctype({
        "name":"CCCM Facility Line","module":MODULE,"istable":1,
        "fields": facility_fields,
        "permissions":[{"role":"System Manager","read":1,"write":1,"create":1,"delete":1}]
    })

    # -----------------------------
    # Child: CCCM Issue Referral Line (safe name)
    # -----------------------------
    issue_fields = [
        {"fieldname":"issue_date","label":"Issue Date","fieldtype":"Date","in_list_view":1},
        {"fieldname":"category","label":"Category","fieldtype":"Select","options":"Protection\nGBV Risk\nWASH\nShelter\nHealth\nSite Management\nAccess/Security\nOther"},
        {"fieldname":"severity","label":"Severity (1-5)","fieldtype":"Select","options":"1\n2\n3\n4\n5"},
        {"fieldname":"description","label":"Description","fieldtype":"Small Text"},
        {"fieldname":"referred_to","label":"Referred To","fieldtype":"Data"},
        {"fieldname":"status","label":"Status","fieldtype":"Select","options":"Open\nIn Progress\nResolved\nClosed","default":"Open","in_list_view":1},
        {"fieldname":"evidence","label":"Evidence","fieldtype":"Attach"},
    ]
    if frappe.db.exists("DocType", "Partners"):
        issue_fields[4] = {"fieldname":"referred_to","label":"Referred To","fieldtype":"Link","options":"Partners","in_list_view":1}
    upsert_doctype({
        "name":"CCCM Issue Referral Line","module":MODULE,"istable":1,
        "fields": issue_fields,
        "permissions":[{"role":"System Manager","read":1,"write":1,"create":1,"delete":1}]
    })

    # -----------------------------
    # Parent: CCCM Site
    # -----------------------------
    site_fields = [
        {"fieldname":"site_name","label":"Site Name","fieldtype":"Data","reqd":1,"in_list_view":1,"bold":1},
        {"fieldname":"site_code","label":"Site Code","fieldtype":"Data","unique":1,"in_list_view":1},
        {"fieldname":"site_status","label":"Site Status","fieldtype":"Select","options":"Active\nTemporarily Closed\nClosed","default":"Active","in_list_view":1},
        {"fieldname":"site_type","label":"Site Type","fieldtype":"Select","options":"Camp\nCollective Center\nSpontaneous Site\nTransit Site\nOther"},

        {"fieldname":"open_date","label":"Opening Date","fieldtype":"Date"},
        {"fieldname":"close_date","label":"Closure Date","fieldtype":"Date"},

        {"fieldname":"governorate","label":"Governorate","fieldtype":"Link","options":"Governorate"},
        {"fieldname":"district","label":"District","fieldtype":"Link","options":"Districts"},
        {"fieldname":"sub_district","label":"Sub-District","fieldtype":"Link","options":"Sub-Districts"},
        {"fieldname":"village","label":"Village","fieldtype":"Link","options":"Villages"},

        {"fieldname":"latitude","label":"Latitude","fieldtype":"Float"},
        {"fieldname":"longitude","label":"Longitude","fieldtype":"Float"},

        {"fieldname":"managing_agency","label":"Managing Agency","fieldtype":"Data"},
        {"fieldname":"site_focal_name","label":"Site Focal Name","fieldtype":"Data"},
        {"fieldname":"site_focal_phone","label":"Site Focal Phone","fieldtype":"Data","options":"Phone"},

        {"fieldname":"households","label":"Households (current est.)","fieldtype":"Int"},
        {"fieldname":"individuals","label":"Individuals (current est.)","fieldtype":"Int"},

        {"fieldname":"notes","label":"Notes","fieldtype":"Small Text"},
        {"fieldname":"attachments","label":"Attachments","fieldtype":"Attach"},

        {"fieldname":"services","label":"Services","fieldtype":"Table","options":"CCCM Service Line"},
        {"fieldname":"population_snapshots","label":"Population Snapshots","fieldtype":"Table","options":"CCCM Population Snapshot"},
        {"fieldname":"facilities","label":"Facilities","fieldtype":"Table","options":"CCCM Facility Line"},
        {"fieldname":"issues_referrals","label":"Issues / Referrals","fieldtype":"Table","options":"CCCM Issue Referral Line"},
    ]
    # Optional upstream links (insert right after Site Name)
    insert_at = 1
    if frappe.db.exists("DocType", "Incident Reports"):
        site_fields.insert(insert_at, {"fieldname":"incident_report","label":"Incident Report","fieldtype":"Link","options":"Incident Reports"}); insert_at += 1
    if frappe.db.exists("DocType", "Donors"):
        site_fields.insert(insert_at, {"fieldname":"donor","label":"Donor","fieldtype":"Link","options":"Donors"}); insert_at += 1
    if frappe.db.exists("DocType", "Partners"):
        site_fields.insert(insert_at, {"fieldname":"partner","label":"Managing Partner","fieldtype":"Link","options":"Partners"})
        # also convert managing_agency to Link
        for i, f in enumerate(site_fields):
            if f["fieldname"] == "managing_agency":
                site_fields[i] = {"fieldname":"managing_agency","label":"Managing Agency","fieldtype":"Link","options":"Partners"}
                break

    upsert_doctype({
        "name":"CCCM Site","module":MODULE,
        "autoname":"format:SITE-{YYYY}-{#####}","title_field":"site_name","track_changes":1,
        "search_fields":"site_name,site_code,governorate,district",
        "fields": site_fields,
        "permissions":[
            {"role":"System Manager","read":1,"write":1,"create":1,"delete":1},
            {"role":"All","read":1}
        ]
    })

    # -----------------------------
    # National Society Programme
    # -----------------------------
    LINK_TARGET = "National Society" if frappe.db.exists("DocType", "National Society") else "Company"
    nsp_fields = [
        {"fieldname":"program_name","label":"Program Name","fieldtype":"Data","reqd":1,"in_list_view":1,"bold":1},
        {"fieldname":"long_name","label":"Long Name","fieldtype":"Data","in_list_view":1},
        {"fieldname":"national_society","label":"National Society","fieldtype":"Link","options":LINK_TARGET,"reqd":1,"in_list_view":1},
        {"fieldname":"description","label":"Description","fieldtype":"Text Editor"},
        {"fieldname":"status","label":"Status","fieldtype":"Select","options":"Active\nInactive","default":"Active","in_list_view":1},
    ]
    upsert_doctype({
        "name":"National Society Programme","module":MODULE,
        "autoname":"format:{national_society}-{program_name}","title_field":"program_name",
        "track_changes":1,"search_fields":"program_name,long_name,national_society",
        "fields": nsp_fields,
        "permissions":[
            {"role":"System Manager","read":1,"write":1,"create":1,"delete":1},
            {"role":"All","read":1}
        ]
    })

    # Uniqueness: Program Name within a National Society
    ensure_server_script(
        name="National Society Programme - Uniqueness",
        doctype="National Society Programme",
        event="Before Save",
        code="""
exists = frappe.db.exists(
    "National Society Programme",
    {
        "national_society": doc.national_society,
        "program_name": doc.program_name,
        "name": ("!=", doc.name),
    },
)
if exists:
    frappe.throw(_("Program Name must be unique within the selected National Society."))
"""
    )

    frappe.clear_cache()
    print("🎉 CCCM pack + National Society Programme ready.")
    print("➡️  Open: /app/cccm-site  and  /app/national-society-programme")
