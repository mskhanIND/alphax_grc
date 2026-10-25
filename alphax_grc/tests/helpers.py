"""Dev helpers run with:  bench --site <site> execute alphax_grc.tests.helpers.<function>"""
import frappe


def info():
    q = lambda sql: frappe.db.sql(sql)[0][0]
    print("template versions:", frappe.db.sql("select name, status from `tabGRC Template Version`"))
    print("questions:", q("select count(*) from `tabGRC Template Question`"),
          "sections:", q("select count(*) from `tabGRC Template Section`"),
          "bands:", q("select count(*) from `tabGRC Maturity Band`"),
          "frameworks:", q("select count(*) from `tabGRC Framework`"))
    print("roles:", [r[0] for r in frappe.db.sql("select role_name from tabRole where role_name like 'GRC%'")])
    print("website home:", frappe.db.get_single_value("Website Settings", "home_page"), "disable_signup:", frappe.db.get_single_value("Website Settings", "disable_signup"))
    s = frappe.get_doc("GRC Settings")
    print("settings default_template:", s.default_template, "| block_personal:", s.block_personal_email_domains, "| ttl:", s.verification_code_ttl_minutes, "| reminder days:", s.reminder_days_before_due)


def dev_settings():
    """Sandbox/testing: allow personal email domains and show the registration code on screen when email is not configured."""
    frappe.db.set_single_value("GRC Settings", "block_personal_email_domains", 0)
    frappe.db.set_single_value("GRC Settings", "show_code_when_email_unavailable", 1)
    frappe.db.commit()


def last_error():
    for r in frappe.get_all("Error Log", fields=["name", "method", "error"], order_by="creation desc", limit=6):
        print("----", r.method); print((r.error or "")[-700:])


def desk_check():
    for dt, n in [("Workspace", "AlphaX GRC"), ("Report", "GRC Survey Tracker"), ("Report", "GRC Consultant Workload"),
                  ("Number Card", "Open Assessments"), ("Number Card", "Awaiting Review"), ("Number Card", "Clarification Pending")]:
        print(dt, n, bool(frappe.db.exists(dt, n)))
    from frappe.desk.query_report import run
    for r in ("GRC Survey Tracker", "GRC Consultant Workload"):
        print(r, "runs:", len(run(r, {}).get("result", [])), "rows")
