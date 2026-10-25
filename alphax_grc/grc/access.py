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
def get_memberships(user=None):
    """All active memberships of a portal user in active organizations (a user may belong to several)."""
    user = user or frappe.session.user
    if not user or user == "Guest":
        return []
    rows = frappe.get_all(
        "GRC Organization Member", filters={"user": user, "status": "Active"},
        fields=["name", "organization", "member_role", "status", "full_name", "notify_email"], order_by="creation asc")
    return [r for r in rows if frappe.db.get_value("GRC Organization", r.organization, "status") == "Active"]


def get_membership(user=None, organization=None):
    """The membership the user is currently working in. The choice is remembered per user (switch_organization)."""
    user = user or frappe.session.user
    ms = get_memberships(user)
    if not ms:
        return None
    want = organization or frappe.db.get_value("User", user, "grc_active_org")
    for m in ms:
        if m.organization == want:
            return m
    return ms[0]


def set_active_organization(user, organization):
    frappe.db.set_value("User", user, "grc_active_org", organization, update_modified=False)


def require_membership(user=None):
    m = get_membership(user)
    if not m:
        frappe.throw(frappe._("You are not a member of an organization."), frappe.PermissionError)
    return m


def subsidiaries(organization, depth=3):
    """Organizations below a holding company (children, grandchildren ...), cycle-safe."""
    seen, frontier = set(), [organization]
    for _ in range(depth):
        kids = frappe.get_all("GRC Organization", filters={"parent_organization": ["in", frontier], "status": "Active"}, pluck="name") if frontier else []
        frontier = [k for k in kids if k not in seen and k != organization]
        seen.update(frontier)
    return sorted(seen)


def can_view_group_org(m, organization):
    """An Org Admin of a holding company may VIEW results of its subsidiaries (read only)."""
    return m.member_role == "Org Admin" and organization in subsidiaries(m.organization)


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
activity_query = _child_query("GRC Activity Log")


def _org_child_query(doctype):
    def fn(user=None):
        user = user or frappe.session.user
        if is_manager(user):
            return ""
        if is_staff(user):
            sub = "select organization from `tabGRC Assessment` where assigned_consultant = {u} or reviewer = {u}".format(u=frappe.db.escape(user))
            return "`tab{dt}`.organization in ({sub})".format(dt=doctype, sub=sub)
        return "1=0"
    return fn


member_query = _org_child_query("GRC Organization Member")
invitation_query = _org_child_query("GRC Invitation")


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


clarification_has_permission = followup_has_permission = reminder_has_permission = report_has_permission = activity_has_permission = _child_has_permission


def _org_child_has_permission(doc, ptype=None, user=None, **kwargs):
    user = user or frappe.session.user
    if is_manager(user):
        return None
    if is_staff(user):
        if doc.is_new():
            return None
        hit = frappe.db.sql(
            "select 1 from `tabGRC Assessment` where organization=%s and (assigned_consultant=%s or reviewer=%s) limit 1",
            (doc.get("organization"), user, user))
        return None if hit else False
    return False


member_has_permission = invitation_has_permission = _org_child_has_permission
