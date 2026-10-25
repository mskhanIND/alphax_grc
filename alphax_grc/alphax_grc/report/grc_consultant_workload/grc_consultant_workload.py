import frappe
from frappe import _


def execute(filters=None):
    cols = [
        {"label": _("Consultant"), "fieldname": "assigned_consultant", "fieldtype": "Link", "options": "User", "width": 220},
        {"label": _("Open assessments"), "fieldname": "open_count", "fieldtype": "Int", "width": 140},
        {"label": _("Awaiting review"), "fieldname": "review_count", "fieldtype": "Int", "width": 140},
        {"label": _("Clarification pending"), "fieldname": "clar_count", "fieldtype": "Int", "width": 160},
    ]
    rows = {}
    for a in frappe.get_list("GRC Assessment", fields=["assigned_consultant", "status"], limit_page_length=0):
        k = a.assigned_consultant or _("Unassigned")
        r = rows.setdefault(k, {"assigned_consultant": a.assigned_consultant, "open_count": 0, "review_count": 0, "clar_count": 0})
        if a.status in ("Draft", "In Progress"):
            r["open_count"] += 1
        elif a.status in ("Submitted", "Resubmitted", "Under Review"):
            r["review_count"] += 1
        elif a.status == "Clarification Required":
            r["clar_count"] += 1
    return cols, list(rows.values())
