app_name = "alphax_grc"
app_title = "AlphaX GRC"
app_publisher = "Neotec Integrated Solutions"
app_description = "AlphaX GRC & Audit Platform: customer portal, assessments and GRC review workspace"
app_email = "info@neotec.ai"
app_license = "Proprietary"
required_apps = ["frappe"]

after_install = "alphax_grc.grc.install.after_install"
after_migrate = "alphax_grc.grc.install.after_migrate"

# Customers land in the portal after sign in.
role_home_page = {"GRC Customer": "grc"}

permission_query_conditions = {
    "GRC Assessment": "alphax_grc.grc.access.assessment_query",
    "GRC Organization": "alphax_grc.grc.access.organization_query",
    "GRC Clarification": "alphax_grc.grc.access.clarification_query",
    "GRC Follow Up Log": "alphax_grc.grc.access.followup_query",
    "GRC Reminder": "alphax_grc.grc.access.reminder_query",
    "GRC Report": "alphax_grc.grc.access.report_query",
    "GRC Activity Log": "alphax_grc.grc.access.activity_query",
    "GRC Organization Member": "alphax_grc.grc.access.member_query",
    "GRC Invitation": "alphax_grc.grc.access.invitation_query",
}

has_permission = {
    "GRC Assessment": "alphax_grc.grc.access.assessment_has_permission",
    "GRC Organization": "alphax_grc.grc.access.organization_has_permission",
    "GRC Clarification": "alphax_grc.grc.access.clarification_has_permission",
    "GRC Follow Up Log": "alphax_grc.grc.access.followup_has_permission",
    "GRC Reminder": "alphax_grc.grc.access.reminder_has_permission",
    "GRC Report": "alphax_grc.grc.access.report_has_permission",
    "GRC Activity Log": "alphax_grc.grc.access.activity_has_permission",
    "GRC Organization Member": "alphax_grc.grc.access.member_has_permission",
    "GRC Invitation": "alphax_grc.grc.access.invitation_has_permission",
}

scheduler_events = {
    "daily": ["alphax_grc.grc.tasks.daily"],
}
