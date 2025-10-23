import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def create_ambulance_doctype():
    if not frappe.db.exists("DocType", "Ambulance"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Ambulance",
            "module": "Yemen Red Crescent Society",
            "custom": 1,
            "fields": [
                {"fieldname": "plate_number", "fieldtype": "Data", "label": "Plate Number", "reqd": 1},
                {"fieldname": "ambulance_type", "fieldtype": "Select", "label": "Type", "options": "4x4\nVan\nMini Bus"},
                {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Available\nIn Use\nMaintenance", "default": "Available"},
                {"fieldname": "location", "fieldtype": "Link", "label": "Location", "options": "Warehouse"},
                {"fieldname": "driver_name", "fieldtype": "Data", "label": "Driver Name"},
                {"fieldname": "remarks", "fieldtype": "Small Text", "label": "Remarks"}
            ],
            "permissions": [
                {
                    "role": "System Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "delete": 1
                }
            ],
            "is_submittable": 0,
            "track_changes": 1,
            "track_views": 1,
            "editable_grid": 1,
            "quick_entry": 1,
        })
        doc.insert()
        frappe.db.commit()
        print("✅ Created custom Doctype: Ambulance")
    else:
        print("ℹ️ Doctype 'Ambulance' already exists.")


