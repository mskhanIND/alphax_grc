import frappe

no_cache = 1


def get_context(context):
    context.platform_name = frappe.db.get_single_value("GRC Settings", "platform_name") or "AlphaX GRC & Audit Platform"
    context.frameworks = frappe.get_all("GRC Framework", filters={"status": "Published"}, fields=["framework_name", "framework_name_ar", "authority", "version", "description", "description_ar", "reviewed_on"], order_by="framework_name asc")
