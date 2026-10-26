"""Shared context for the public website pages."""
import frappe


def base(context, with_frameworks=False):
    s = frappe.get_cached_doc("GRC Settings")
    context.no_cache = 1
    context.platform_name = s.platform_name or "AlphaX GRC & Audit Platform"
    context.provider_name = s.provider_name or "IRSAA Business Solutions"
    context.support_email = s.support_email or ""
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.title = None
    if with_frameworks:
        rows = frappe.get_all("GRC Framework", filters={"status": "Published"}, order_by="framework_name asc",
                              fields=["name", "framework_name", "framework_name_ar", "authority", "authority_ar", "category", "version", "description", "description_ar", "reviewed_on"])
        for r in rows:
            r["sector_list"] = frappe.get_all("GRC Framework Sector", filters={"parent": r.name, "parenttype": "GRC Framework"}, pluck="sector", order_by="idx asc")
            r["cat"] = "".join(c if c.isalnum() else "-" for c in (r.category or "other").lower())
        context.frameworks = rows
    return context
