from frappe import _

def get_data():
    return [
        {
            "module_name": "Yemen Red Crescent Society",
            "color": "red",
            "icon": "octicon octicon-heart",
            "type": "module",
            "label": _("Yemen Red Crescent Society"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Program",
                    "label": _("Program"),
                    "description": _("Program master records"),
                },
                {
                    "type": "doctype",
                    "name": "Objective",
                    "label": _("Objective"),
                    "description": _("Program objectives"),
                },
                {
                    "type": "doctype",
                    "name": "Indicator",
                    "label": _("Indicator"),
                    "description": _("Monitoring indicators"),
                },
                {
                    "type": "doctype",
                    "name": "Activity",
                    "label": _("Activity"),
                    "description": _("Field activities"),
                },
                {
                    "type": "doctype",
                    "name": "Monitoring Log",
                    "label": _("Monitoring Log"),
                    "description": _("Track field progress"),
                },
                {
                    "type": "doctype",
                    "name": "Evaluation",
                    "label": _("Evaluation"),
                    "description": _("Project evaluations"),
                },
                {
                    "type": "doctype",
                    "name": "Field Visit Log",
                    "label": _("Field Visit Log"),
                    "description": _("Monitoring visits"),
                },
                {
                    "type": "doctype",
                    "name": "Report Submission",
                    "label": _("Report Submission"),
                    "description": _("Narrative and donor reports"),
                }
            ]
        }
    ]
