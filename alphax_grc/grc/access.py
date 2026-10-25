"""Who can see what.

Customers (GRC Customer role) have NO DocType permissions. They only reach data through the whitelisted
portal API, which resolves their organization membership first (see api/portal.py).

Staff:
  * GRC Manager and System Manager see everything.
  * GRC Consultant and GRC Reviewer see only assessments where they are the assigned consultant or reviewer,
    plus the organizations and child records that belong to those assessments.
"""
import frappe

MANAGER_ROLES = {"GRC Manager", "System Manager"}
STAFF_ROLES = {"GRC Manager", "GRC Consultant", "GRC Reviewer", "System Manager"}
ORG_ROLES = ("Org Admin", "Assessor", "Action Owner", "Viewer")
ORG_EDIT_ROLES = ("Org Admin", "Assessor")


def _roles(user):
    return set(frappe.get_roles(user))


def is_manager(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or bool(_roles(user) & MANAGER_ROLES)


def is_staff(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or bool(_roles(user) & STAFF_ROLES)


def is_reviewer(user=None):
    user = user or frappe.session.user
    return is_manager(user) or "GRC Reviewer" in _roles(user)


# ------------------------------------------------------------------ membership (customers)
def get_membership(user=None):
    """Active organization membership of a portal user, or None."""
    user = user or frappe.session.user
    if not user or user == "Guest":
        return None
    row = frappe.db.get_value(
        "GRC Organization Member",
        {"user": user, "status": "Active"},
        ["name", "organization", "member_role", "status", "full_name"],
        as_dict=True,
    )
    if not row:
        return None
    if frappe.db.get_value("GRC Organization", row.organization, "status") != "Active":
        return None
    return row


def require_membership(user=None):
    m = get_membership(user)
    if not m:
        frappe.throw(frappe._("You are not a member of an organization."), frappe.PermissionError)
    return m


def not_found():
    """One generic error for missing AND foreign records so existence is never revealed."""
    frappe.throw(frappe._("Not found"), frappe.DoesNotExistError)


# ------------------------------------------------------------------ staff scoping (Desk)
def _assigned_clause(user):
    u = frappe.db.escape(user)
    return "(`tabGRC Assessment`.assigned_consultant = {u} or `tabGRC Assessment`.reviewer = {u})".format(u=u)


def assessment_query(user=None):
    user = user or frappe.session.user
    if is_manager(user):
        return ""
    if is_staff(user):
        return _assigned_clause(user)
    return "1=0"


def _assigned_assessments_subquery(user):
    u = frappe.db.escape(user)
    return "select name from `tabGRC Assessment` where assigned_consultant = {u} or reviewer = {u}".format(u=u)


def organization_query(user=None):
    user = user or frappe.session.user
    if is_manager(user):
        return ""
    if is_staff(user):
        sub = "select organization from `tabGRC Assessment` where assigned_consultant = {u} or reviewer = {u}".format(u=frappe.db.escape(user))
        return "`tabGRC Organization`.name in ({})".format(sub)
    return "1=0"


def _child_query(doctype):
    def fn(user=None):
        user = user or frappe.session.user
        if is_manager(user):
            return ""
        if is_staff(user):
            return "`tab{dt}`.assessment in ({sub})".format(dt=doctype, sub=_assigned_assessments_subquery(user))
        return "1=0"
    return fn


clarification_query = _child_query("GRC Clarification")
followup_query = _child_query("GRC Follow Up Log")
reminder_query = _child_query("GRC Reminder")
report_query = _child_query("GRC Report")


def _assigned(doc, user):
    return user in (doc.get("assigned_consultant"), doc.get("reviewer"))


def assessment_has_permission(doc, ptype=None, user=None, **kwargs):
    user = user or frappe.session.user
    if is_manager(user):
        return None
    if is_staff(user):
        if doc.is_new():
            return None  # creating is governed by role permissions
        return None if _assigned(doc, user) else False
    return False


def organization_has_permission(doc, ptype=None, user=None, **kwargs):
    user = user or frappe.session.user
    if is_manager(user):
        return None
    if is_staff(user):
        if doc.is_new():
            return None
        hit = frappe.db.sql(
            "select 1 from `tabGRC Assessment` where organization=%s and (assigned_consultant=%s or reviewer=%s) limit 1",
            (doc.name, user, user))
        return None if hit else False
    return False


def _child_has_permission(doc, ptype=None, user=None, **kwargs):
    user = user or frappe.session.user
    if is_manager(user):
        return None
    if is_staff(user):
        if doc.is_new():
            return None
        a = frappe.db.get_value("GRC Assessment", doc.get("assessment"), ["assigned_consultant", "reviewer"], as_dict=True)
        if a and user in (a.assigned_consultant, a.reviewer):
            return None
        return False
    return False


clarification_has_permission = followup_has_permission = reminder_has_permission = report_has_permission = _child_has_permission
