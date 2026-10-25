frappe.ui.form.on("GRC Template Version", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Publish"), () => {
				frappe.confirm(
					__("Publishing locks this version. Assessments created from it will use it exactly as it is. Continue?"),
					() => frappe.call({
						method: "alphax_grc.alphax_grc.doctype.grc_template_version.grc_template_version.publish",
						args: { name: frm.doc.name },
						callback: () => frm.reload_doc(),
					})
				);
			}).addClass("btn-primary");
		}
		if (frm.doc.status === "Published") {
			frm.add_custom_button(__("Retire"), () => {
				frappe.confirm(__("Retired versions cannot be used for new assessments. Continue?"), () =>
					frappe.call({
						method: "alphax_grc.alphax_grc.doctype.grc_template_version.grc_template_version.retire",
						args: { name: frm.doc.name },
						callback: () => frm.reload_doc(),
					})
				);
			}, __("Actions"));
		}
		frm.add_custom_button(__("New Version"), () => {
			frappe.prompt({ fieldname: "version_no", label: __("New version number"), fieldtype: "Data", reqd: 1 }, (v) => {
				frappe.call({
					method: "alphax_grc.alphax_grc.doctype.grc_template_version.grc_template_version.new_version",
					args: { name: frm.doc.name, version_no: v.version_no },
					callback: (r) => frappe.set_route("Form", "GRC Template Version", r.message),
				});
			}, __("Copy to a new Draft version"));
		}, __("Actions"));
		if (frm.doc.status !== "Draft") {
			frm.dashboard.set_headline_alert(__("This version is locked. Create a new version to change content or scoring policy."), "blue");
		}
	},
});
