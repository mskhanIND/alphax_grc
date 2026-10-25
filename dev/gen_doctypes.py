"""Generates DocType JSON + controller stubs for alphax_grc. Dev-time helper, not shipped."""
import json, os, re, datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "alphax_grc", "alphax_grc", "doctype"))
MODULE = "AlphaX GRC"
TS = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

def scrub(n): return n.replace(" ", "_").replace("-", "_").lower()
def cls(n): return n.replace(" ", "").replace("-", "")
def title(s): return s.replace("_", " ").title()

SECTORS = "Banking & Finance\nInsurance\nFintech\nListed Companies\nGovernment\nHealthcare\nEnergy & Utilities\nTelecommunications\nLogistics & Transport\nE-Commerce\nOther"

def F(fieldname, fieldtype="Data", label=None, **kw):
    d = {"fieldname": fieldname, "fieldtype": fieldtype}
    if fieldtype not in ("Section Break", "Column Break", "Tab Break") or label:
        d["label"] = label if label is not None else title(fieldname)
    d.update(kw)
    return d

def SB(name, label=None, **kw): return F(name, "Section Break", label or "", **kw)
def CB(name): return F(name, "Column Break", "")

ROLES = {"M": "GRC Manager", "C": "GRC Consultant", "R": "GRC Reviewer", "S": "System Manager"}
def P(role, flags):
    d = {"role": ROLES[role], "read": 0, "write": 0, "create": 0, "delete": 0, "report": 1, "export": 1, "share": 1, "print": 1, "email": 1}
    for ch, key in (("r", "read"), ("w", "write"), ("c", "create"), ("d", "delete")):
        if ch in flags: d[key] = 1
    return d

def doctype(name, fields, perms=None, **opts):
    folder = os.path.join(ROOT, scrub(name)); os.makedirs(folder, exist_ok=True)
    open(os.path.join(folder, "__init__.py"), "a").close()
    istable = opts.get("istable", 0)
    d = {
        "actions": [], "allow_rename": 0, "creation": TS, "doctype": "DocType", "engine": "InnoDB",
        "field_order": [f["fieldname"] for f in fields], "fields": fields,
        "index_web_pages_for_search": 0, "links": [], "modified": TS, "modified_by": "Administrator",
        "module": MODULE, "name": name, "owner": "Administrator",
        "permissions": [] if istable else (perms or []), "sort_field": "modified", "sort_order": "DESC", "states": [],
    }
    if not istable and not opts.get("issingle"): d["track_changes"] = 1
    d.update(opts)
    with open(os.path.join(folder, scrub(name) + ".json"), "w") as f:
        json.dump(d, f, indent=1, ensure_ascii=False); f.write("\n")
    py = os.path.join(folder, scrub(name) + ".py")
    if not os.path.exists(py):
        base = "Document"
        with open(py, "w") as f:
            f.write(f"import frappe\nfrom frappe.model.document import Document\n\n\nclass {cls(name)}(Document):\n    pass\n")
    print("generated", name)

STAFF_ALL = [P("S", "rwcd"), P("M", "rwcd")]

# ---------------------------------------------------------------- GRC Settings
doctype("GRC Settings", [
    SB("sb_site", "Platform"),
    F("platform_name", label="Platform name", default="AlphaX GRC & Audit Platform"),
    F("provider_name", label="Provider name", default="IRSAA Business Solutions"),
    F("public_site_url", label="Public site URL", description="Used in email links. Leave blank to use the site's own URL."),
    F("support_email", "Data", "Support email", options="Email"),
    F("staff_notification_email", "Data", "GRC team notification email", options="Email", description="Receives consultation requests and new submissions."),
    SB("sb_reg", "Registration"),
    F("block_personal_email_domains", "Check", "Block personal email domains", default="1", description="Customers must register with a work email. Turn off only for testing."),
    F("personal_email_domains", "Small Text", "Personal email domains", default="gmail.com,yahoo.com,hotmail.com,outlook.com,live.com,icloud.com,aol.com,proton.me,protonmail.com,gmx.com,mail.com,yandex.com,msn.com"),
    F("allowed_email_domains", "Small Text", "Allowed email domains (optional)", description="Comma separated. If set, only these domains can register."),
    F("verification_code_ttl_minutes", "Int", "Verification code lifetime (minutes)", default="15"),
    F("show_code_when_email_unavailable", "Check", "TEST ONLY: show verification code on screen when no outgoing email is configured", default="0",
      description="Never enable on a production site."),
    SB("sb_ass", "Assessments"),
    F("default_template", "Link", "Default template", options="GRC Assessment Template"),
    F("max_evidence_mb", "Int", "Maximum evidence file size (MB)", default="10"),
    F("allowed_evidence_extensions", "Small Text", "Allowed evidence file types", default="pdf,doc,docx,xls,xlsx,ppt,pptx,png,jpg,jpeg,txt,csv"),
    SB("sb_rem", "Reminders and SLAs"),
    F("reminders_enabled", "Check", "Automatic reminders enabled", default="1"),
    F("reminder_days_before_due", "Data", "Remind this many days before due date", default="7,3,1", description="Comma separated list of days."),
    F("overdue_reminder_every_days", "Int", "Repeat overdue reminders every (days)", default="7"),
    F("clarification_sla_days", "Int", "Clarification response SLA (days)", default="5"),
    F("review_sla_days", "Int", "Review SLA (days)", default="5"),
    SB("sb_rep", "Reports"),
    F("report_disclaimer_en", "Small Text", "Report disclaimer (English)",
      default="This maturity score is an assessment output based on the information supplied and reviewed. It does not constitute a regulatory compliance determination, certification or assurance opinion."),
    F("report_disclaimer_ar", "Small Text", "Report disclaimer (Arabic)",
      default="درجة النضج الواردة هنا مخرج تقييم مبني على المعلومات المقدمة والتي جرت مراجعتها، ولا تمثل حكماً بالامتثال التنظيمي ولا شهادة اعتماد ولا رأياً في التأكيد."),
], [P("S", "rw"), P("M", "rw")], issingle=1)

# ---------------------------------------------------------------- Organization
doctype("GRC Organization", [
    F("legal_name", "Data", "Legal name", reqd=1, in_list_view=1, in_standard_filter=1),
    F("legal_name_ar", "Data", "Legal name (Arabic)"),
    F("status", "Select", "Status", options="Active\nSuspended", default="Active", in_list_view=1, in_standard_filter=1),
    CB("cb1"),
    F("sector", "Select", "Sector", options=SECTORS, in_list_view=1, in_standard_filter=1),
    F("city", "Data", "City"),
    F("country", "Data", "Country", default="Saudi Arabia"),
    SB("sb_more", "Details"),
    F("commercial_registration", "Data", "Commercial registration no."),
    F("website", "Data", "Website"),
    F("preferred_language", "Select", "Preferred language", options="en\nar", default="en"),
    CB("cb2"),
    F("primary_contact_name", "Data", "Primary contact name"),
    F("primary_contact_email", "Data", "Primary contact email", options="Email"),
    SB("sb_group", "Group and notifications"),
    F("parent_organization", "Link", "Parent organization (holding company)", options="GRC Organization", description="Admins of the parent can view this organization's assessments (read only)."),
    F("notify_reminders", "Check", "Send reminder and status emails", default="1", description="Security emails (verification, invitations) and clarification requests are always sent."),
    CB("cb3"),
    F("managed_by_staff", "Check", "Created by the GRC team on behalf of the customer", read_only=1),
    F("created_by_user", "Link", "Created by", options="User", read_only=1),
], [P("S", "rwcd"), P("M", "rwc"), P("C", "rw"), P("R", "r")],
    autoname="format:ORG-{#####}", title_field="legal_name", search_fields="legal_name,sector,city", show_title_field_in_link=1)

doctype("GRC Organization Member", [
    F("user", "Link", "User", options="User", reqd=1, in_list_view=1),
    F("full_name", "Data", "Full name", fetch_from="user.full_name", read_only=1, in_list_view=1),
    F("organization", "Link", "Organization", options="GRC Organization", reqd=1, in_list_view=1, in_standard_filter=1),
    F("member_role", "Select", "Role in organization", options="Org Admin\nAssessor\nAction Owner\nViewer", default="Assessor", reqd=1, in_list_view=1),
    F("status", "Select", "Status", options="Active\nDisabled\nRemoved", default="Active", in_list_view=1),
    F("notify_email", "Check", "Receive reminder and status emails", default="1"),
    F("invited_by", "Link", "Invited by", options="User", read_only=1),
], [P("S", "rwcd"), P("M", "rwcd"), P("C", "r"), P("R", "r")], autoname="hash", title_field="full_name")

doctype("GRC Invitation", [
    F("email", "Data", "Email", options="Email", reqd=1, in_list_view=1),
    F("organization", "Link", "Organization", options="GRC Organization", reqd=1, in_list_view=1, in_standard_filter=1),
    F("member_role", "Select", "Role in organization", options="Org Admin\nAssessor\nAction Owner\nViewer", default="Assessor", reqd=1, in_list_view=1),
    F("status", "Select", "Status", options="Pending\nAccepted\nRevoked\nExpired", default="Pending", in_list_view=1, in_standard_filter=1),
    F("expires_on", "Datetime", "Expires on"),
    F("invited_by", "Link", "Invited by", options="User", read_only=1),
    F("accepted_by", "Link", "Accepted by", options="User", read_only=1),
    F("accepted_on", "Datetime", "Accepted on", read_only=1),
    F("token_hash", "Data", "Token hash", hidden=1, read_only=1),
], [P("S", "rwcd"), P("M", "rwcd"), P("C", "rwc"), P("R", "r")], autoname="hash", title_field="email")

# ---------------------------------------------------------------- Templates
doctype("GRC Template Section", [
    F("section_code", "Data", "Code", reqd=1, in_list_view=1),
    F("title", "Data", "Title", reqd=1, in_list_view=1),
    F("title_ar", "Data", "Title (Arabic)"),
    F("weight", "Float", "Weight", default="1", in_list_view=1),
    F("owner_role", "Data", "Suggested owner role"),
    F("owner_role_ar", "Data", "Suggested owner role (Arabic)"),
    F("reference", "Small Text", "Reference"),
    F("reference_ar", "Small Text", "Reference (Arabic)"),
], istable=1, editable_grid=1)

QOPT = []
for L in "abcd":
    QOPT += [F(f"option_{L}", "Small Text", f"Option {L.upper()}"), F(f"option_{L}_ar", "Small Text", f"Option {L.upper()} (Arabic)")]
doctype("GRC Template Question", [
    F("question_code", "Data", "Code", reqd=1, in_list_view=1),
    F("section_code", "Data", "Section", reqd=1, in_list_view=1),
    F("short_label", "Data", "Short label", in_list_view=1),
    F("short_label_ar", "Data", "Short label (Arabic)"),
    F("question_text", "Small Text", "Question", reqd=1),
    F("question_text_ar", "Small Text", "Question (Arabic)"),
    *QOPT,
    F("allow_na", "Check", "Can be Not Applicable"),
    F("is_gating", "Check", "Gating question"),
    F("gate_trigger", "Select", "Gate triggers on", options="A\nA or B", default="A"),
    F("gate_cap_level", "Data", "Caps maturity level at"),
    F("source_ref", "Data", "Original question ref"),
], istable=1, editable_grid=1)

doctype("GRC Maturity Band", [
    F("level_name", "Data", "Level", reqd=1, in_list_view=1),
    F("level_name_ar", "Data", "Level (Arabic)"),
    F("min_score", "Float", "From %", reqd=1, in_list_view=1),
    F("max_score", "Float", "To %", in_list_view=1),
    F("color", "Data", "Colour"),
    F("interpretation", "Small Text", "Interpretation"),
    F("interpretation_ar", "Small Text", "Interpretation (Arabic)"),
], istable=1, editable_grid=1)

doctype("GRC Assessment Template", [
    F("template_code", "Data", "Template code", reqd=1, unique=1, in_list_view=1, description="Short unique code, e.g. IIA-GIAS-20Q"),
    F("template_name", "Data", "Name", reqd=1, in_list_view=1),
    F("template_name_ar", "Data", "Name (Arabic)"),
    F("framework", "Data", "Framework"),
    F("is_active", "Check", "Active", default="1", in_list_view=1),
    F("show_on_website", "Check", "Show in public catalogue", default="1"),
    F("description", "Small Text", "Description"),
    F("description_ar", "Small Text", "Description (Arabic)"),
    F("latest_published_version", "Link", "Latest published version", options="GRC Template Version", read_only=1),
], [P("S", "rwcd"), P("M", "rwcd"), P("C", "r"), P("R", "r")], autoname="field:template_code", title_field="template_name")

doctype("GRC Template Version", [
    F("template", "Link", "Template", options="GRC Assessment Template", reqd=1, set_only_once=1, in_list_view=1, in_standard_filter=1),
    F("version_no", "Data", "Version", reqd=1, set_only_once=1, in_list_view=1),
    F("status", "Select", "Status", options="Draft\nPublished\nRetired", default="Draft", read_only=1, in_list_view=1, in_standard_filter=1),
    F("published_on", "Datetime", "Published on", read_only=1),
    F("published_by", "Link", "Published by", options="User", read_only=1),
    F("release_notes", "Small Text", "Release notes"),
    SB("sb_policy", "Scoring policy (frozen into every assessment at creation)"),
    F("points_a", "Float", "Points for A", default="25", reqd=1),
    F("points_b", "Float", "Points for B", default="50", reqd=1),
    F("points_c", "Float", "Points for C", default="75", reqd=1),
    F("points_d", "Float", "Points for D", default="100", reqd=1),
    CB("cb_pol"),
    F("weighting_method", "Select", "Weighting", options="Equal\nSection Weights", default="Equal"),
    F("enable_gating", "Check", "Apply gating caps", default="0", description="Open decision: should Q1 cap the final level?"),
    F("allow_na", "Check", "Allow Not Applicable where a question permits", default="0", description="Open decision: should Q20 allow N/A?"),
    SB("sb_intro", "Respondent guidance"),
    F("introduction", "Small Text", "Introduction"),
    F("introduction_ar", "Small Text", "Introduction (Arabic)"),
    F("answer_rule", "Small Text", "Answer rule"),
    F("answer_rule_ar", "Small Text", "Answer rule (Arabic)"),
    SB("sb_content", "Content"),
    F("sections", "Table", "Sections", options="GRC Template Section"),
    F("questions", "Table", "Questions", options="GRC Template Question"),
    F("bands", "Table", "Maturity bands", options="GRC Maturity Band"),
], [P("S", "rwcd"), P("M", "rwcd"), P("C", "r"), P("R", "r")], autoname="format:{template}-V{version_no}")

# ---------------------------------------------------------------- Assessment
STATES = "Draft\nIn Progress\nSubmitted\nUnder Review\nClarification Required\nResubmitted\nApproved\nReport Released"
doctype("GRC Assessment Answer", [
    F("question_code", "Data", "Question", reqd=1, in_list_view=1),
    F("section_code", "Data", "Section"),
    F("selected_option", "Select", "Customer answer", options="\nA\nB\nC\nD\nN/A", in_list_view=1),
    F("reviewer_option", "Select", "Reviewer-adjusted answer", options="\nA\nB\nC\nD\nN/A", in_list_view=1),
    F("points", "Float", "Points", read_only=1),
    F("comment", "Small Text", "Customer comment"),
    F("reviewer_note", "Small Text", "Reviewer note (internal)"),
    F("answered_on", "Datetime", "Answered on", read_only=1),
    F("answered_by", "Link", "Answered by", options="User", read_only=1),
    F("answered_by_staff", "Check", "Entered by the GRC team", read_only=1),
], istable=1, editable_grid=1)

doctype("GRC Assessment", [
    F("naming_series", "Select", "Series", options="ASM-.YYYY.-.#####", default="ASM-.YYYY.-.#####", hidden=1),
    F("organization", "Link", "Organization", options="GRC Organization", reqd=1, set_only_once=1, in_list_view=1, in_standard_filter=1),
    F("template_version", "Link", "Template version", options="GRC Template Version", reqd=1, set_only_once=1, in_standard_filter=1),
    F("template_title", "Data", "Assessment", read_only=1, in_list_view=1),
    CB("cb1"),
    F("status", "Select", "Status", options=STATES, default="Draft", read_only=1, in_list_view=1, in_standard_filter=1, no_copy=1),
    F("due_date", "Date", "Due date", in_list_view=1),
    F("respondent", "Link", "Started by", options="User", read_only=1),
    F("respondent_name", "Data", "Respondent", read_only=1),
    SB("sb_team", "GRC team"),
    F("assigned_consultant", "Link", "Assigned consultant", options="User", in_standard_filter=1),
    CB("cb_team"),
    F("reviewer", "Link", "Reviewer", options="User", in_standard_filter=1),
    SB("sb_prog", "Progress"),
    F("started_on", "Datetime", "Started", read_only=1),
    F("submitted_on", "Datetime", "Submitted", read_only=1),
    F("review_started_on", "Datetime", "Review started", read_only=1),
    CB("cb_prog"),
    F("approved_on", "Datetime", "Approved", read_only=1),
    F("approved_by", "Link", "Approved by", options="User", read_only=1),
    F("released_on", "Datetime", "Report released", read_only=1),
    F("released_by", "Link", "Released by", options="User", read_only=1),
    F("resubmit_count", "Int", "Resubmissions", read_only=1),
    SB("sb_res", "Results"),
    F("overall_score", "Percent", "Current score", read_only=1, in_list_view=1, description="Preliminary until the report is approved."),
    F("maturity_level", "Data", "Current level", read_only=1),
    F("result_type", "Select", "Result type", options="Preliminary\nApproved", read_only=1),
    CB("cb_res"),
    F("answered_count", "Int", "Answered", read_only=1),
    F("question_count", "Int", "Questions", read_only=1),
    F("gating_note", "Small Text", "Gating note", read_only=1),
    F("preliminary_score", "Percent", "Preliminary score (as submitted)", read_only=1),
    F("preliminary_level", "Data", "Preliminary level", read_only=1),
    F("final_score", "Percent", "Final score (approved)", read_only=1),
    F("final_level", "Data", "Final level", read_only=1),
    SB("sb_ans", "Answers"),
    F("answers", "Table", "Answers", options="GRC Assessment Answer"),
    SB("sb_notes", "Internal"),
    F("internal_notes", "Text", "Internal notes (never shown to the customer)"),
    SB("sb_snap", "Frozen scoring snapshot", collapsible=1),
    F("template_snapshot", "Code", "Template and scoring snapshot", options="JSON", read_only=1, no_copy=1),
    F("preliminary_result", "Code", "Preliminary result", options="JSON", read_only=1, no_copy=1),
    F("final_result", "Code", "Final result", options="JSON", read_only=1, no_copy=1),
], [P("S", "rwcd"), P("M", "rwcd"), P("C", "rwc"), P("R", "rw")],
    autoname="naming_series:", title_field="template_title", search_fields="organization,template_title,status", is_calendar_and_gantt=0)

# ---------------------------------------------------------------- Workflow companions
doctype("GRC Clarification", [
    F("assessment", "Link", "Assessment", options="GRC Assessment", reqd=1, in_list_view=1, in_standard_filter=1),
    F("organization", "Link", "Organization", options="GRC Organization", fetch_from="assessment.organization", read_only=1),
    F("question_code", "Data", "Question", in_list_view=1),
    F("kind", "Select", "Kind", options="Request\nReply", default="Request", in_list_view=1),
    F("author", "Link", "Author", options="User", read_only=1),
    F("author_name", "Data", "Author name", read_only=1, in_list_view=1),
    F("author_type", "Select", "Author type", options="Staff\nCustomer", read_only=1),
    F("status", "Select", "Status", options="Open\nAnswered\nResolved", default="Open", in_list_view=1, in_standard_filter=1),
    F("message", "Text", "Message", reqd=1),
], [P("S", "rwcd"), P("M", "rwc"), P("C", "rwc"), P("R", "rwc")], autoname="hash", title_field="question_code")

doctype("GRC Follow Up Log", [
    F("assessment", "Link", "Assessment", options="GRC Assessment", reqd=1, in_list_view=1, in_standard_filter=1),
    F("organization", "Link", "Organization", options="GRC Organization", fetch_from="assessment.organization", read_only=1, in_list_view=1),
    F("contact_type", "Select", "Type", options="Email Reminder\nPhone Call\nMeeting\nNote\nSystem Reminder", default="Note", reqd=1, in_list_view=1, in_standard_filter=1),
    F("followup_on", "Datetime", "When", default="Now", reqd=1, in_list_view=1),
    F("logged_by", "Link", "Logged by", options="User", default="__user"),
    F("note", "Text", "Note"),
    F("next_action_on", "Date", "Next action on"),
], [P("S", "rwcd"), P("M", "rwcd"), P("C", "rwc"), P("R", "r")], autoname="format:FUP-{#####}", title_field="contact_type")

doctype("GRC Activity Log", [
    F("assessment", "Link", "Assessment", options="GRC Assessment", reqd=1, in_list_view=1, in_standard_filter=1),
    F("organization", "Link", "Organization", options="GRC Organization", in_list_view=1, in_standard_filter=1),
    F("event_type", "Select", "Event", options="Answer\nEvidence\nStatus\nAssignment\nClarification\nReport\nReminder\nNote", in_list_view=1, in_standard_filter=1),
    F("actor", "Link", "By", options="User", in_list_view=1),
    F("actor_type", "Select", "Actor type", options="Customer\nStaff\nSystem", in_list_view=1, in_standard_filter=1),
    F("question_code", "Data", "Question"),
    F("detail", "Small Text", "Detail"),
    F("visible_to_customer", "Check", "Visible to customer", default="1"),
], [P("S", "r"), P("M", "r"), P("C", "r"), P("R", "r")], autoname="hash", title_field="event_type", track_changes=0, sort_field="creation")

doctype("GRC Reminder", [
    F("assessment", "Link", "Assessment", options="GRC Assessment", reqd=1, in_list_view=1, in_standard_filter=1),
    F("organization", "Link", "Organization", options="GRC Organization", fetch_from="assessment.organization", read_only=1, in_list_view=1),
    F("remind_on", "Date", "Remind on", reqd=1, in_list_view=1),
    F("status", "Select", "Status", options="Scheduled\nSent\nCancelled", default="Scheduled", in_list_view=1, in_standard_filter=1),
    F("message", "Small Text", "Message to the customer", description="Optional. A default message is used when blank."),
    F("sent_on", "Datetime", "Sent on", read_only=1),
], [P("S", "rwcd"), P("M", "rwcd"), P("C", "rwc"), P("R", "r")], autoname="format:REM-{#####}")

doctype("GRC Report", [
    F("assessment", "Link", "Assessment", options="GRC Assessment", reqd=1, in_list_view=1, in_standard_filter=1),
    F("organization", "Link", "Organization", options="GRC Organization", fetch_from="assessment.organization", read_only=1, in_list_view=1),
    F("report_type", "Select", "Report type", options="Preliminary\nApproved", reqd=1, in_list_view=1),
    F("language", "Select", "Language", options="en\nar", default="en", in_list_view=1),
    F("version", "Int", "Version", default="1"),
    F("score", "Percent", "Score"),
    F("maturity_level", "Data", "Level"),
    F("file", "Attach", "PDF file", read_only=1),
    F("generated_on", "Datetime", "Generated on", read_only=1),
    F("generated_by", "Link", "Generated by", options="User", read_only=1),
], [P("S", "rwcd"), P("M", "rwc"), P("C", "r"), P("R", "r")], autoname="format:RPT-{#####}")

# ---------------------------------------------------------------- Frameworks and website
doctype("GRC Framework Sector", [
    F("sector", "Select", "Sector", options="All Entities\n" + SECTORS, reqd=1, in_list_view=1),
], istable=1, editable_grid=1)

doctype("GRC Framework", [
    F("framework_code", "Data", "Code", reqd=1, unique=1, in_list_view=1),
    F("framework_name", "Data", "Name", reqd=1, in_list_view=1),
    F("framework_name_ar", "Data", "Name (Arabic)"),
    F("authority", "Data", "Authority"),
    F("authority_ar", "Data", "Authority (Arabic)"),
    F("category", "Select", "Category", options="Cybersecurity\nFinancial & Corporate Governance\nPrivacy & Data\nInternal Audit\nOther", in_list_view=1, in_standard_filter=1),
    F("version", "Data", "Version", in_list_view=1),
    F("status", "Select", "Status", options="Draft\nPublished", default="Draft", in_list_view=1, in_standard_filter=1),
    SB("sb_review", "Applicability review"),
    F("reviewed_on", "Date", "Applicability reviewed on", description="Shown on the website. Leave blank until IRSAA has reviewed this entry."),
    F("reviewed_by", "Link", "Reviewed by", options="User"),
    F("source_url", "Data", "Official source URL"),
    SB("sb_text", "Description"),
    F("description", "Small Text", "Description"),
    F("description_ar", "Small Text", "Description (Arabic)"),
    F("sectors", "Table", "Applicable sectors", options="GRC Framework Sector"),
], [P("S", "rwcd"), P("M", "rwcd"), P("C", "r"), P("R", "r")], autoname="field:framework_code", title_field="framework_name")

doctype("GRC Consultation Request", [
    F("full_name", "Data", "Name", reqd=1, in_list_view=1),
    F("email", "Data", "Email", options="Email", reqd=1, in_list_view=1),
    F("phone", "Data", "Phone"),
    F("organization_name", "Data", "Organization", in_list_view=1),
    F("sector", "Data", "Sector"),
    F("preferred_language", "Select", "Preferred language", options="en\nar"),
    F("status", "Select", "Status", options="New\nContacted\nClosed", default="New", in_list_view=1, in_standard_filter=1),
    F("assigned_to", "Link", "Assigned to", options="User"),
    F("message", "Text", "Message"),
    F("source_page", "Data", "Source page", read_only=1),
], [P("S", "rwcd"), P("M", "rwcd"), P("C", "rw")], autoname="format:CONS-{#####}", title_field="full_name")
