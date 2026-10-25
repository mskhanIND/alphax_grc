"""Customer portal API. Customers have no DocType permissions: every endpoint resolves the caller's organization
membership first and only touches records of that organization. Missing and foreign records give the same error.
"""
import json
import os

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, escape_html

from alphax_grc.api import auth
from alphax_grc.grc import access, notify, scoring, workflow

EDIT = access.ORG_EDIT_ROLES


def _me():
    if frappe.session.user == "Guest":
        frappe.throw(_("Please sign in."), frappe.PermissionError)
    return frappe.session.user


def _member():
    return access.require_membership(_me())


def _need_edit(m):
    if m.member_role not in EDIT:
        frappe.throw(_("Your role does not allow this action."), frappe.PermissionError)


def _need_admin(m):
    if m.member_role != "Org Admin":
        frappe.throw(_("Only an Org Admin can do this."), frappe.PermissionError)


def _assessment(name, m):
    """Load an assessment of the caller's organization or fail with the generic not-found."""
    if not name or not frappe.db.exists("GRC Assessment", {"name": name, "organization": m.organization}):
        access.not_found()
    return frappe.get_doc("GRC Assessment", name)


def _jl(v):
    return json.loads(v) if isinstance(v, str) and v else (v or [])


# ------------------------------------------------------------------ context
@frappe.whitelist(allow_guest=True)
def get_context():
    user = frappe.session.user
    if user == "Guest":
        return None
    m = access.get_membership(user)
    out = {"user": user, "full_name": frappe.utils.get_fullname(user), "language": notify.user_language(user),
           "is_staff": access.is_staff(user), "membership": None}
    if m:
        org = frappe.db.get_value("GRC Organization", m.organization, ["name", "legal_name", "legal_name_ar"], as_dict=True)
        out["membership"] = {"role": m.member_role, "organization": org, "can_edit": m.member_role in EDIT, "is_admin": m.member_role == "Org Admin"}
    return out


@frappe.whitelist()
def set_language(language):
    frappe.db.set_value("User", _me(), "language", auth.clean_lang(language))
    return {"language": auth.clean_lang(language)}


@frappe.whitelist()
def accept_invitation(token):
    user = _me()
    inv = auth.find_invitation(token)
    if not inv or inv.email.strip().lower() != user.lower():
        frappe.throw(_("This invitation is invalid or has expired."))
    auth.accept_invitation_for(user, inv)
    return get_context()


@frappe.whitelist()
def create_organization(organization):
    user = _me()
    if access.get_membership(user) or frappe.db.exists("GRC Organization Member", {"user": user}):
        frappe.throw(_("This account already belongs to an organization."))
    v = auth.clean_org_values(organization or {})
    if not v.get("legal_name"):
        frappe.throw(_("Enter your organization's legal name."))
    org = frappe.get_doc(dict(doctype="GRC Organization", status="Active", created_by_user=user,
                              preferred_language=notify.user_language(user), **v))
    org.insert(ignore_permissions=True)
    frappe.get_doc({"doctype": "GRC Organization Member", "user": user, "organization": org.name, "member_role": "Org Admin", "status": "Active"}).insert(ignore_permissions=True)
    return get_context()


# ------------------------------------------------------------------ organization & members
@frappe.whitelist()
def get_organization():
    m = _member()
    d = frappe.get_doc("GRC Organization", m.organization)
    return {k: d.get(k) for k in auth.ORG_FIELDS + ("name", "country", "status")}


@frappe.whitelist()
def update_organization(organization):
    m = _member()
    _need_admin(m)
    v = auth.clean_org_values(_jl(organization) if isinstance(organization, str) else organization)
    if not v.get("legal_name"):
        frappe.throw(_("Enter your organization's legal name."))
    d = frappe.get_doc("GRC Organization", m.organization)
    d.update(v)
    d.save(ignore_permissions=True)
    return get_organization()


@frappe.whitelist()
def list_members():
    m = _member()
    members = frappe.get_all("GRC Organization Member", filters={"organization": m.organization}, fields=["name", "user", "full_name", "member_role", "status"], order_by="creation asc")
    invites = frappe.get_all("GRC Invitation", filters={"organization": m.organization, "status": "Pending"}, fields=["name", "email", "member_role", "expires_on"], order_by="creation desc")
    return {"members": members, "invitations": invites, "can_manage": m.member_role == "Org Admin"}


@frappe.whitelist()
@rate_limit(limit=30, seconds=3600)
def invite_member(email, role):
    m = _member()
    _need_admin(m)
    email = auth.clean_email(email)
    if role not in access.ORG_ROLES:
        frappe.throw(_("Choose a valid role."))
    if frappe.db.exists("GRC Organization Member", {"user": email}):
        frappe.throw(_("This person already belongs to an organization."))
    for n in frappe.get_all("GRC Invitation", filters={"organization": m.organization, "email": email, "status": "Pending"}, pluck="name"):
        frappe.db.set_value("GRC Invitation", n, "status", "Revoked")
    inv, token, link = auth.create_invitation(m.organization, email, role, frappe.session.user)
    org = frappe.db.get_value("GRC Organization", m.organization, "legal_name")
    lang = notify.user_language(frappe.session.user)
    sent = notify.send(email, notify.tr("invite_subject", lang, org=org, platform=notify.platform_name()),
                       notify.tr("invite_body", lang, inviter=escape_html(frappe.utils.get_fullname(frappe.session.user)), org=escape_html(org),
                                 platform=notify.platform_name(), role=role, days=auth.INVITE_DAYS, url=link), lang, "")
    # the link is returned to the admin so the invitation still works when outgoing email is not configured
    return {"invitation": inv.name, "email_sent": bool(sent), "link": link}


@frappe.whitelist()
def revoke_invitation(name):
    m = _member()
    _need_admin(m)
    if not frappe.db.exists("GRC Invitation", {"name": name, "organization": m.organization}):
        access.not_found()
    frappe.db.set_value("GRC Invitation", name, "status", "Revoked")
    return True


def _admin_count(org):
    return frappe.db.count("GRC Organization Member", {"organization": org, "status": "Active", "member_role": "Org Admin"})


@frappe.whitelist()
def change_member_role(name, role):
    m = _member()
    _need_admin(m)
    if role not in access.ORG_ROLES:
        frappe.throw(_("Choose a valid role."))
    row = frappe.db.get_value("GRC Organization Member", {"name": name, "organization": m.organization}, ["name", "member_role"], as_dict=True)
    if not row:
        access.not_found()
    if row.member_role == "Org Admin" and role != "Org Admin" and _admin_count(m.organization) <= 1:
        frappe.throw(_("An organization needs at least one Org Admin."))
    frappe.db.set_value("GRC Organization Member", name, "member_role", role)
    return True


@frappe.whitelist()
def remove_member(name):
    m = _member()
    _need_admin(m)
    row = frappe.db.get_value("GRC Organization Member", {"name": name, "organization": m.organization}, ["name", "member_role", "user"], as_dict=True)
    if not row:
        access.not_found()
    if row.member_role == "Org Admin" and _admin_count(m.organization) <= 1:
        frappe.throw(_("An organization needs at least one Org Admin."))
    frappe.db.set_value("GRC Organization Member", name, "status", "Removed")
    return True


# ------------------------------------------------------------------ assessments
def _summary(a, m):
    return {
        "name": a.name, "title": a.template_title, "status": a.status, "due_date": a.due_date, "answered": a.answered_count, "total": a.question_count,
        "next_action": workflow.NEXT_ACTION.get(a.status), "editable": a.status in workflow.CUSTOMER_EDITABLE and m.member_role in EDIT,
        "released": a.status == "Report Released", "submitted_on": a.submitted_on,
        "preliminary_level": a.preliminary_level if a.status in ("Submitted", "Under Review", "Clarification Required", "Resubmitted", "Approved") else None,
    }


@frappe.whitelist()
def list_assessments():
    m = _member()
    rows = frappe.get_all("GRC Assessment", filters={"organization": m.organization}, fields=[
        "name", "template_title", "status", "due_date", "answered_count", "question_count", "submitted_on", "preliminary_level"], order_by="creation desc")
    return [_summary(frappe._dict(name=r.name, template_title=r.template_title, status=r.status, due_date=r.due_date, answered_count=r.answered_count,
                                  question_count=r.question_count, submitted_on=r.submitted_on, preliminary_level=r.preliminary_level), m) for r in rows]


@frappe.whitelist()
def start_assessment():
    m = _member()
    _need_edit(m)
    open_n = frappe.db.count("GRC Assessment", {"organization": m.organization, "status": ["in", ["Draft", "In Progress"]]})
    if open_n:
        frappe.throw(_("You already have an assessment in progress. Finish or submit it first."))
    tpl = frappe.db.get_single_value("GRC Settings", "default_template")
    tv = tpl and frappe.db.get_value("GRC Assessment Template", tpl, "latest_published_version")
    if not tv:
        frappe.throw(_("No assessment is available right now."))
    doc = frappe.get_doc({"doctype": "GRC Assessment", "organization": m.organization, "template_version": tv,
                          "respondent": frappe.session.user, "respondent_name": frappe.utils.get_fullname(frappe.session.user)})
    doc.insert(ignore_permissions=True)
    return doc.name


def _public_snapshot(snap):
    """Questionnaire as the customer sees it. Scoring internals (points, gating, bands, weights) are left out."""
    qkeys = ("question_code", "section_code", "short_label", "short_label_ar", "question_text", "question_text_ar",
             "option_a", "option_b", "option_c", "option_d", "option_a_ar", "option_b_ar", "option_c_ar", "option_d_ar", "allow_na")
    skeys = ("section_code", "title", "title_ar", "reference", "reference_ar", "owner_role", "owner_role_ar")
    return {
        "template_name": snap.get("template_name"), "template_name_ar": snap.get("template_name_ar"),
        "introduction": snap.get("introduction"), "introduction_ar": snap.get("introduction_ar"),
        "answer_rule": snap.get("answer_rule"), "answer_rule_ar": snap.get("answer_rule_ar"),
        "sections": [{k: x.get(k) for k in skeys} for x in snap["sections"]],
        "questions": [{k: x.get(k) for k in qkeys} for x in snap["questions"]],
        "allow_na": bool(snap.get("allow_na")),
    }


def _evidence(name, m=None):
    rows = frappe.get_all("File", filters={"attached_to_doctype": "GRC Assessment", "attached_to_name": name, "is_private": 1},
                          fields=["name", "file_name", "file_size", "grc_question_code", "creation"], order_by="creation asc")
    return [{"id": r.name, "file_name": r.file_name, "size": r.file_size, "question_code": r.grc_question_code, "uploaded_on": r.creation} for r in rows]


@frappe.whitelist()
def get_assessment(name):
    m = _member()
    a = _assessment(name, m)
    snap = workflow.snapshot_of(a)
    clar = frappe.get_all("GRC Clarification", filters={"assessment": a.name}, fields=["name", "question_code", "kind", "author_name", "author_type", "status", "message", "creation"], order_by="creation asc")
    return {
        **_summary(a, m), "organization": a.organization, "snapshot": _public_snapshot(snap),
        "answers": {r.question_code: {"selected_option": r.selected_option, "comment": r.comment} for r in a.answers},
        "evidence": _evidence(a.name), "clarifications": clar, "can_edit": m.member_role in EDIT,
        "max_evidence_mb": cint(frappe.db.get_single_value("GRC Settings", "max_evidence_mb")) or 10,
    }


@frappe.whitelist()
def save_answers(name, items):
    m = _member()
    _need_edit(m)
    a = _assessment(name, m)
    n = workflow.apply_answers(a, _jl(items), frappe.session.user)
    a.reload()
    return {"changed": n, "status": a.status, "answered": a.answered_count, "total": a.question_count}


@frappe.whitelist()
def submit_assessment(name):
    m = _member()
    _need_edit(m)
    a = _assessment(name, m)
    workflow.submit_assessment(a, frappe.session.user)
    return {"status": a.status}


@frappe.whitelist()
def add_clarification_reply(name, question_code, message):
    m = _member()
    _need_edit(m)
    a = _assessment(name, m)
    workflow.add_reply(a, frappe.session.user, frappe.utils.get_fullname(frappe.session.user), question_code, message)
    return True


@frappe.whitelist()
def resubmit_assessment(name):
    m = _member()
    _need_edit(m)
    a = _assessment(name, m)
    workflow.resubmit_assessment(a, frappe.session.user)
    return {"status": a.status}


# ------------------------------------------------------------------ evidence
def _allowed_ext():
    s = frappe.db.get_single_value("GRC Settings", "allowed_evidence_extensions") or "pdf,docx,xlsx,pptx,png,jpg,jpeg,csv,txt"
    return {x.strip().lower().lstrip(".") for x in s.replace("\n", ",").split(",") if x.strip()}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=120, seconds=3600)
def upload_evidence(name, question_code=""):
    m = _member()
    _need_edit(m)
    a = _assessment(name, m)
    if a.status not in workflow.CUSTOMER_EDITABLE:
        frappe.throw(_("Evidence can no longer be changed."))
    code = (question_code or "").strip()
    if code and code not in {q["question_code"] for q in workflow.snapshot_of(a)["questions"]}:
        frappe.throw(_("Unknown question {0}.").format(code))
    f = frappe.request.files.get("file") if frappe.request else None
    if not f:
        frappe.throw(_("Choose a file."))
    fname = os.path.basename(f.filename or "").replace("\x00", "")[:120]
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    if ext not in _allowed_ext():
        frappe.throw(_("This file type is not allowed."))
    content = f.read()
    limit = (cint(frappe.db.get_single_value("GRC Settings", "max_evidence_mb")) or 10) * 1024 * 1024
    if len(content) > limit:
        frappe.throw(_("The file is larger than {0} MB.").format(limit // 1048576))
    if not content:
        frappe.throw(_("The file is empty."))
    if frappe.db.count("File", {"attached_to_doctype": "GRC Assessment", "attached_to_name": a.name}) >= 100:
        frappe.throw(_("Too many files attached."))
    doc = frappe.get_doc({"doctype": "File", "file_name": fname, "attached_to_doctype": "GRC Assessment", "attached_to_name": a.name,
                          "is_private": 1, "content": content, "grc_question_code": code})
    doc.flags.ignore_permissions = True
    try:
        doc.insert()
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(title="GRC evidence upload failed")
        frappe.throw(_("The file could not be read. Check that it is not damaged and try again."))
    return {"id": doc.name, "file_name": doc.file_name, "size": doc.file_size, "question_code": code}


def _own_file(file_id, m):
    row = frappe.db.get_value("File", {"name": file_id, "attached_to_doctype": "GRC Assessment"}, ["name", "attached_to_name"], as_dict=True)
    if not row or not frappe.db.exists("GRC Assessment", {"name": row.attached_to_name, "organization": m.organization}):
        access.not_found()
    return frappe.get_doc("File", row.name), frappe.get_doc("GRC Assessment", row.attached_to_name)


@frappe.whitelist(methods=["POST"])
def delete_evidence(file_id):
    m = _member()
    _need_edit(m)
    f, a = _own_file(file_id, m)
    if a.status not in workflow.CUSTOMER_EDITABLE:
        frappe.throw(_("Evidence can no longer be changed."))
    frappe.delete_doc("File", f.name, ignore_permissions=True)
    return True


@frappe.whitelist()
def download_evidence(file_id):
    m = _member()
    f, a = _own_file(file_id, m)
    frappe.local.response.filename = f.file_name
    frappe.local.response.filecontent = f.get_content()
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "attachment"


# ------------------------------------------------------------------ results
def _result_for(a):
    """Approved result only after release; the customer never receives preliminary reviewer-adjusted data early."""
    if a.status != "Report Released":
        return None
    return json.loads(a.final_result or "null")


@frappe.whitelist()
def get_scorecard(name):
    m = _member()
    a = _assessment(name, m)
    snap = workflow.snapshot_of(a)
    out = {"name": a.name, "status": a.status, "title": a.template_title, "released": a.status == "Report Released", "preliminary": None, "final": None}
    if a.preliminary_result and a.status in ("Submitted", "Under Review", "Clarification Required", "Resubmitted", "Approved", "Report Released"):
        p = json.loads(a.preliminary_result)
        out["preliminary"] = {"overall_score": p["overall_score"], "maturity_level": p["maturity_level"], "maturity_level_ar": p.get("maturity_level_ar"),
                              "note": "Preliminary: pending review by the GRC team."}
    out["final"] = _result_for(a)
    if out["final"]:
        out["reports"] = [{"kind": r.report_type, "language": r.language, "version": r.version}
                          for r in frappe.get_all("GRC Report", filters={"assessment": a.name, "report_type": "Approved"}, fields=["report_type", "language", "version"])]
    labels = {q["question_code"]: {"short_label": q["short_label"], "short_label_ar": q.get("short_label_ar")} for q in snap["questions"]}
    out["labels"] = labels
    return out


@frappe.whitelist()
def download_report(name, lang="en"):
    m = _member()
    a = _assessment(name, m)
    if a.status != "Report Released":
        access.not_found()
    lang = auth.clean_lang(lang)
    rep = frappe.db.get_value("GRC Report", {"assessment": a.name, "report_type": "Approved", "language": lang}, "name", order_by="version desc")
    if not rep:
        access.not_found()
    furl = frappe.db.get_value("GRC Report", rep, "file")
    f = frappe.get_doc("File", {"file_url": furl})
    frappe.local.response.filename = "%s-%s.pdf" % (a.name, lang)
    frappe.local.response.filecontent = f.get_content()
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "attachment"


@frappe.whitelist()
def dashboard():
    m = _member()
    rows = list_assessments()
    latest_released = next((r for r in rows if r["released"]), None)
    return {"assessments": rows, "latest_released": latest_released,
            "open": next((r for r in rows if r["status"] in ("Draft", "In Progress", "Clarification Required")), None)}
