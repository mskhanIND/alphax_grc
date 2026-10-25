"""Install and migrate hooks, seed data and helper commands."""
import json
import os
import secrets
import string

import frappe

STAFF_ROLES = ("GRC Manager", "GRC Consultant", "GRC Reviewer")
CUSTOMER_ROLE = "GRC Customer"
DATA = os.path.join(os.path.dirname(__file__), "..", "data")

SECTOR_MAP = {
    "Financing Companies": "Banking & Finance", "Financial Services": "Banking & Finance",
    "Capital Market Institutions": "Listed Companies", "Investment Funds": "Listed Companies",
    "Corporate": "All Entities",
}


def after_install():
    ensure_roles()
    ensure_file_field()
    configure_website()
    seed_template()
    seed_frameworks()
    configure_settings()
    frappe.db.commit()


def after_migrate():
    ensure_roles()
    ensure_file_field()


def ensure_file_field():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({"File": [dict(fieldname="grc_question_code", label="GRC Question Code", fieldtype="Data", read_only=1, hidden=1, no_copy=1, insert_after="file_name")]}, ignore_validate=True)


def ensure_roles():
    for role in (CUSTOMER_ROLE,) + STAFF_ROLES:
        desk = 0 if role == CUSTOMER_ROLE else 1
        if frappe.db.exists("Role", role):
            frappe.db.set_value("Role", role, "desk_access", desk, update_modified=False)
            continue
        frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": desk}).insert(ignore_permissions=True)


def configure_website():
    frappe.db.set_single_value("Website Settings", "home_page", "grc-home")
    # Customers must come in through the GRC portal (email verification + organization), never the generic sign-up.
    frappe.db.set_single_value("Website Settings", "disable_signup", 1)


def configure_settings():
    s = frappe.get_doc("GRC Settings")
    if not s.default_template and frappe.db.exists("GRC Assessment Template", "IIA-GIAS-20Q"):
        s.default_template = "IIA-GIAS-20Q"
    s.flags.ignore_permissions = True
    s.save()


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def _pick(d, keys):
    return {k: d.get(k) for k in keys if k in d}


def seed_template():
    if frappe.db.exists("GRC Assessment Template", "IIA-GIAS-20Q"):
        return
    data = _load("template_v1.json")
    info = data["info"]
    tpl = frappe.get_doc({
        "doctype": "GRC Assessment Template",
        "template_code": "IIA-GIAS-20Q",
        "template_name": info["name"],
        "template_name_ar": "تقييم نضج وظيفة التدقيق الداخلي (معايير IIA – المملكة العربية السعودية)",
        "framework": info["framework"],
        "description": info["introduction"],
        "description_ar": info["introduction_ar"],
        "is_active": 1, "show_on_website": 1,
    }).insert(ignore_permissions=True)
    ver = frappe.get_doc({
        "doctype": "GRC Template Version",
        "template": tpl.name, "version_no": "1.0", "status": "Draft",
        "release_notes": "Initial version from the 20-question Excel reference. Policy defaults follow the Excel: equal weights, "
                         "no Q1 gating cap, no Q20 Not Applicable. These are open decisions for the assessment owner.",
        "points_a": 25, "points_b": 50, "points_c": 75, "points_d": 100,
        "weighting_method": "Equal", "enable_gating": 0, "allow_na": 0,
        "introduction": info["introduction"], "introduction_ar": info["introduction_ar"],
        "answer_rule": info["answer_rule"], "answer_rule_ar": info["answer_rule_ar"],
    })
    for s in data["sections"]:
        ver.append("sections", {"section_code": s["section_code"], "title": s["section_title"], "title_ar": s["section_title_ar"],
                                "reference": s["reference"], "reference_ar": s["reference_ar"], "weight": s.get("weight", 1),
                                "owner_role": s["owner_role"], "owner_role_ar": s["owner_role_ar"]})
    qkeys = ["question_code", "section_code", "short_label", "short_label_ar", "question_text", "question_text_ar",
             "option_a", "option_a_ar", "option_b", "option_b_ar", "option_c", "option_c_ar", "option_d", "option_d_ar",
             "allow_na", "is_gating", "gate_trigger", "gate_cap_level", "source_ref"]
    for q in data["questions"]:
        ver.append("questions", _pick(q, qkeys))
    for b in data["bands"]:
        ver.append("bands", _pick(b, ["level_name", "level_name_ar", "min_score", "max_score", "color", "interpretation", "interpretation_ar"]))
    ver.insert(ignore_permissions=True)
    ver.flags.allow_lifecycle_change = True
    ver.db_set({"status": "Published", "published_on": frappe.utils.now_datetime(), "published_by": "Administrator"})
    frappe.db.set_value("GRC Assessment Template", tpl.name, "latest_published_version", ver.name)


def seed_frameworks():
    for fw in _load("frameworks.json"):
        if frappe.db.exists("GRC Framework", fw["id"]):
            continue
        sectors = []
        for s in fw["sectors"]:
            s = SECTOR_MAP.get(s, s)
            if s not in sectors:
                sectors.append(s)
        doc = frappe.get_doc({
            "doctype": "GRC Framework", "framework_code": fw["id"], "framework_name": fw["name"], "framework_name_ar": fw["name_ar"],
            "authority": fw["authority"], "authority_ar": fw["authority_ar"], "category": fw["category"], "version": fw["version"],
            "description": fw["description"], "description_ar": fw["description_ar"], "status": "Published",
            "sectors": [{"sector": s} for s in sectors],
        })
        doc.insert(ignore_permissions=True)


def _password():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(14)) + "9a"


def create_demo_staff():
    """bench --site <site> execute alphax_grc.grc.install.create_demo_staff
    Creates one user per GRC staff role for testing and prints their passwords."""
    out = {}
    for local, role, first in (("manager", "GRC Manager", "Demo Manager"), ("consultant", "GRC Consultant", "Demo Consultant"), ("reviewer", "GRC Reviewer", "Demo Reviewer")):
        email = "demo.%s@alphax-demo.test" % local
        pwd = _password()
        if frappe.db.exists("User", email):
            user = frappe.get_doc("User", email)
        else:
            user = frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "user_type": "System User", "send_welcome_email": 0, "enabled": 1})
        if not user.get("roles") or role not in [r.role for r in user.roles]:
            user.append("roles", {"role": role})
        user.new_password = pwd
        user.flags.ignore_permissions = True
        user.flags.ignore_password_policy = True
        user.save()
        out[email] = {"role": role, "password": pwd}
    frappe.db.commit()
    for k, v in out.items():
        print("%s  %s  password: %s" % (k, v["role"], v["password"]))
    return out


def enable_staff_2fa():
    """bench --site <site> execute alphax_grc.grc.install.enable_staff_2fa
    Turns on two-factor authentication for GRC staff roles (authenticator app). Do this before go-live."""
    frappe.db.set_single_value("System Settings", "enable_two_factor_auth", 1)
    frappe.db.set_single_value("System Settings", "two_factor_method", "OTP App")
    for role in STAFF_ROLES:
        frappe.db.set_value("Role", role, "two_factor_auth", 1)
    frappe.db.commit()
    print("Two-factor authentication enabled for", ", ".join(STAFF_ROLES))
