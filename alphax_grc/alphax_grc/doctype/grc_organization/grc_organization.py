import frappe
from frappe import _
from frappe.model.document import Document

from alphax_grc.grc import access, activity


class GRCOrganization(Document):
    def before_insert(self):
        user = frappe.session.user
        if access.is_staff(user) and not self.created_by_user:
            self.created_by_user = user
            self.managed_by_staff = 1

    def validate(self):
        p = self.parent_organization
        if p:
            if p == self.name:
                frappe.throw(_("An organization cannot be its own parent."))
            if not self.is_new() and p in access.subsidiaries(self.name, depth=5):
                frappe.throw(_("The parent organization cannot be one of this organization's subsidiaries."))


@frappe.whitelist()
def invite_customer_admin(organization, email, role="Org Admin"):
    """GRC team invites the customer's first admin (or any member) into an organization the team created."""
    if not access.is_staff():
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    frappe.get_doc("GRC Organization", organization).check_permission("write")
    from alphax_grc.api import auth
    from alphax_grc.grc import notify
    email = auth.clean_email(email)
    if role not in access.ORG_ROLES:
        frappe.throw(_("Choose a valid role."))
    if frappe.db.exists("GRC Organization Member", {"user": email, "organization": organization, "status": "Active"}):
        frappe.throw(_("This person is already a member."))
    for n in frappe.get_all("GRC Invitation", filters={"organization": organization, "email": email, "status": "Pending"}, pluck="name"):
        frappe.db.set_value("GRC Invitation", n, "status", "Revoked")
    inv, token, link = auth.create_invitation(organization, email, role, frappe.session.user)
    org = frappe.db.get_value("GRC Organization", organization, "legal_name")
    sent = notify.send(email, notify.tr("invite_subject", "en", org=org, platform=notify.platform_name()),
                       notify.tr("invite_body", "en", inviter=frappe.utils.escape_html(frappe.utils.get_fullname(frappe.session.user)),
                                 org=frappe.utils.escape_html(org), platform=notify.platform_name(), role=role, days=auth.INVITE_DAYS, url=link), "en", "", now=True)
    return {"email_sent": bool(sent), "link": link}
