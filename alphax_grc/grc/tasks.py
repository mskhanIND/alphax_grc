"""Daily scheduler job. Every send is logged in GRC Follow Up Log so reminders are auditable. Never raises for one bad record."""
import frappe
from frappe.utils import add_days, cint, date_diff, getdate, now_datetime, today

from alphax_grc.grc import notify, workflow

OPEN_FOR_CUSTOMER = ("Draft", "In Progress", "Clarification Required")


def _s():
    return frappe.get_cached_doc("GRC Settings")


def _log(a, note, kind="System Reminder"):
    frappe.get_doc({"doctype": "GRC Follow Up Log", "assessment": a.name, "organization": a.organization, "contact_type": kind,
                    "followup_on": now_datetime(), "note": note, "logged_by": "Administrator"}).insert(ignore_permissions=True)


def _remind(a, message_key, message=None, **kw):
    recipients, lang, name = workflow._audience(a)
    title = workflow.title_of(a)
    body = message or notify.tr(message_key, lang, title=frappe.utils.escape_html(title), **kw)
    ok = notify.send(recipients, notify.tr("reminder_subject", lang, title=title),
                     notify.tr("reminder_body", lang, message=body, url=notify.portal_url("#/assessments/" + a.name)), lang, name, ("GRC Assessment", a.name))
    _log(a, "%s (%s)" % (message_key, "email queued" if ok else "email not sent"))
    return ok


def _already(a, key):
    return frappe.db.exists("GRC Follow Up Log", {"assessment": a.name, "contact_type": "System Reminder", "note": ["like", key + "%"],
                                                   "followup_on": [">=", today()]})


def send_manual_reminders():
    for r in frappe.get_all("GRC Reminder", filters={"status": "Scheduled", "remind_on": ["<=", today()]}, fields=["name", "assessment", "message"]):
        try:
            a = frappe.get_doc("GRC Assessment", r.assessment)
            if a.status in ("Approved", "Report Released"):
                frappe.db.set_value("GRC Reminder", r.name, "status", "Cancelled")
                continue
            _remind(a, "manual_reminder", message=frappe.utils.escape_html(r.message or "") or None) if r.message else _remind(a, "reminder_default_before", due=a.due_date, days=0)
            frappe.db.set_value("GRC Reminder", r.name, {"status": "Sent", "sent_on": now_datetime()})
        except Exception:
            frappe.log_error(title="GRC reminder failed: %s" % r.name)


def send_due_reminders():
    s = _s()
    days = sorted({cint(x) for x in (s.reminder_days_before_due or "7,3,1").replace(";", ",").split(",") if x.strip().isdigit()}, reverse=True)
    every = max(1, cint(s.overdue_reminder_every_days) or 7)
    for a in frappe.get_all("GRC Assessment", filters={"status": ["in", list(OPEN_FOR_CUSTOMER)], "due_date": ["is", "set"]}, pluck="name"):
        try:
            a = frappe.get_doc("GRC Assessment", a)
            left = date_diff(getdate(a.due_date), getdate(today()))
            if left in days and not _already(a, "reminder_default_before"):
                _remind(a, "reminder_default_before", due=a.due_date, days=left)
            elif left < 0 and (-left) % every == 0 and not _already(a, "reminder_default_overdue"):
                _remind(a, "reminder_default_overdue", due=a.due_date)
        except Exception:
            frappe.log_error(title="GRC due reminder failed: %s" % a)


def clarification_sla():
    sla = cint(_s().clarification_sla_days) or 5
    cutoff = add_days(today(), -sla)
    for a in frappe.get_all("GRC Assessment", filters={"status": "Clarification Required", "modified": ["<=", cutoff]}, pluck="name"):
        try:
            a = frappe.get_doc("GRC Assessment", a)
            if not _already(a, "reminder_default_sla"):
                _remind(a, "reminder_default_sla")
        except Exception:
            frappe.log_error(title="GRC clarification SLA failed: %s" % a)


def review_sla_digest():
    sla = cint(_s().review_sla_days) or 5
    cutoff = add_days(today(), -sla)
    rows = frappe.get_all("GRC Assessment", filters={"status": ["in", ["Submitted", "Resubmitted", "Under Review"]], "modified": ["<=", cutoff]},
                          fields=["name", "organization", "status", "modified"])
    to = notify.staff_notification_recipients()
    if rows and to:
        lines = "<br>".join("%s - %s (%s)" % (frappe.utils.escape_html(r.name), frappe.utils.escape_html(r.organization), r.status) for r in rows)
        notify.send(to, "GRC assessments waiting for review longer than %s days" % sla, lines, "en")


def daily():
    if not cint(_s().reminders_enabled):
        return
    for fn in (send_manual_reminders, send_due_reminders, clarification_sla, review_sla_digest):
        try:
            fn()
        except Exception:
            frappe.log_error(title="GRC daily task %s failed" % fn.__name__)
