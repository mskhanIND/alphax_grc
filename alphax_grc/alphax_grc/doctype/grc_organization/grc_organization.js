frappe.ui.form.on("GRC Organization", {
  refresh(frm) {
    if (frm.is_new()) return;
    frm.add_custom_button(__("Assign Assessment"), () => {
      frappe.prompt([{ fieldname: "due_date", label: __("Due date"), fieldtype: "Date" },
                     { fieldname: "assigned_consultant", label: __("Consultant"), fieldtype: "Link", options: "User" },
                     { fieldname: "reviewer", label: __("Reviewer"), fieldtype: "Link", options: "User" }],
        (v) => frappe.call({ method: "alphax_grc.alphax_grc.doctype.grc_assessment.grc_assessment.create_for_organization", args: Object.assign({ organization: frm.doc.name }, v) })
          .then((r) => frappe.set_route("Form", "GRC Assessment", r.message)),
        __("Assign Assessment"));
    });
  },
});
