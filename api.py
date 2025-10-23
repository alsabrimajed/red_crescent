import frappe, requests

@frappe.whitelist()
def reverse_geocode(lat: float, lng: float) -> str:
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "jsonv2", "lat": lat, "lon": lng, "addressdetails": 1},
            headers={"User-Agent": "Frappe-ERPNext-Volunteer-Map/1.0"}
        )
        r.raise_for_status()
        j = r.json()
        display = j.get("display_name")
        if display:
            return display
        a = j.get("address", {}) or {}
        parts = [
            a.get("road"), a.get("suburb"),
            a.get("city") or a.get("town") or a.get("village"),
            a.get("state"), a.get("postcode"), a.get("country")
        ]
        return ", ".join([p for p in parts if p])
    except Exception:
        return f"{float(lat):.6f}, {float(lng):.6f}"


@frappe.whitelist(allow_guest=True)
def get_mapbox_token():
    """Expose Mapbox token from site_config.json"""
    return frappe.conf.get("mapbox_token")


@frappe.whitelist(allow_guest=True)
def get_district_risks(governorate=None, risk_type=None, min_severity=None):
    filters = {"latitude": ["is", "set"], "longitude": ["is", "set"]}
    if governorate:
        filters["governorate"] = governorate
    if risk_type:
        filters["risk_type"] = risk_type

    rows = frappe.get_all(
        "District Risk Profile",
        fields=[
            "name", "governorate", "district", "sub_district", "village",
            "risk_type", "impact", "risk_ranking as risk_level",
            "latitude", "longitude"
        ],
        filters=filters,
        limit_page_length=2000,
        order_by="modified desc",
    )

    out = []
    for r in rows:
        impact = frappe.utils.cint(r.get("impact") or 0)
        level = frappe.utils.cint(r.get("risk_level") or 0)
        severity = impact * level
        if min_severity is not None and severity < int(min_severity):
            continue
        r["severity"] = severity
        r["latitude"] = float(r["latitude"])
        r["longitude"] = float(r["longitude"])
        out.append(r)

    return out


def boot_session(bootinfo):
    token = frappe.conf.get("mapbox_token")
    if token:
        bootinfo["mapbox_token"] = token


@frappe.whitelist(allow_guest=True)
def get_volunteer_addresses_geojson(governorate=None, district=None, address_type=None, q=None, team=None, sex=None):
    CHILD = "Volunteer Address"
    PARENT = "YRCS Volunteers"

    volunteer_whitelist = None
    if team:
        members = frappe.get_all(
            "Team Member",
            filters={"parenttype": "Teams", "parent": team},
            fields=["volunteer"]
        )
        volunteer_whitelist = {m.volunteer for m in members if m.volunteer}
        if not volunteer_whitelist:
            return {"type": "FeatureCollection", "features": []}

    filters = {"parenttype": PARENT, "latitude": ["is", "set"], "longitude": ["is", "set"]}
    if governorate:
        filters["governorate"] = governorate
    if district:
        filters["district"] = district
    if address_type:
        filters["add_type"] = address_type

    or_filters = []
    if q:
        or_filters = [
            [CHILD, "home_address", "like", f"%{q}%"],
            [CHILD, "village", "like", f"%{q}%"],
            [CHILD, "district", "like", f"%{q}%"],
        ]

    rows = frappe.get_all(
        CHILD,
        fields=[
            "name", "parent", "add_type",
            "governorate", "district", "sub_district", "village",
            "home_address", "latitude", "longitude",
        ],
        filters=filters,
        or_filters=or_filters,
        limit_page_length=5000,
        order_by="modified desc",
    )

    if volunteer_whitelist is not None:
        rows = [r for r in rows if r.parent in volunteer_whitelist]

    parent_names = list({r.parent for r in rows})
    name_map, sex_map, img_map = {}, {}, {}
    if parent_names:
        pr = frappe.get_all(
            PARENT,
            filters={"name": ["in", parent_names]},
            fields=["name", "firstname", "middle_name", "last_name", "sex", "image"]
        )
        for p in pr:
            full = " ".join([p.get("firstname") or "", p.get("middle_name") or "", p.get("last_name") or ""]).strip()
            name_map[p.name] = full or p.name
            sex_map[p.name] = p.sex or ""
            img_map[p.name] = p.image or ""

    feats = []
    for r in rows:
        if not r.latitude or not r.longitude:
            continue
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(r.longitude), float(r.latitude)]},
            "properties": {
                "row": r.name,
                "volunteer_id": r.parent,
                "volunteer": name_map.get(r.parent, r.parent),
                "sex": sex_map.get(r.parent),
                "image": img_map.get(r.parent),
                "address_type": r.add_type,
                "governorate": r.governorate,
                "district": r.district,
                "sub_district": r.sub_district,
                "village": r.village,
                "home_address": r.home_address,
            }
        })

    return {"type": "FeatureCollection", "features": feats}


@frappe.whitelist(allow_guest=True)
def get_distinct_vol_address_types():
    rows = frappe.get_all(
        "Volunteer Address",
        fields=["distinct add_type as add_type"],
        filters={"parenttype": "YRCS Volunteers"}
    )
    return [r.add_type for r in rows if r.add_type]


@frappe.whitelist(allow_guest=True)
def get_vol_governorates():
    rows = frappe.db.sql("""
        select distinct governorate
        from `tabVolunteer Address`
        where parenttype = 'YRCS Volunteers'
          and ifnull(governorate,'')!=''
        order by governorate
    """, as_dict=True)
    return [r.governorate for r in rows]


@frappe.whitelist(allow_guest=True)
def get_vol_districts(governorate=None):
    if governorate:
        rows = frappe.db.sql("""
            select distinct district
            from `tabVolunteer Address`
            where parenttype = 'YRCS Volunteers'
              and ifnull(district,'')!=''
              and governorate = %s
            order by district
        """, (governorate,), as_dict=True)
    else:
        rows = frappe.db.sql("""
            select distinct district
            from `tabVolunteer Address`
            where parenttype = 'YRCS Volunteers'
              and ifnull(district,'')!=''
            order by district
        """, as_dict=True)
    return [r.district for r in rows]


@frappe.whitelist(allow_guest=True)
def get_teams_for_filter():
    return [r.name for r in frappe.get_all("Teams", fields=["name"], order_by="name asc")]
