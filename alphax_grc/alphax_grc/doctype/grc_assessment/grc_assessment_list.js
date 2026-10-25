frappe.listview_settings["GRC Assessment"] = {
  add_fields: ["status", "overall_score", "maturity_level"],
  get_indicator(doc) {
    const c = { "Draft": "gray", "In Progress": "blue", "Submitted": "orange", "Under Review": "orange", "Clarification Required": "red", "Resubmitted": "orange", "Approved": "green", "Report Released": "green" };
    return [__(doc.status), c[doc.status] || "gray", "status,=," + doc.status];
  },
};
