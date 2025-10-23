import frappe

@frappe.whitelist()
def get_volunteers_with_location(last_days=60, governorate=None, gender=None, role=None):
    filters = "a.latitude IS NOT NULL AND a.longitude IS NOT NULL"
    if last_days:
        filters += f" AND DATEDIFF(NOW(), v.modified) <= {int(last_days)}"
    if governorate:
        filters += f" AND a.governorate = {frappe.db.escape(governorate)}"
    if gender:
        filters += f" AND v.gender = {frappe.db.escape(gender)}"
    if role:
        filters += f" AND v.role LIKE {frappe.db.escape('%' + role + '%')}"

    return frappe.db.sql(f"""
        SELECT 
            v.name,
            v.full_name,
            v.gender,
            v.role,
            v.profile_image,
            a.latitude,
            a.longitude,
            a.home_address,
            a.village,
            a.governorate
        FROM `tabYRCS Volunteers` v
        JOIN `tabVolunteer Address` a ON a.parent = v.name
        WHERE {filters}
    """, as_dict=True)
