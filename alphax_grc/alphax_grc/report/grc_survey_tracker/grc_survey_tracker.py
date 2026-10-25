import frappe
from frappe import _
from frappe.utils import date_diff, today


def execute(filters=None):
    cols = [
        {"label": _("Assessment"), "fieldname": "name", "fieldtype": "Link", "options": "GRC Assessment", "width": 150},
        {"label": _("Organization"), "fieldname": "organization", "fieldtype": "Link", "options": "GRC Organization", "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 140},
        {"label": _("Due"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
        {"label": _("Days overdue"), "fieldname": "overdue", "fieldtype": "Int", "width": 100},
        {"label": _("Answered"), "fieldname": "answered_count", "fieldtype": "Int", "width": 90},
        {"label": _("Consultant"), "fieldname": "assigned_consultant", "fieldtype": "Link", "options": "User", "width": 160},
        {"label": _("Reviewer"), "fieldname": "reviewer", "fieldtype": "Link", "options": "User", "width": 160},
    ]
    rows = frappe.get_list("GRC Assessment", fields=["name", "organization", "status", "due_date", "answered_count", "assigned_consultant", "reviewer"], order_by="due_date asc")
    for r in rows:
        r["overdue"] = max(0, date_diff(today(), r.due_date)) if r.due_date and r.status in ("Draft", "In Progress", "Clarification Required") else 0
    return cols, rows
