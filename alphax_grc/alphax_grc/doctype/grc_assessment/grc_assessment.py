import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, today

from alphax_grc.grc import access, activity, notify, scoring, workflow


class GRCAssessment(Document):
    def before_insert(self):
        tv = frappe.get_doc("GRC Template Version", self.template_version)
        if tv.status != "Published":
            frappe.throw(_("Assessments can only be created from a Published template version."))
        snap = tv.get_snapshot()
        self.template_snapshot = json.dumps(snap, ensure_ascii=False)
        self.template_title = snap["template_name"]
        self.question_count = len(snap["questions"])
        self.status = "Draft"
        have = {r.question_code for r in self.get("answers")}
        for q in snap["questions"]:
            if q["question_code"] not in have:
                self.append("answers", {"question_code": q["question_code"], "section_code": q["section_code"]})

    def after_insert(self):
        activity.log(self, "Status", "Assessment created" + (" by the GRC team" if access.is_staff() else ""))

    def validate(self):
        if not self.is_new():
            if self.has_value_changed("status") and not self.flags.transition_ok:
                frappe.throw(_("Status can only change through the assessment actions."))
            if self.has_value_changed("template_snapshot") and not self.flags.allow_snapshot_change:
                frappe.throw(_("The scoring snapshot is frozen and cannot be changed."))
            if self.has_value_changed("template_version"):
                frappe.throw(_("The template version cannot be changed after creation."))
            before = self.get_doc_before_save()
            if before and before.status == "Report Released" and not self.flags.transition_ok and not self.flags.allow_released_edit:
                frappe.throw(_("A released assessment is read only."))
        self.validate_team()
        self.validate_due_date()
        self.score_answers()
        self.collect_audit()

    def collect_audit(self):
        """Remember reviewer-side changes so on_update can write them to the activity trail (staff-only entries)."""
        self.flags.audit = []
        before = self.get_doc_before_save()
        if not before:
            return
        old = {r.question_code: (r.reviewer_option or "") for r in before.answers}
        for r in self.answers:
            if (r.reviewer_option or "") != old.get(r.question_code, ""):
                self.flags.audit.append(("Answer", "Reviewer adjusted %s: %s \u2192 %s" % (r.question_code, old.get(r.question_code) or "-", r.reviewer_option or "-"), r.question_code, 0))
        for f, label in (("assigned_consultant", "Consultant"), ("reviewer", "Reviewer"), ("due_date", "Due date")):
            if str(before.get(f) or "") != str(self.get(f) or ""):
                self.flags.audit.append(("Assignment", "%s: %s \u2192 %s" % (label, before.get(f) or "-", self.get(f) or "-"), "", 0))

    def on_update(self):
        for ev, detail, code, visible in (self.flags.get("audit") or []):
            activity.log(self, ev, detail, question_code=code, visible=visible)
        self.flags.audit = []

    def validate_team(self):
        for f in ("assigned_consultant", "reviewer"):
            u = self.get(f)
            if u and not (set(frappe.get_roles(u)) & access.STAFF_ROLES):
                frappe.throw(_("{0} must be a GRC team member.").format(self.meta.get_label(f)))

    def validate_due_date(self):
        if self.due_date and self.is_new() and getdate(self.due_date) < getdate(today()):
            frappe.throw(_("The due date cannot be in the past."))

    def score_answers(self):
        if not self.template_snapshot:
            return
        snap = workflow.snapshot_of(self)
        qmap = {q["question_code"]: q for q in snap["questions"]}
        pts = scoring.points_map(snap)
        for r in self.answers:
            q = qmap.get(r.question_code)
            if not q:
                frappe.throw(_("Unknown question {0}.").format(r.question_code))
            r.section_code = q["section_code"]
            for f in ("selected_option", "reviewer_option"):
                v = (r.get(f) or "").strip()
                if v and not scoring.is_valid_option(q, v, snap):
                    frappe.throw(_("Option {0} is not allowed for question {1}.").format(v, r.question_code))
            eff = scoring.normalise_answer(q, scoring.effective_option(r.selected_option, r.reviewer_option), snap)
            r.points = pts.get(eff, 0) if eff in pts else 0
        res = scoring.compute(snap, workflow.effective_answers(self))
        self.overall_score = res["overall_score"]
        self.maturity_level = res["maturity_level"]
        self.gating_note = res["gating_note"]
        self.answered_count = res["answered_count"]
        self.question_count = res["question_count"]
        self.result_type = "Approved" if self.status == "Report Released" else "Preliminary"

    def on_trash(self):
        if self.status not in ("Draft", "In Progress") and not access.is_manager():
            frappe.throw(_("Only a GRC Manager can delete a submitted assessment."))


# ---------------------------------------------------------------- staff actions (Desk buttons)
def _get(name):
    doc = frappe.get_doc("GRC Assessment", name)
    doc.check_permission("write")
    return doc


@frappe.whitelist()
def staff_action(name, action, note=None, requests=None):
    """action: start_review | request_clarification | approve | reopen | release"""
    user = frappe.session.user
    if not access.is_staff(user):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    doc = _get(name)
    full_name = frappe.utils.get_fullname(user)
    if action == "start_review":
        workflow.start_review(doc, user)
    elif action == "request_clarification":
        reqs = json.loads(requests) if isinstance(requests, str) and requests else (requests or [])
        if not reqs and note:
            reqs = [{"question_code": "", "message": note}]
        workflow.request_clarification(doc, user, full_name, reqs)
    elif action == "approve":
        workflow.approve(doc, user)
    elif action == "reopen":
        workflow.reopen(doc, user)
    elif action == "release":
        workflow.release(doc, user)
    elif action == "submit_on_behalf":
        workflow.submit_assessment(doc, user)
    else:
        frappe.throw(_("Unknown action {0}.").format(action))
    return doc.status


@frappe.whitelist()
def save_answers_for(name, items):
    """GRC team enters answers on the customer's behalf (marked as such in the trail and on the answer rows)."""
    if not access.is_staff():
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    doc = _get(name)
    items = json.loads(items) if isinstance(items, str) else (items or [])
    return workflow.apply_answers(doc, items, frappe.session.user, by_staff=True)


@frappe.whitelist()
def transfer(name, reason, assigned_consultant=None, reviewer=None):
    """Hand an assessment to another team member. A Manager, or the current consultant or reviewer, may do it; a reason is required."""
    user = frappe.session.user
    doc = frappe.get_doc("GRC Assessment", name)
    if not (access.is_manager(user) or user in (doc.assigned_consultant, doc.reviewer)):
        frappe.throw(_("Only a GRC Manager or the current assignee can transfer this assessment."), frappe.PermissionError)
    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("Write the reason for the transfer."))
    if not (assigned_consultant or reviewer):
        frappe.throw(_("Choose who should take over."))
    before = (doc.assigned_consultant, doc.reviewer)
    if assigned_consultant:
        doc.assigned_consultant = assigned_consultant
    if reviewer:
        doc.reviewer = reviewer
    doc.save(ignore_permissions=True)
    activity.log(doc, "Assignment", "Transferred: %s" % reason, visible=0)
    org = frappe.db.get_value("GRC Organization", doc.organization, "legal_name")
    url = frappe.utils.get_url_to_form("GRC Assessment", doc.name)
    new = [u for u in (assigned_consultant, reviewer) if u and u not in before]
    notify.send(new, "Assessment transferred to you: %s" % doc.name,
                "%s transferred <b>%s</b> (%s) to you.<br>Reason: %s<br><a href='%s'>Open</a>" % (
                    frappe.utils.escape_html(frappe.utils.get_fullname(user)), doc.name, frappe.utils.escape_html(org), frappe.utils.escape_html(reason), url), "en", "")
    return doc.name


@frappe.whitelist()
def assign(name, assigned_consultant=None, reviewer=None, due_date=None):
    if not access.is_manager():
        frappe.throw(_("Only a GRC Manager can assign assessments."), frappe.PermissionError)
    doc = frappe.get_doc("GRC Assessment", name)
    doc.assigned_consultant = assigned_consultant or None
    doc.reviewer = reviewer or None
    if due_date:
        doc.due_date = due_date
    doc.flags.allow_released_edit = False
    doc.save()
    return doc.name


@frappe.whitelist()
def create_for_organization(organization, template_version=None, due_date=None, assigned_consultant=None, reviewer=None):
    """GRC team assigns a survey to a customer organization."""
    if not access.is_staff():
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    if not template_version:
        tpl = frappe.db.get_single_value("GRC Settings", "default_template")
        template_version = tpl and frappe.db.get_value("GRC Assessment Template", tpl, "latest_published_version")
    if not template_version:
        frappe.throw(_("Choose a published template version."))
    doc = frappe.get_doc({
        "doctype": "GRC Assessment", "organization": organization, "template_version": template_version,
        "due_date": due_date or None, "assigned_consultant": assigned_consultant or None, "reviewer": reviewer or None,
    })
    doc.insert()
    return doc.name


@frappe.whitelist()
def get_review_summary(name):
    """Data for the Desk review panel: answers with wording, evidence and clarification threads."""
    if not access.is_staff():
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    doc = frappe.get_doc("GRC Assessment", name)
    doc.check_permission("read")
    snap = workflow.snapshot_of(doc)
    q = {x["question_code"]: x for x in snap["questions"]}
    files = frappe.get_all("File", filters={"attached_to_doctype": "GRC Assessment", "attached_to_name": name},
                           fields=["name", "file_name", "grc_question_code", "file_url", "file_size"])
    by_q = {}
    for f in files:
        by_q.setdefault(f.grc_question_code, []).append(f)
    out = []
    for r in doc.answers:
        d = q.get(r.question_code, {})
        out.append({
            "question_code": r.question_code, "short_label": d.get("short_label"), "question_text": d.get("question_text"),
            "options": {L: d.get("option_%s" % L.lower()) for L in "ABCD"},
            "selected_option": r.selected_option, "reviewer_option": r.reviewer_option, "comment": r.comment,
            "reviewer_note": r.reviewer_note, "evidence": by_q.get(r.question_code, []),
        })
    clar = frappe.get_all("GRC Clarification", filters={"assessment": name}, fields=["name", "question_code", "kind", "author_name", "author_type", "status", "message", "creation"], order_by="creation asc")
    trail = frappe.get_all("GRC Activity Log", filters={"assessment": name}, fields=["event_type", "actor", "actor_type", "question_code", "detail", "visible_to_customer", "creation"], order_by="creation desc", limit_page_length=200)
    return {"answers": out, "clarifications": clar, "status": doc.status, "activity": trail}
