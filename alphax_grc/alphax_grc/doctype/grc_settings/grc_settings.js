frappe.ui.form.on("GRC Settings", {
  refresh(frm) {
    frm.add_custom_button(__("Send Test Email"), () => {
      frappe.prompt([{ fieldname: "to", label: __("Send to"), fieldtype: "Data", options: "Email", default: frappe.session.user_email, reqd: 1 }],
        (v) => frappe.call({ method: "alphax_grc.alphax_grc.doctype.grc_settings.grc_settings.send_test_email", args: v, freeze: true }).then((r) => {
          const m = r.message;
          frappe.msgprint({ title: __("Test email"), indicator: m.ok ? (m.seconds > 5 ? "orange" : "green") : "red",
            message: m.ok ? __("Sent in {0} seconds. {1}", [m.seconds, m.seconds > 5 ? __("That is slow: check the outgoing mail server.") : ""]) : __("Failed after {0} seconds: {1}", [m.seconds, frappe.utils.escape_html(m.error)]) });
        }), __("Send Test Email"));
    });
  },
});
