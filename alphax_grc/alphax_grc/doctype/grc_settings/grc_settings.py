import time

import frappe
from frappe import _
from frappe.model.document import Document

from alphax_grc.grc import access


class GRCSettings(Document):
    pass


@frappe.whitelist()
def send_test_email(to=None):
    """Send one email immediately and report how long the mail server took. Helps diagnose slow verification emails."""
    if not access.is_manager():
        frappe.throw(_("Only a GRC Manager can do this."), frappe.PermissionError)
    to = (to or frappe.session.user).strip()
    started = time.time()
    try:
        frappe.sendmail(recipients=[to], subject="GRC test email", message="This is a test email from the GRC platform.", now=True)
    except Exception as e:
        return {"ok": False, "seconds": round(time.time() - started, 1), "error": str(e)[:300]}
    return {"ok": True, "seconds": round(time.time() - started, 1)}
