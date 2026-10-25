import frappe

no_cache = 1


def get_context(context):
    context.platform_name = frappe.db.get_single_value("GRC Settings", "platform_name") or "AlphaX GRC & Audit Platform"
    context.provider_name = frappe.db.get_single_value("GRC Settings", "provider_name") or "IRSAA Business Solutions"
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.title = None
