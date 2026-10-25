"""Assessment activity trail: who did what and when. Never raises, so it cannot break a user action."""
import frappe

from alphax_grc.grc import access


def actor_type(user):
    if not user or user in ("Guest",):
        return "System"
    if user == "Administrator" or access.is_staff(user):
        return "Staff"
    return "Customer"


def log(assessment, event_type, detail="", user=None, question_code="", visible=1, organization=None, system=False):
    """assessment: name or doc. visible=0 keeps the entry staff-only (reviewer adjustments, internal notes)."""
    try:
        name = assessment if isinstance(assessment, str) else assessment.name
        org = organization or (assessment.get("organization") if not isinstance(assessment, str) else frappe.db.get_value("GRC Assessment", name, "organization"))
        user = None if system else (user or frappe.session.user)
        frappe.get_doc({
            "doctype": "GRC Activity Log", "assessment": name, "organization": org, "event_type": event_type,
            "actor": user, "actor_type": "System" if system else actor_type(user), "question_code": question_code or "",
            "detail": (detail or "")[:1000], "visible_to_customer": 1 if visible else 0,
        }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(title="GRC activity log failed", message=frappe.get_traceback())


def customer_view(assessment):
    """Timeline for the customer: staff actors are shown only as 'GRC team'; staff-only entries are excluded."""
    rows = frappe.get_all(
        "GRC Activity Log", filters={"assessment": assessment, "visible_to_customer": 1},
        fields=["event_type", "actor", "actor_type", "question_code", "detail", "creation"], order_by="creation desc", limit_page_length=300)
    out = []
    for r in rows:
        who = "GRC team" if r.actor_type == "Staff" else ("System" if r.actor_type == "System" else frappe.utils.get_fullname(r.actor))
        out.append({"event_type": r.event_type, "by": who, "by_type": r.actor_type, "question_code": r.question_code, "detail": r.detail, "at": r.creation})
    return out
