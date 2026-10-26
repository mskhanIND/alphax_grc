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
    if (["Submitted", "Under Review", "Resubmitted"].includes(s)) {
      frm.add_custom_button(__("Return to Customer for Edit"), () => {
        frappe.prompt([{ fieldname: "message", label: __("What should the customer change?"), fieldtype: "Small Text", reqd: 1 }],
          (v) => call("request_clarification", null, JSON.stringify([{ question_code: "", message: v.message }])),
          __("Return to Customer for Edit"));
      }, __("Review"));
    }
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
    const A = "alphax_grc.alphax_grc.doctype.grc_assessment.grc_assessment.";
    const editable = ["Draft", "In Progress", "Clarification Required"].includes(s);
    if (editable) {
      frm.add_custom_button(__("Enter Answers for Customer"), () => {
        frappe.call(A + "get_review_summary", { name: frm.doc.name }).then((r) => {
          const fields = [];
          r.message.answers.forEach((a) => {
            fields.push({ fieldtype: "Select", fieldname: "q_" + a.question_code, label: a.question_code + " " + (a.short_label || ""), options: ["", "A", "B", "C", "D"].join("\n"), default: a.selected_option || "",
              description: ["A", "B", "C", "D"].map((L) => L + ": " + ((a.options || {})[L] || "")).join("  |  ") });
          });
          const d = new frappe.ui.Dialog({ title: __("Enter answers on behalf of the customer"), size: "extra-large", fields,
            primary_action_label: __("Save answers"), primary_action(v) {
              const items = r.message.answers.filter((a) => (v["q_" + a.question_code] || "") !== (a.selected_option || "") && v["q_" + a.question_code])
                .map((a) => ({ question_code: a.question_code, selected_option: v["q_" + a.question_code] }));
              if (!items.length) { d.hide(); return; }
              frappe.call(A + "save_answers_for", { name: frm.doc.name, items: JSON.stringify(items) }).then(() => { d.hide(); frm.reload_doc(); });
            } });
          d.show();
        });
      }, __("On Behalf"));
      if (["In Progress"].includes(s)) add(__("Submit for Customer"), "submit_on_behalf", __("On Behalf"));
    }
    if (frappe.user.has_role(["GRC Manager", "System Manager"]) || [frm.doc.assigned_consultant, frm.doc.reviewer].includes(frappe.session.user)) {
      if (s !== "Report Released") {
        frm.add_custom_button(__("Transfer"), () => {
          frappe.prompt([{ fieldname: "assigned_consultant", label: __("New consultant"), fieldtype: "Link", options: "User", default: frm.doc.assigned_consultant },
                         { fieldname: "reviewer", label: __("New reviewer"), fieldtype: "Link", options: "User", default: frm.doc.reviewer },
                         { fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1 }],
            (v) => frappe.call(A + "transfer", Object.assign({ name: frm.doc.name }, v)).then(() => frm.reload_doc()), __("Transfer assessment"));
        });
      }
    }
    frm.add_custom_button(__("Activity"), () => frappe.set_route("List", "GRC Activity Log", { assessment: frm.doc.name }));
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
