{
  "doctype": "DocType",
  "name": "Programme Activity",
  "module": "Yemen Red Crescent Society",
  "custom": 0,
  "istable": 1,
  "fields": [
    {
      "fieldname": "activity_name",
      "label": "Activity Name",
      "fieldtype": "Data",
      "reqd": 1
    },
    {
      "fieldname": "responsible",
      "label": "Responsible",
      "fieldtype": "Link",
      "options": "User"
    },
    {
      "fieldname": "planned_date",
      "label": "Planned Date",
      "fieldtype": "Date"
    },
    {
      "fieldname": "status",
      "label": "Status",
      "fieldtype": "Select",
      "options": "Planned\nOngoing\nCompleted"
    }
  ],
  "permissions": [
    {
      "role": "System Manager",
      "read": 1,
      "write": 1,
      "create": 1,
      "delete": 1,
      "submit": 1,
      "cancel": 1,
      "amend": 1
    }
  ]
}
