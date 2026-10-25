frappe.ui.form.on("GRC Assessment", {
  refresh(frm) {
    if (frm.is_new()) return;
    const call = (action, note, requests) =>
      frappe.call({
        method: "alphax_grc.alphax_grc.doctype.grc_assessment.grc_assessment.staff_action",
        args: { name: frm.doc.name, action, note, requests },
        freeze: true,
      }).then(() => frm.reload_doc());
    const add = (label, action, group) => frm.add_custom_button(label, () => {
      frappe.confirm(__("{0}?", [label]), () => call(action));
    }, group || __("Review"));
    const s = frm.doc.status;
    if (["Submitted", "Resubmitted"].includes(s)) add(__("Start Review"), "start_review");
    if (s === "Under Review") {
      frm.add_custom_button(__("Request Clarification"), () => {
        frappe.prompt([{ fieldname: "question_code", label: __("Question code (optional)"), fieldtype: "Data" },
                       { fieldname: "message", label: __("Message"), fieldtype: "Small Text", reqd: 1 }],
          (v) => call("request_clarification", null, JSON.stringify([{ question_code: v.question_code || "", message: v.message }])),
          __("Request Clarification"));
      }, __("Review"));
      add(__("Approve"), "approve");
    }
    if (s === "Approved") {
      add(__("Release Report"), "release");
      add(__("Reopen"), "reopen");
    }
    if (frappe.user.has_role(["GRC Manager", "System Manager"]) && s !== "Report Released") {
      frm.add_custom_button(__("Assign"), () => {
        frappe.prompt([{ fieldname: "assigned_consultant", label: __("Consultant"), fieldtype: "Link", options: "User", default: frm.doc.assigned_consultant },
                       { fieldname: "reviewer", label: __("Reviewer"), fieldtype: "Link", options: "User", default: frm.doc.reviewer },
                       { fieldname: "due_date", label: __("Due date"), fieldtype: "Date", default: frm.doc.due_date }],
          (v) => frappe.call({ method: "alphax_grc.alphax_grc.doctype.grc_assessment.grc_assessment.assign", args: Object.assign({ name: frm.doc.name }, v) }).then(() => frm.reload_doc()),
          __("Assign"));
      });
    }
    frm.add_custom_button(__("Review Panel"), () => {
      frappe.call("alphax_grc.alphax_grc.doctype.grc_assessment.grc_assessment.get_review_summary", { name: frm.doc.name }).then((r) => {
        const d = r.message;
        const rows = d.answers.map((a) => `<tr><td><b>${frappe.utils.escape_html(a.question_code)}</b> ${frappe.utils.escape_html(a.short_label || "")}</td>
          <td>${a.selected_option || "-"}</td><td>${a.reviewer_option || ""}</td><td>${frappe.utils.escape_html(a.comment || "")}</td>
          <td>${(a.evidence || []).map((f) => frappe.utils.escape_html(f.file_name)).join("<br>")}</td></tr>`).join("");
        frappe.msgprint({ title: __("Answers and evidence"), wide: true, message: `<table class="table table-bordered"><thead><tr><th>${__("Question")}</th><th>${__("Customer")}</th><th>${__("Reviewer")}</th><th>${__("Comment")}</th><th>${__("Evidence")}</th></tr></thead><tbody>${rows}</tbody></table>` });
      });
    });
    frm.set_intro(__("Status changes only through the Review buttons. Customer answers are frozen after submit; use Reviewer option to adjust."), "blue");
  },
});
