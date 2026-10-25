import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.platform_name = frappe.db.get_single_value("GRC Settings", "platform_name") or "AlphaX GRC & Audit Platform"
    context.title = context.platform_name
    context.show_sidebar = 0
    context.no_header = 1
    context.no_breadcrumbs = 1
