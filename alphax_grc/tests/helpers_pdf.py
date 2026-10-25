import frappe, json
from alphax_grc.grc import reports, scoring, workflow
def sample():
    snap = json.load(open(frappe.get_app_path("alphax_grc","data","template_v1.json")))
    tv = frappe.get_doc("GRC Template Version", frappe.get_all("GRC Template Version", pluck="name")[0])
    s = tv.get_snapshot()
    ans = {q["question_code"]: "ABCD"[i % 4] for i, q in enumerate(s["questions"])}
    res = scoring.compute(s, ans)
    org = frappe.get_doc(dict(doctype="GRC Organization", legal_name="Al Noor Holding", legal_name_ar="شركة النور القابضة", status="Active")).insert(ignore_permissions=True)
    class D: name="ASM-2026-00001"; organization=org.name
    for lang in ("en","ar"):
        open("/tmp/sample_%s.pdf" % lang, "wb").write(reports.make_pdf(D, res, lang))
    frappe.db.rollback()
