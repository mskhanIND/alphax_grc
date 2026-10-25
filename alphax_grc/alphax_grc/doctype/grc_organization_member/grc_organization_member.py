import frappe
from frappe import _
from frappe.model.document import Document


class GRCOrganizationMember(Document):
    def validate(self):
        dup = frappe.db.exists("GRC Organization Member", {"user": self.user, "organization": self.organization, "name": ["!=", self.name or ""], "status": ["!=", "Removed"]})
        if dup and self.status != "Removed":
            frappe.throw(_("{0} is already a member of this organization.").format(self.user))
        roles = set(frappe.get_roles(self.user))
        if roles & {"GRC Manager", "GRC Consultant", "GRC Reviewer", "System Manager"} and self.status == "Active":
            frappe.throw(_("GRC team members cannot be customer organization members. Use a separate customer account."))
