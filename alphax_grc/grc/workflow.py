"""Assessment state machine.

Draft -> In Progress -> Submitted -> Under Review -> Clarification Required -> Resubmitted -> Under Review
      -> Approved -> Report Released

Implemented in code (not the Frappe Workflow doctype) because customers move the assessment through the API
and staff through Desk buttons. Every status change must go through `transition()`.
"""
import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from alphax_grc.grc import access, activity, notify, scoring

STATES = ["Draft", "In Progress", "Submitted", "Under Review", "Clarification Required", "Resubmitted", "Approved", "Report Released"]

TRANSITIONS = {
    ("Draft", "In Progress"),
    ("In Progress", "Submitted"),
    ("Submitted", "Under Review"),
    ("Under Review", "Clarification Required"),
    ("Submitted", "Clarification Required"),
    ("Resubmitted", "Clarification Required"),
    ("Clarification Required", "Resubmitted"),
    ("Resubmitted", "Under Review"),
    ("Under Review", "Approved"),
    ("Approved", "Under Review"),
    ("Approved", "Report Released"),
}

CUSTOMER_EDITABLE = ("Draft", "In Progress", "Clarification Required")

# What the customer should do next, per status. The portal translates the codes.
NEXT_ACTION = {
    "Draft": "start_answering",
    "In Progress": "complete_and_submit",
    "Submitted": "wait_for_review",
    "Under Review": "wait_for_review",
    "Clarification Required": "reply_and_resubmit",
    "Resubmitted": "wait_for_review",
    "Approved": "wait_for_release",
    "Report Released": "view_report",
}


def snapshot_of(doc):
    return json.loads(doc.template_snapshot or "{}")


def selected_answers(doc):
    return {r.question_code: (r.selected_option or "") for r in doc.answers}


def effective_answers(doc):
    return {r.question_code: scoring.effective_option(r.selected_option, r.reviewer_option) for r in doc.answers}


def transition(doc, to_status, note=None, **fields):
    frm = doc.status
    if (frm, to_status) not in TRANSITIONS:
        frappe.throw(_("An assessment cannot move from {0} to {1}.").format(frm, to_status))
    doc.flags.transition_ok = True
    doc.status = to_status
    for k, v in fields.items():
        doc.set(k, v)
    doc.save(ignore_permissions=True)
    doc.add_comment("Info", _("Status changed from {0} to {1}.").format(frm, to_status) + ((" " + note) if note else ""))
    activity.log(doc, "Status", "%s \u2192 %s%s" % (frm, to_status, (": " + note) if note else ""))
    return doc


def title_of(doc):
    return "{} ({})".format(doc.template_title or doc.template_version, doc.name)


def _audience(doc, optional=False):
    """(recipients, lang, name) for the customer-side people of this assessment.
    optional=True applies the customer's notification switches (not used for clarification requests)."""
    emails = set(notify.org_admin_emails(doc.organization))
    if doc.respondent:
        emails.add(doc.respondent)
    if optional:
        emails = set(notify.optional_recipients(doc.organization, sorted(emails)))
    lang = notify.user_language(doc.respondent) if doc.respondent else "en"
    name = doc.respondent_name or ""
    return sorted(emails), lang, name


# ------------------------------------------------------------------ customer side
def apply_answers(doc, items, user, by_staff=False):
    """items: [{question_code, selected_option, comment}] from the portal or, with by_staff, from the GRC team on the
    customer's behalf. Returns number of rows changed."""
    if doc.status not in CUSTOMER_EDITABLE:
        frappe.throw(_("This assessment can no longer be edited."))
    snap = snapshot_of(doc)
    qmap = {q["question_code"]: q for q in snap["questions"]}
    rows = {r.question_code: r for r in doc.answers}
    changed = 0
    touched = []
    started = False
    for it in items or []:
        code = (it.get("question_code") or "").strip()
        if code not in qmap:
            frappe.throw(_("Unknown question {0}.").format(code))
        row = rows.get(code)
        if row is None:
            row = doc.append("answers", {"question_code": code, "section_code": qmap[code]["section_code"]})
            rows[code] = row
        if "selected_option" in it:
            opt = (it.get("selected_option") or "").strip()
            if opt and not scoring.is_valid_option(qmap[code], opt, snap):
                frappe.throw(_("Option {0} is not allowed for question {1}.").format(opt, code))
            if opt != (row.selected_option or ""):
                old = row.selected_option or ""
                row.selected_option = opt
                row.answered_on = now_datetime()
                row.answered_by = user
                row.answered_by_staff = 1 if by_staff else 0
                touched.append("%s: %s" % (code, ("%s \u2192 %s" % (old, opt)) if old else opt))
                changed += 1
        if "comment" in it:
            c = (it.get("comment") or "")[:2000]
            if c != (row.comment or ""):
                row.comment = c
                changed += 1
    if changed:
        if doc.status == "Draft":
            doc.flags.transition_ok = True
            doc.status = "In Progress"
            doc.started_on = doc.started_on or now_datetime()
            started = True
        doc.save(ignore_permissions=True)
        if started:
            activity.log(doc, "Status", "Draft \u2192 In Progress", user=user)
        if touched:
            activity.log(doc, "Answer", ("On behalf of the customer: " if by_staff else "") + "; ".join(touched[:25]), user=user)
    return changed


def _freeze_preliminary(doc):
    res = scoring.compute(snapshot_of(doc), selected_answers(doc))
    doc.preliminary_result = json.dumps(res, ensure_ascii=False)
    doc.preliminary_score = res["overall_score"]
    doc.preliminary_level = res["maturity_level"]
    return res


def _assert_complete(doc):
    snap = snapshot_of(doc)
    answers = selected_answers(doc)
    missing = [q["question_code"] for q in snap["questions"]
               if scoring.normalise_answer(q, answers.get(q["question_code"]), snap) == ""]
    if missing:
        frappe.throw(_("Please answer all questions before submitting. Missing: {0}").format(", ".join(missing)))


def submit_assessment(doc, user):
    if doc.status != "In Progress":
        frappe.throw(_("Only an assessment in progress can be submitted."))
    _assert_complete(doc)
    doc.flags.transition_ok = True  # fields below are set before transition() saves
    _freeze_preliminary(doc)
    transition(doc, "Submitted", submitted_on=now_datetime())
    recipients, lang, name = _audience(doc, optional=True)
    notify.send(recipients, notify.tr("submitted_subject", lang, title=title_of(doc)),
                notify.tr("submitted_body", lang, title=frappe.utils.escape_html(title_of(doc))), lang, name, ("GRC Assessment", doc.name))
    staff = list(notify.staff_notification_recipients())
    if doc.assigned_consultant:
        staff.append(doc.assigned_consultant)
    org = frappe.db.get_value("GRC Organization", doc.organization, "legal_name")
    url = frappe.utils.get_url_to_form("GRC Assessment", doc.name)
    notify.send(staff, notify.tr("staff_submitted_subject", "en", org=org, title=title_of(doc)),
                notify.tr("staff_submitted_body", "en", org=frappe.utils.escape_html(org), title=frappe.utils.escape_html(title_of(doc)), name=doc.name, url=url), "en")
    return doc


def add_reply(doc, user, user_name, question_code, message):
    if doc.status != "Clarification Required":
        frappe.throw(_("Replies can only be added while clarification is requested."))
    message = (message or "").strip()
    if not message:
        frappe.throw(_("Please write a reply."))
    code = (question_code or "").strip()
    snap = snapshot_of(doc)
    if code and code not in {q["question_code"] for q in snap["questions"]}:
        frappe.throw(_("Unknown question {0}.").format(code))
    reply = frappe.get_doc({
        "doctype": "GRC Clarification", "assessment": doc.name, "question_code": code, "kind": "Reply",
        "author": user, "author_name": user_name, "author_type": "Customer", "status": "Answered", "message": message[:5000],
    })
    reply.insert(ignore_permissions=True)
    activity.log(doc, "Clarification", "Reply" + ((" on " + code) if code else ""), user=user, question_code=code)
    for name in frappe.get_all("GRC Clarification", filters={"assessment": doc.name, "kind": "Request", "status": "Open", "question_code": code}, pluck="name"):
        frappe.db.set_value("GRC Clarification", name, "status", "Answered")
    return reply


def resubmit_assessment(doc, user):
    if doc.status != "Clarification Required":
        frappe.throw(_("Only an assessment awaiting clarification can be resubmitted."))
    open_reqs = frappe.get_all("GRC Clarification", filters={"assessment": doc.name, "kind": "Request", "status": "Open"}, pluck="question_code")
    if open_reqs:
        frappe.throw(_("Please reply to every clarification request first. Waiting: {0}").format(", ".join(c or _("general") for c in open_reqs)))
    _assert_complete(doc)
    _freeze_preliminary(doc)
    transition(doc, "Resubmitted", resubmit_count=(doc.resubmit_count or 0) + 1)
    return doc


# ------------------------------------------------------------------ staff side
def start_review(doc, user):
    if doc.status not in ("Submitted", "Resubmitted"):
        frappe.throw(_("Only submitted assessments can be taken into review."))
    updates = {"review_started_on": doc.review_started_on or now_datetime()}
    if not doc.assigned_consultant and "GRC Consultant" in frappe.get_roles(user):
        updates["assigned_consultant"] = user
    transition(doc, "Under Review", **updates)
    return doc


def request_clarification(doc, user, user_name, requests):
    """requests: [{question_code, message}]"""
    if doc.status not in ("Submitted", "Under Review", "Resubmitted"):
        frappe.throw(_("Clarification can only be requested on a submitted assessment that is not yet approved."))
    requests = [r for r in (requests or []) if (r.get("message") or "").strip()]
    if not requests:
        frappe.throw(_("Write at least one clarification request."))
    for r in requests:
        frappe.get_doc({
            "doctype": "GRC Clarification", "assessment": doc.name, "question_code": (r.get("question_code") or "").strip(),
            "kind": "Request", "author": user, "author_name": user_name, "author_type": "Staff", "status": "Open",
            "message": r["message"].strip()[:5000],
        }).insert(ignore_permissions=True)
    transition(doc, "Clarification Required")
    activity.log(doc, "Clarification", "%d clarification request(s) sent" % len(requests), user=user)
    recipients, lang, name = _audience(doc)
    note = "<br>".join(frappe.utils.escape_html(("%s: " % r["question_code"] if r.get("question_code") else "") + r["message"].strip()) for r in requests)
    notify.send(recipients, notify.tr("clarify_subject", lang, title=title_of(doc)),
                notify.tr("clarify_body", lang, title=frappe.utils.escape_html(title_of(doc)), note=note, url=notify.portal_url("#/assessments/" + doc.name)), lang, name, ("GRC Assessment", doc.name))
    return doc


def approve(doc, user):
    if doc.status != "Under Review":
        frappe.throw(_("Only an assessment under review can be approved."))
    if not access.is_reviewer(user):
        frappe.throw(_("Only a GRC Reviewer or GRC Manager can approve."), frappe.PermissionError)
    if frappe.db.exists("GRC Clarification", {"assessment": doc.name, "kind": "Request", "status": "Open"}):
        frappe.throw(_("There are open clarification requests. Resolve them or wait for the customer's reply before approving."))
    res = scoring.compute(snapshot_of(doc), effective_answers(doc))
    doc.final_result = json.dumps(res, ensure_ascii=False)
    doc.final_score = res["overall_score"]
    doc.final_level = res["maturity_level"]
    transition(doc, "Approved", approved_on=now_datetime(), approved_by=user)
    for name in frappe.get_all("GRC Clarification", filters={"assessment": doc.name, "status": "Answered"}, pluck="name"):
        frappe.db.set_value("GRC Clarification", name, "status", "Resolved")
    return doc


def reopen(doc, user):
    if doc.status != "Approved":
        frappe.throw(_("Only an approved (not yet released) assessment can be reopened."))
    if not access.is_manager(user):
        frappe.throw(_("Only a GRC Manager can reopen."), frappe.PermissionError)
    doc.final_result = None
    doc.final_score = None
    doc.final_level = None
    transition(doc, "Under Review", approved_on=None, approved_by=None)
    return doc


def release(doc, user):
    if doc.status != "Approved":
        frappe.throw(_("Only an approved assessment can be released."))
    if not access.is_manager(user):
        frappe.throw(_("Only a GRC Manager can release a report."), frappe.PermissionError)
    from alphax_grc.grc import reports
    reports.generate_approved_reports(doc, user)  # raises if PDF generation fails: no release without a report
    transition(doc, "Report Released", released_on=now_datetime(), released_by=user)
    activity.log(doc, "Report", "Approved report generated (English and Arabic) and released", user=user)
    recipients, lang, name = _audience(doc, optional=True)
    notify.send(recipients, notify.tr("released_subject", lang, title=title_of(doc)),
                notify.tr("released_body", lang, title=frappe.utils.escape_html(title_of(doc)), level=doc.final_level, score=doc.final_score,
                          url=notify.portal_url("#/assessments/" + doc.name + "/scorecard")), lang, name, ("GRC Assessment", doc.name))
    return doc
