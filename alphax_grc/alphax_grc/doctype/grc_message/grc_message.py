import frappe
from frappe import _
from frappe.model.document import Document

from alphax_grc.grc import access, notify


class GRCMessage(Document):
    def before_insert(self):
        user = frappe.session.user
        self.sender_type = "Staff" if access.is_staff(user) else "Customer"
        self.sender = self.sender or user
        self.sender_name = self.sender_name or frappe.utils.get_fullname(user)
        self.body = (self.body or "").strip()[:5000]
        if not self.body:
            frappe.throw(_("Write a message first."))
        if self.assessment and frappe.db.get_value("GRC Assessment", self.assessment, "organization") != self.organization:
            frappe.throw(_("The assessment does not belong to this organization."))
        if self.sender_type == "Staff":
            self.read_by_staff = 1
        else:
            self.read_by_customer = 1

    def after_insert(self):
        """Staff to customer: always emailed (it is a direct reply). Customer to staff: emailed to the team inbox and the assigned consultant."""
        try:
            if self.sender_type == "Staff":
                emails = notify.org_admin_emails(self.organization)
                if self.assessment:
                    r = frappe.db.get_value("GRC Assessment", self.assessment, "respondent")
                    if r:
                        emails = list(emails) + [r]
                lang = notify.user_language(emails[0]) if emails else "en"
                notify.send(emails, notify.tr("msg_subject", lang), notify.tr("msg_body", lang, body=frappe.utils.escape_html(self.body).replace("\\n", "<br>"),
                            url=notify.portal_url("#/messages")), lang, "", ("GRC Message", self.name))
            else:
                staff = list(notify.staff_notification_recipients())
                if self.assessment:
                    c = frappe.db.get_value("GRC Assessment", self.assessment, "assigned_consultant")
                    if c:
                        staff.append(c)
                org = frappe.db.get_value("GRC Organization", self.organization, "legal_name")
                url = frappe.utils.get_url_to_form("GRC Message", self.name)
                key = "staff_change_subject" if self.kind == "Change Request" else "staff_msg_subject"
                notify.send(staff, notify.tr(key, "en", org=org), notify.tr("staff_msg_body", "en", org=frappe.utils.escape_html(org), name=frappe.utils.escape_html(self.sender_name),
                            body=frappe.utils.escape_html(self.body).replace("\\n", "<br>"), url=url), "en")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "GRC message notification")
