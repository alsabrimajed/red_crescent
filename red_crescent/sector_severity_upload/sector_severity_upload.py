import frappe
import pandas as pd
import os

@frappe.whitelist()
def process_sector_file(docname):
    doc = frappe.get_doc("Sector Severity Upload", docname)

    if not doc.upload_file:
        frappe.throw("Please upload an Excel file first.")

    path = frappe.get_site_path("public", "files", os.path.basename(doc.upload_file))
    log = [f"📁 File path: {path}"]

    try:
        df = pd.read_excel(path)
        log.append(f"✅ File loaded. Rows found: {len(df)}")
    except Exception as e:
        doc.status_log = f"❌ Error reading Excel file: {e}"
        doc.save()
        return

    # Rename Excel columns
    df = df.rename(columns={
        "ID": "parent",
        "Sector": "sector",
        "Total PiN": "total_pin",
        "Boys (0-17)": "boys_0_17",
        "Men (18+)": "men_18_plus",
        "Girls (0-17)": "girls_0_17",
        "Women (18+)": "women_18_plus",
        "Severity": "severity"
    })

    # Get severity field options from child table
    child_table_doctype = "Sector Severity"  # Replace with your actual child table DocType
    severity_options = []
    try:
        meta = frappe.get_meta(child_table_doctype)
        severity_field = meta.get_field("severity")
        if severity_field and severity_field.options:
            severity_options = [opt.strip() for opt in severity_field.options.split("\n") if opt.strip()]
    except Exception as e:
        log.append(f"⚠️ Could not fetch severity options: {e}")

    def safe_int(value):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def safe_str(value):
        return str(value).strip() if pd.notna(value) else ""

    def normalize_severity(value):
        if pd.isna(value):
            return ""
        try:
            normalized = str(int(float(value))).strip()
        except Exception:
            normalized = safe_str(value)
        return normalized if normalized in severity_options else ""

    for index, row in enumerate(df.to_dict(orient="records")):
        try:
            parent_id = safe_str(row.get("parent"))
            sector = safe_str(row.get("sector"))
            severity = normalize_severity(row.get("severity"))

            log.append(f"\n➡️ Row {index + 1} | Parent: {parent_id} | Sector: {sector}")

            if not parent_id or not sector:
                log.append("⚠️ Skipped row: missing parent or sector")
                continue

            parent = frappe.get_doc("District Sectoral Needs", parent_id)
            updated = False

            for child in parent.get("sector") or []:
                if child.sector == sector:
                    child.total_pin = safe_int(row["total_pin"])
                    child.boys_0_17 = safe_int(row["boys_0_17"])
                    child.men_18_plus = safe_int(row["men_18_plus"])
                    child.girls_0_17 = safe_int(row["girls_0_17"])
                    child.women_18_plus = safe_int(row["women_18_plus"])
                    child.severity = severity
                    updated = True
                    log.append("🔄 Updated existing child row.")
                    break

            if not updated:
                try:
                    parent.append("sector", {
                        "sector": sector,
                        "total_pin": safe_int(row["total_pin"]),
                        "boys_0_17": safe_int(row["boys_0_17"]),
                        "men_18_plus": safe_int(row["men_18_plus"]),
                        "girls_0_17": safe_int(row["girls_0_17"]),
                        "women_18_plus": safe_int(row["women_18_plus"]),
                        "severity": severity
                    })
                    log.append("➕ Appended new child row.")
                except Exception as e:
                    log.append(f"❌ Error appending new child row: {e}")
                    continue

            parent.flags.ignore_validate = True
            parent.flags.ignore_mandatory = True
            parent.save()
            frappe.db.commit()
            log.append("💾 Saved and committed to DB.")

        except frappe.DoesNotExistError:
            log.append(f"❌ Parent record not found: {parent_id}")
        except Exception as e:
            log.append(f"❌ Error processing row {index + 1}: {e}")

    doc.status_log = "\n".join(log)
    doc.save()