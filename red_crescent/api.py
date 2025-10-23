import math
import requests
from urllib.parse import quote

import frappe


# ------------------------------- Helpers ------------------------------- #

def make_point_feature(lat, lng, props):
    """Build a GeoJSON Point feature with safe float casting."""
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
        "properties": props,
    }


# ------------------------------- Public APIs ------------------------------- #

@frappe.whitelist()
def reverse_geocode(lat: float, lng: float) -> str:
    """Reverse geocode using Nominatim with a graceful fallback."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "jsonv2", "lat": lat, "lon": lng, "addressdetails": 1},
            headers={"User-Agent": "Frappe-ERPNext-Volunteer-Map/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        j = r.json()
        display = j.get("display_name")
        if display:
            return display
        a = j.get("address", {}) or {}
        parts = [
            a.get("road"),
            a.get("suburb"),
            a.get("city") or a.get("town") or a.get("village"),
            a.get("state"),
            a.get("postcode"),
            a.get("country"),
        ]
        return ", ".join([p for p in parts if p])
    except Exception:
        return f"{float(lat):.6f}, {float(lng):.6f}"


@frappe.whitelist(allow_guest=True)
def get_mapbox_token():
    return frappe.conf.get("mapbox_token")


def boot_session(bootinfo):
    token = frappe.conf.get("mapbox_token")
    if token:
        bootinfo["mapbox_token"] = token


# ------------------------------- Risk / Needs ------------------------------- #
import json
import frappe
from frappe.utils import cint

@frappe.whitelist()
def get_district_risks(governorate=None, district=None, risk_type=None, min_severity=None, limit_start=0, page_length=2000):
    filters = {}
    if governorate:
        filters["governorate"] = governorate
    if district:
        filters["district"] = district
    if risk_type:
        filters["risk_type"] = risk_type

    default_mode = not risk_type and (min_severity in (None, "", 0, "0"))

    rows = frappe.get_all(
        "District Risk Profile",
        fields=[
            "name", "governorate", "district", "sub_district", "village",
            "risk_type", "impact", "risk_ranking as risk_level",
            "latitude", "longitude"
        ],
        filters=filters,
        start=int(limit_start),
        page_length=int(page_length),
        order_by="modified desc",
    )

    population_rows = frappe.get_all(
        "Yemen Population by District - 2025",
        fields=["district", "population_total"]
    )
    population_map = {
        row["district"]: row["population_total"] or 0
        for row in population_rows
    }

    district_map = {}
    for r in rows:
        impact = cint(r.get("impact") or 0)
        level = cint(r.get("risk_level") or 0)
        severity = impact * level

        dist_key = f"{r['governorate']}::{r['district']}"

        if dist_key not in district_map:
            district_map[dist_key] = {
                "governorate": r["governorate"],
                "district": r["district"],
                "sub_district": r.get("sub_district"),
                "village": r.get("village"),
                "latitude": r.get("latitude"),
                "longitude": r.get("longitude"),
                "all_risks": [],
                "filtered_risks": []
            }

        # جميع المخاطر
        district_map[dist_key]["all_risks"].append({
            "name": r["name"],
            "risk_type": r["risk_type"],
            "impact": impact,
            "risk_level": level,
            "severity": severity
        })

        # قائمة المخاطر المفلترة
        if min_severity is None or severity >= int(min_severity):
            district_map[dist_key]["filtered_risks"].append({
                "name": r["name"],
                "risk_type": r["risk_type"],
                "impact": impact,
                "risk_level": level,
                "severity": severity
            })

    features = []
    for dist_key, data in district_map.items():
        if not data["filtered_risks"]:
            # 🧠 في الوضع الافتراضي → نعرض أعلى خطر
            if default_mode and data["all_risks"]:
                top_risk = max(data["all_risks"], key=lambda r: r["severity"])
                data["filtered_risks"].append(top_risk)
            else:
                continue  # ❌ تجاهل إذا مافي مخاطر

        geom = None
        district_ar = data["district"]

        try:
            dist_doc = frappe.db.get_value(
                "Districts",
                {
                    "governorate": data["governorate"],
                    "name": data["district"]
                },
                ["location_geojson", "ar_name"],
                as_dict=True,
            )
            if dist_doc:
                if dist_doc.get("ar_name"):
                    district_ar = dist_doc["ar_name"]
                if dist_doc.get("location_geojson"):
                    try:
                        geom = json.loads(dist_doc["location_geojson"])
                    except Exception:
                        geom = None
        except Exception as e:
            frappe.logger().error(f"GeoJSON load failed for {dist_key}: {e}")

        if not geom and data["latitude"] and data["longitude"]:
            try:
                geom = {
                    "type": "Point",
                    "coordinates": [float(data["longitude"]), float(data["latitude"])]
                }
            except Exception:
                geom = None

        if not geom:
            continue

        max_severity = max([r["severity"] for r in data["all_risks"]]) if data["all_risks"] else 0
        total_pop = population_map.get(data["district"], 0)

        # 🆕 حساب السكان المعرضين بنسبة من السكان
        ratio = max_severity / 100 if max_severity else 0
        ratio = min(ratio, 1)  # لا يتجاوز 100%
        exposed_pop = int(total_pop * ratio)

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "governorate": data["governorate"],
                "district": data["district"],
                "district_ar": district_ar,
                "sub_district": data.get("sub_district"),
                "village": data.get("village"),
                "severity": max_severity,
                "risks": data["filtered_risks"],
                "population_total": total_pop,
                "exposed_population": exposed_pop
            }
        })

    # 🆕 إجماليات على مستوى البلد
    total_population_all = sum(population_map.values())
    total_exposed = sum(f["properties"]["exposed_population"] for f in features)

    return {
        "type": "FeatureCollection",
        "features": features,
        "limit_start": int(limit_start),
        "page_length": int(page_length),
        "records_returned": len(rows),
        "population_total_all": total_population_all,
        "population_exposed_total": total_exposed
    }

@frappe.whitelist()
def add_map_risk(district, risk_type, impact, risk_level, latitude, longitude):
    impact = int(impact)
    risk_level = int(risk_level)

    doc = frappe.get_doc({
        "doctype": "District Risk Profile",
        "district": district,
        "risk_type": risk_type,
        "impact": impact,
        "risk_ranking": risk_level,
        "severity": impact * risk_level,  # optional, if not handled in validate()
        "latitude": float(latitude),
        "longitude": float(longitude),
        "date": frappe.utils.nowdate()
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return "OK"



@frappe.whitelist(allow_guest=True)
def get_district_sectoral_needs_geojson(governorate=None, district=None, sector=None):
    """GeoJSON of District Sectoral Needs with optional filters."""
    filters = {"latitude": ["is", "set"], "longitude": ["is", "set"]}
    if governorate:
        filters["governorate"] = governorate
    if district:
        filters["district"] = district
    if sector:
        filters["sector"] = sector

    rows = frappe.get_all(
        "District Sectoral Needs",
        fields=[
            "name", "gov_pcode", "dis_pcode", "governorate", "district",
            "sector", "severity_score", "latitude", "longitude",
        ],
        filters=filters,
        limit_page_length=2000,
    )

    feats = []
    for r in rows:
        feats.append(
            make_point_feature(
                r.latitude,
                r.longitude,
                {
                    "id": r.name,
                    "governorate": r.governorate,
                    "district": r.district,
                    "sector": r.sector,
                    "severity": int(r.severity_score or 0),
                    "docname": r.name,
                    "label": f"{(r.sector or 'Sector')} - {(r.district or 'District')}",
                },
            )
        )
    return {"type": "FeatureCollection", "features": feats}


# ------------------------------- Volunteers ------------------------------- #

@frappe.whitelist(allow_guest=True)
def get_volunteer_addresses_geojson(
    governorate=None, district=None, address_type=None, q=None, team=None, sex=None
):
    CHILD = "Volunteer Address"
    PARENT = "YRCS Volunteers"

    volunteer_whitelist = None
    if team:
        members = frappe.get_all(
            "Team Member", filters={"parenttype": "Teams", "parent": team}, fields=["volunteer"]
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
            fields=["name", "firstname", "middle_name", "last_name", "sex", "volunteer_photo"],
        )
        for p in pr:
            full = " ".join(
                [p.get("firstname") or "", p.get("middle_name") or "", p.get("last_name") or ""]
            ).strip()
            name_map[p.name] = full or p.name
            sex_map[p.name] = p.sex or ""
            img_map[p.name] = p.volunteer_photo or ""

    feats = []
    for r in rows:
        if not r.latitude or not r.longitude:
            continue

        raw_img = img_map.get(r.parent)
        image_url = (
            frappe.utils.get_url(f"/files/{quote(raw_img)}")
            if raw_img
            else frappe.utils.get_url("/files/default-avatar.png")
        )

        feats.append(
            make_point_feature(
                r.latitude,
                r.longitude,
                {
                    "row": r.name,
                    "volunteer_id": r.parent,
                    "volunteer": name_map.get(r.parent, r.parent),
                    "sex": sex_map.get(r.parent),
                    "image": image_url,
                    "address_type": r.add_type,
                    "governorate": r.governorate,
                    "district": r.district,
                    "sub_district": r.sub_district,
                    "village": r.village,
                    "home_address": r.home_address,
                    "weight": 1,
                },
            )
        )

    return {"type": "FeatureCollection", "features": feats}


@frappe.whitelist(allow_guest=True)
def get_distinct_vol_address_types():
    rows = frappe.get_all(
        "Volunteer Address",
        fields=["distinct add_type as add_type"],
        filters={"parenttype": "YRCS Volunteers"},
    )
    return [r.add_type for r in rows if r.add_type]


@frappe.whitelist(allow_guest=True)
def get_vol_governorates():
    rows = frappe.db.sql(
        """
        SELECT DISTINCT governorate
        FROM `tabVolunteer Address`
        WHERE parenttype = 'YRCS Volunteers'
          AND IFNULL(governorate, '') != ''
        ORDER BY governorate
        """,
        as_dict=True,
    )
    return [r.governorate for r in rows]


@frappe.whitelist(allow_guest=True)
def get_vol_districts(governorate=None):
    if governorate:
        rows = frappe.db.sql(
            """
            SELECT DISTINCT district
            FROM `tabVolunteer Address`
            WHERE parenttype = 'YRCS Volunteers'
              AND IFNULL(district, '') != ''
              AND governorate = %s
            ORDER BY district
            """,
            (governorate,),
            as_dict=True,
        )
    else:
        rows = frappe.db.sql(
            """
            SELECT DISTINCT district
            FROM `tabVolunteer Address`
            WHERE parenttype = 'YRCS Volunteers'
              AND IFNULL(district, '') != ''
            ORDER BY district
            """,
            as_dict=True,
        )
    return [r.district for r in rows]


@frappe.whitelist(allow_guest=True)
def get_teams_for_filter():
    return [r.name for r in frappe.get_all("Teams", fields=["name"], order_by="name asc")]


@frappe.whitelist(allow_guest=True)
def get_nearest_volunteers(
    lat, lng, radius_km=10, address_type=None, team=None, sex=None, limit=100
):
    from frappe.utils.data import flt

    lat = flt(lat)
    lng = flt(lng)
    radius_km = flt(radius_km)

    volunteer_ids = None
    if team:
        members = frappe.get_all("Team Member", filters={"parent": team}, fields=["volunteer"])
        volunteer_ids = [m.volunteer for m in members if m.volunteer]

    filters = {"latitude": ["is", "set"], "longitude": ["is", "set"]}
    if address_type:
        filters["add_type"] = address_type

    rows = frappe.get_all(
        "Volunteer Address",
        fields=[
            "name", "parent", "add_type", "governorate", "district", "sub_district",
            "village", "home_address", "latitude", "longitude",
        ],
        filters=filters,
        limit_page_length=5000,
    )

    if volunteer_ids:
        rows = [r for r in rows if r.parent in volunteer_ids]

    parent_names = list({r.parent for r in rows})
    name_map, sex_map, img_map = {}, {}, {}

    if parent_names:
        volunteers = frappe.get_all(
            "YRCS Volunteers",
            filters={"name": ["in", parent_names]},
            fields=["name", "sex", "volunteer_photo", "firstname", "middle_name", "last_name"],
        )
        for v in volunteers:
            full_name = " ".join(filter(None, [v.firstname, v.middle_name, v.last_name])) or v.name
            name_map[v.name] = full_name
            sex_map[v.name] = v.sex
            img_map[v.name] = v.volunteer_photo or "/files/default-avatar.png"

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
            math.radians(lat2)
        ) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    out = []
    for r in rows:
        try:
            d_km = haversine(lat, lng, float(r.latitude), float(r.longitude))
            if d_km > radius_km:
                continue
            v_id = r.parent
            v_sex = sex_map.get(v_id)
            if sex and sex != v_sex:
                continue
            out.append(
                {
                    "volunteer_id": v_id,
                    "volunteer": name_map.get(v_id, v_id),
                    "sex": v_sex,
                    "image": img_map.get(v_id),
                    "address_type": r.add_type,
                    "governorate": r.governorate,
                    "district": r.district,
                    "sub_district": r.sub_district,
                    "village": r.village,
                    "home_address": r.home_address,
                    "latitude": float(r.latitude),
                    "longitude": float(r.longitude),
                    "distance_km": round(d_km, 2),
                }
            )
        except Exception:
            continue

    return sorted(out, key=lambda x: x["distance_km"])[: int(limit)]


# ------------------------------- IDPs ------------------------------- #

@frappe.whitelist(allow_guest=True)
def get_idps_sites_geojson():
    rows = frappe.get_all(
        "IDPs Sites",
        fields=[
            "name", "implementing_partner", "site_category", "coverage",
            "funded_by", "governorate", "district", "sub_district",
            "location_village", "latitude", "longitude", "hhs_numbers",
        ],
        filters={"latitude": ["is", "set"], "longitude": ["is", "set"]},
        limit_page_length=1000,
    )

    feats = []
    for r in rows:
        feats.append(
            make_point_feature(
                r.latitude,
                r.longitude,
                {
                    "id": r.name,
                    "partner": r.implementing_partner,
                    "category": r.site_category,
                    "coverage": r.coverage,
                    "funded_by": r.funded_by,
                    "governorate": r.governorate,
                    "district": r.district,
                    "sub_district": r.sub_district,
                    "village": r.location_village,
                    "hhs_numbers": r.hhs_numbers or 0,
                    "docname": r.name,
                },
            )
        )
    return {"type": "FeatureCollection", "features": feats}


# ------------------------------- Fleet / Warehouses / Assets ------------------------------- #

@frappe.whitelist(allow_guest=True)
def get_vehicles_geojson(branch=None, status=None, q=None):
    filters = {"latitude": ["is", "set"], "longitude": ["is", "set"]}
    if branch:
        filters["location"] = branch
    if status:
        filters["status"] = status
    if q:
        filters["name"] = ["like", f"%{q}%"]

    rows = frappe.get_all(
        "YRCS Fleet Vehicle",
        fields=["name", "latitude", "longitude", "location", "status"],
        filters=filters,
        limit_page_length=2000,
    )

    feats = []
    for r in rows:
        feats.append(
            make_point_feature(
                r.latitude,
                r.longitude,
                {
                    "label": r.name,
                    # Keep "branch" key for frontend compatibility, value from "location" field
                    "branch": r.location,
                    "status": r.status,
                },
            )
        )
    return {"type": "FeatureCollection", "features": feats}


@frappe.whitelist(allow_guest=True)
def get_warehouses_geojson(branch=None, warehouse_type=None, q=None):
    filters = {"latitude": ["is", "set"], "longitude": ["is", "set"]}
    if branch:
        filters["branch"] = branch
    if warehouse_type:
        filters["warehouse_type"] = warehouse_type
    if q:
        filters["name"] = ["like", f"%{q}%"]

    rows = frappe.get_all(
        "Warehouse",
        fields=["name", "latitude", "longitude", "branch", "warehouse_type"],
        filters=filters,
        limit_page_length=2000,
    )

    feats = []
    for r in rows:
        feats.append(
            make_point_feature(
                r.latitude,
                r.longitude,
                {
                    "label": r.name,
                    "branch": r.branch,
                    "type": r.warehouse_type
                },
            )
        )
    return {"type": "FeatureCollection", "features": feats}


@frappe.whitelist(allow_guest=True)
def get_assets_geojson(branch=None, asset_category=None, q=None):
    filters = {"latitude": ["is", "set"], "longitude": ["is", "set"]}
    if branch:
        filters["branch"] = branch
    if asset_category:
        filters["asset_category"] = asset_category
    if q:
        filters["name"] = ["like", f"%{q}%"]

    rows = frappe.get_all(
        "Asset",
        fields=[
            "name", "latitude", "longitude", "branch", "asset_category"
        ],
        filters=filters,
        limit_page_length=2000,
    )

    feats = []
    for r in rows:
        feats.append(
            make_point_feature(
                r.latitude,
                r.longitude,
                {
                    "label": r.name,
                    "branch": r.branch,
                    "category": r.asset_category
                },
            )
        )
    return {"type": "FeatureCollection", "features": feats}


# ------------------------------- Small Lookups ------------------------------- #

@frappe.whitelist()
def get_vehicle_statuses():
    """Return distinct vehicle statuses from Vehicle doctype"""
    return [
        r.status
        for r in frappe.get_all(
            "YRCS Fleet Vehicle", distinct=True, fields=["status"], order_by="status"
        )
    ]


@frappe.whitelist()
def get_warehouse_types():
    return [
        r.warehouse_type
        for r in frappe.get_all(
            "Warehouse", distinct=True, fields=["warehouse_type"], order_by="warehouse_type"
        )
    ]


@frappe.whitelist()
def get_asset_categories():
    return [
        r.asset_category_name
        for r in frappe.get_all(
            "Asset Category",
            distinct=True,
            fields=["asset_category_name"],
            order_by="asset_category_name",
        )
    ]
@frappe.whitelist(allow_guest=True)
def get_branches_for_filter(q: str | None = None):
    """Return list of branch names for filters (guest-safe).
    Works with NS Branch / Branch doctypes and branch_name / name fields."""
    # Pick doctype
    doctype = "NS Branch" if frappe.db.exists("DocType", "NS Branch") else "Branch"
    # Pick field
    field = "branch_name" if frappe.db.has_column(doctype, "branch_name") else "name"

    filters = {}
    if q:
        filters[field] = ["like", f"%{q}%"]

    rows = frappe.get_all(
        doctype,
        fields=[field],
        filters=filters,
        order_by=f"{field} asc",
        limit_page_length=1000,
    )
    return [r.get(field) for r in rows if r.get(field)]
import json
import frappe


def flip_coordinates(geometry):
    """Flip GeoJSON coordinates for Leaflet (lat/lon → lon/lat)"""
    def flip(coords):
        return [[[ [lat, lon] for lon, lat in polygon ] for polygon in multi ]] if geometry["type"] == "MultiPolygon" else \
               [[ [lat, lon] for lon, lat in ring ] for ring in coords]

    if not geometry or "coordinates" not in geometry:
        return geometry

    geometry["coordinates"] = flip(geometry["coordinates"])
    return geometry
import json

@frappe.whitelist(allow_guest=True)
def get_geojson_with_severity(sector=None, governorate=None, district=None):
    import json

    parent_filters = {}

    # Governorate filter
    if governorate:
        gov_name = frappe.db.get_value("Governorate", {"ar_name": governorate}, "name") or governorate
        parent_filters["governorate"] = gov_name

    # District filter
    if district:
        dist_name = frappe.db.get_value("Districts", {"ar_name": district}, "name")
        if not dist_name:
            dist_name = frappe.db.get_value("Districts", {"eng_name": district}, "name")
        parent_filters["district"] = dist_name or district

    records = frappe.get_all(
        "District Sectoral Needs",
        filters=parent_filters,
        fields=["name", "district", "location_geojson", "governorate", "dis_pcode"],
        limit_page_length=1000
    )

    # Preload lookups
    district_names = {
        d.name: {"ar": d.ar_name, "en": d.eng_name}
        for d in frappe.get_all("Districts", fields=["name", "ar_name", "eng_name"])
    }
    governorate_names = {
        g.name: g.ar_name
        for g in frappe.get_all("Governorate", fields=["name", "ar_name"])
    }
    sector_names = {
        s.name: s.ar_sector
        for s in frappe.get_all("Sectors", fields=["name", "ar_sector"])
    }

    features = []

    for rec in records:
        if not rec.location_geojson:
            continue

        try:
            geojson_data = json.loads(rec.location_geojson)
            geometry = geojson_data.get("geometry") if "geometry" in geojson_data else geojson_data
            if not geometry:
                continue

            severity_filters = {"parent": rec.name}
            if sector:
                severity_filters["sector"] = sector

            sector_rows = frappe.get_all(
                "Sector Severity",
                filters=severity_filters,
                fields=[
                    "sector", "severity", "total_pin",
                    "boys_0_17", "girls_0_17", "men_18_plus", "women_18_plus"
                ]
            )

            if sector and not sector_rows:
                continue

            max_severity = 0
            total_pin_sum = 0
            sector_severities = []

            for row in sector_rows:
                severity_val = int(row.severity or 0)
                if severity_val > max_severity:
                    max_severity = severity_val

                total_pin_sum += int(row.total_pin or 0)

                sector_ar = sector_names.get(row.sector, "")
                sector_severities.append({
                    "sector": row.sector,
                    "sector_ar": sector_ar,
                    "severity": row.severity,
                    "total_pin": row.total_pin or 0,
                    "boys_0_17": row.boys_0_17 or 0,
                    "girls_0_17": row.girls_0_17 or 0,
                    "men_18_plus": row.men_18_plus or 0,
                    "women_18_plus": row.women_18_plus or 0,
                })

            district_data = district_names.get(rec.district, {})
            governorate_ar = governorate_names.get(rec.governorate, "")

            features.append({
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "district": rec.district,
                    "district_ar": district_data.get("ar", rec.district),
                    "district_en": district_data.get("en", rec.district),
                    "governorate": rec.governorate,
                    "governorate_ar": governorate_ar,
                    "sector_severities": sector_severities,  # ✅ stays as JSON
                    "dis_pcode": rec.dis_pcode,
                    "max_severity": max_severity,
                    "total_pin_sum": total_pin_sum
                }
            })

        except Exception as e:
            frappe.log_error(f"GeoJSON parse error in {rec.name}: {e}", "get_geojson_with_severity")

    return {"type": "FeatureCollection", "features": features}


@frappe.whitelist()
def get_sectors_for_governorate(governorate):
    # Get all parent entries from District Sectoral Needs
    parent_names = frappe.get_all("District Sectoral Needs", 
        filters={"governorate": governorate},
        pluck="name"
    )

    if not parent_names:
        return []

    # Find distinct sectors from Sector Severity
    sector_ids = frappe.get_all("Sector Severity",
        filters={"parent": ["in", parent_names]},
        distinct=True,
        pluck="sector"
    )

    # Fetch sector names
    return frappe.get_all("Sectors",
        filters={"name": ["in", sector_ids]},
        fields=["name", "sector", "ar_sector"])
# red_crescent/api/district_geojson.py

import frappe
import json

@frappe.whitelist(allow_guest=True)
def get_districts_geojson():
    districts = frappe.get_all("Districts", fields=["name", "location_geojson"])
    features = []

    for d in districts:
        if not d.location_geojson:
            continue

        try:
            geometry = json.loads(d.location_geojson)
        except Exception:
            continue  # skip invalid GeoJSON

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "name": d.name
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }
import frappe
from frappe.model.naming import make_autoname

import frappe
from frappe.model.naming import make_autoname
import re

@frappe.whitelist()
def generate_incident_name(place, incident_type, date):
    def sanitize(text):
        text = re.sub(r'[^\w]', '', text)           # remove punctuation and spaces
        text = re.sub(r'[^\x00-\x7F]', '', text)    # remove Arabic / non-ASCII
        return text[:20] or "UNKNOWN"

    safe_place = sanitize(place)
    safe_type = sanitize(incident_type)
    safe_date = date.replace("-", "")  # should already be yyyyMMdd format

    prefix = f"{safe_place}-{safe_type}-{safe_date}-"
    return make_autoname(prefix + "####")
