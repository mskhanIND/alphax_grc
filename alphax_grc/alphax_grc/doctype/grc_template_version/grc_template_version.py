import json

import frappe
from frappe import _
from frappe.model.document import Document

SECTION_KEYS = ("section_code", "title", "title_ar", "reference", "reference_ar", "weight", "owner_role", "owner_role_ar")
BAND_KEYS = ("level_name", "level_name_ar", "min_score", "max_score", "color", "interpretation", "interpretation_ar")
QUESTION_KEYS = (
    "question_code", "section_code", "short_label", "short_label_ar", "question_text", "question_text_ar",
    "option_a", "option_a_ar", "option_b", "option_b_ar", "option_c", "option_c_ar", "option_d", "option_d_ar",
    "allow_na", "is_gating", "gate_trigger", "gate_cap_level", "source_ref",
)


def _pick(row, keys):
    return {k: row.get(k) for k in keys}


class GRCTemplateVersion(Document):
    def validate(self):
        before = self.get_doc_before_save()
        if before and before.status in ("Published", "Retired") and not self.flags.allow_lifecycle_change:
            frappe.throw(_("A {0} template version cannot be edited. Create a new version instead.").format(before.status))
        self.validate_content()

    def validate_content(self):
        codes = [q.question_code for q in self.questions]
        if len(codes) != len(set(codes)):
            frappe.throw(_("Question codes must be unique."))
        sections = {s.section_code for s in self.sections}
        for q in self.questions:
            if q.section_code not in sections:
                frappe.throw(_("Question {0} refers to unknown section {1}.").format(q.question_code, q.section_code))
        if self.bands:
            mins = sorted(float(b.min_score or 0) for b in self.bands)
            if mins[0] != 0:
                frappe.throw(_("The lowest maturity band must start at 0%."))
        for k in ("points_a", "points_b", "points_c", "points_d"):
            if float(self.get(k) or 0) < 0:
                frappe.throw(_("Points cannot be negative."))

    def on_trash(self):
        if self.status != "Draft":
            frappe.throw(_("Only Draft versions can be deleted. Retire this version instead."))
        if frappe.db.exists("GRC Assessment", {"template_version": self.name}):
            frappe.throw(_("This version is used by assessments and cannot be deleted."))

    def get_snapshot(self):
        tpl = frappe.get_cached_doc("GRC Assessment Template", self.template)
        return {
            "template": self.template,
            "template_name": tpl.template_name,
            "template_name_ar": tpl.template_name_ar or tpl.template_name,
            "framework": tpl.framework,
            "version": self.version_no,
            "version_name": self.name,
            "points": {"A": self.points_a, "B": self.points_b, "C": self.points_c, "D": self.points_d},
            "weighting_method": self.weighting_method or "Equal",
            "enable_gating": int(self.enable_gating or 0),
            "allow_na": int(self.allow_na or 0),
            "introduction": self.introduction, "introduction_ar": self.introduction_ar,
            "answer_rule": self.answer_rule, "answer_rule_ar": self.answer_rule_ar,
            "sections": [_pick(r, SECTION_KEYS) for r in self.sections],
            "questions": [_pick(r, QUESTION_KEYS) for r in self.questions],
            "bands": [_pick(r, BAND_KEYS) for r in sorted(self.bands, key=lambda b: float(b.min_score or 0))],
        }


@frappe.whitelist()
def publish(name):
    """Lock a Draft version and make it the template's latest published version."""
    frappe.only_for(("GRC Manager", "System Manager"))
    doc = frappe.get_doc("GRC Template Version", name)
    if doc.status != "Draft":
        frappe.throw(_("Only Draft versions can be published."))
    if not doc.questions or not doc.sections or not doc.bands:
        frappe.throw(_("A version needs sections, questions and maturity bands before it can be published."))
    doc.validate_content()
    doc.flags.allow_lifecycle_change = True
    doc.db_set({"status": "Published", "published_on": frappe.utils.now_datetime(), "published_by": frappe.session.user})
    frappe.db.set_value("GRC Assessment Template", doc.template, "latest_published_version", doc.name)
    return doc.name


@frappe.whitelist()
def retire(name):
    frappe.only_for(("GRC Manager", "System Manager"))
    doc = frappe.get_doc("GRC Template Version", name)
    if doc.status != "Published":
        frappe.throw(_("Only Published versions can be retired."))
    doc.db_set("status", "Retired")
    latest = frappe.db.get_value("GRC Assessment Template", doc.template, "latest_published_version")
    if latest == doc.name:
        other = frappe.get_all("GRC Template Version", filters={"template": doc.template, "status": "Published", "name": ["!=", doc.name]},
                               order_by="published_on desc", limit=1, pluck="name")
        frappe.db.set_value("GRC Assessment Template", doc.template, "latest_published_version", other[0] if other else None)
    return doc.name


@frappe.whitelist()
def new_version(name, version_no):
    """Clone any version into a new Draft so policy or wording can change without touching history."""
    frappe.only_for(("GRC Manager", "System Manager"))
    src = frappe.get_doc("GRC Template Version", name)
    new = frappe.copy_doc(src)
    new.version_no = version_no
    new.status = "Draft"
    new.published_on = None
    new.published_by = None
    new.release_notes = _("Copied from {0}").format(src.name)
    new.insert()
    return new.name
