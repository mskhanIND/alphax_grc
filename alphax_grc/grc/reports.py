"""PDF reports. Approved reports are generated at release (EN and AR); a Preliminary report can be produced for staff.
Rendering: Jinja HTML -> wkhtmltopdf via frappe.utils.pdf.get_pdf, with the Arabic font embedded as base64."""
import base64
import json
import os

import frappe
from frappe import _
from frappe.utils import formatdate, now_datetime

from alphax_grc.grc import workflow

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "fonts")
_B64 = {}

T = {
    "en": {"title": "Internal Audit Maturity Assessment", "org": "Organization", "date": "Report date", "ref": "Assessment", "overall": "Overall maturity",
           "score": "Overall score", "level": "Maturity level", "sections": "Results by section", "section": "Section", "pct": "Score", "actions": "Recommended actions",
           "priority": "Priority", "area": "Area", "current": "Current state", "target": "Next step", "timeframe": "Timeframe", "owner": "Owner",
           "prelim": "PRELIMINARY - NOT REVIEWED", "disc": "Disclaimer", "answered": "Questions answered", "findings": "Findings", "immediate": "Immediate actions",
           "note": "Note", "none": "No gaps were identified.", "page": "Page"},
    "ar": {"title": "تقييم نضج التدقيق الداخلي", "org": "الجهة", "date": "تاريخ التقرير", "ref": "التقييم", "overall": "مستوى النضج العام",
           "score": "النتيجة الإجمالية", "level": "مستوى النضج", "sections": "النتائج حسب المحور", "section": "المحور", "pct": "النتيجة", "actions": "الإجراءات الموصى بها",
           "priority": "الأولوية", "area": "المجال", "current": "الوضع الحالي", "target": "الخطوة التالية", "timeframe": "الإطار الزمني", "owner": "المسؤول",
           "prelim": "أولي - لم تتم مراجعته", "disc": "إخلاء مسؤولية", "answered": "الأسئلة المجاب عنها", "findings": "الملاحظات", "immediate": "إجراءات فورية",
           "note": "ملاحظة", "none": "لم تُرصد فجوات.", "page": "صفحة"},
}

DEFAULT_DISCLAIMER = {
    "en": "This report is based on the answers provided by the organization and reviewed by the GRC team. It is an advisory assessment, not an audit opinion or assurance engagement. DRAFT wording: to be confirmed by the service provider.",
    "ar": "يستند هذا التقرير إلى الإجابات المقدمة من الجهة بعد مراجعة فريق الحوكمة. وهو تقييم استشاري وليس رأي تدقيق أو مهمة تأكيد. صياغة مبدئية: يؤكدها مزود الخدمة.",
}

CSS = """
@font-face{font-family:'NotoAr';src:url(data:font/ttf;base64,%(reg)s);font-weight:normal}
@font-face{font-family:'NotoAr';src:url(data:font/ttf;base64,%(bold)s);font-weight:bold}
body{font-family:'NotoAr',Arial,sans-serif;font-size:11px;color:#13232F;direction:%(dir)s;text-align:%(align)s}
h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 8px;border-bottom:2px solid #0B5C6B;padding-bottom:4px;color:#0B5C6B}
.meta{color:#586976;margin-bottom:14px}.hero{border:1px solid #D5DDE3;padding:14px;margin:10px 0;overflow:hidden}
.big{font-size:34px;font-weight:bold}.pill{display:inline-block;padding:3px 10px;color:#fff;font-weight:bold}
table{width:100%%;border-collapse:collapse;margin-top:6px;table-layout:fixed}td,th{word-wrap:break-word;word-break:break-word;white-space:normal;line-height:1.8}th{background:#EAF1F4;font-weight:bold}
th,td{border:1px solid #D5DDE3;padding:5px 6px;vertical-align:top;text-align:%(align)s}
.bar{background:#EAF1F4;height:8px;width:100%%}.bar i{display:block;height:8px;background:#0B5C6B}
.wm{color:#B42318;font-weight:bold;border:2px solid #B42318;padding:6px;text-align:center;margin-bottom:10px}
.lb{color:#0B5C6B}.act{border:1px solid #D5DDE3;padding:4px 14px 6px;margin:6px 0;page-break-inside:avoid;line-height:1.8}.ah{border-bottom:1px solid #D5DDE3;padding:2px 0;margin-bottom:4px}.ln{padding:1px 0}.ah{font-weight:bold}.disc{margin-top:24px;color:#586976;font-size:9.5px;border-top:1px solid #D5DDE3;padding-top:8px}
tr{page-break-inside:avoid}
"""


def _font(name):
    if name not in _B64:
        with open(os.path.join(FONT_DIR, name), "rb") as f:
            _B64[name] = base64.b64encode(f.read()).decode()
    return _B64[name]


def _esc(v):
    return frappe.utils.escape_html("" if v is None else str(v))


def render_html(doc, result, lang="en", preliminary=False):
    t = T[lang]
    ar = lang == "ar"
    _e = _esc
    org = frappe.db.get_value("GRC Organization", doc.organization, ["legal_name", "legal_name_ar"], as_dict=True)
    org_name = (org.legal_name_ar if ar and org.legal_name_ar else org.legal_name)
    disc = frappe.db.get_single_value("GRC Settings", "report_disclaimer_ar" if ar else "report_disclaimer_en") or DEFAULT_DISCLAIMER[lang]
    css = CSS % {"reg": _font("NotoSansArabic-Regular.ttf"), "bold": _font("NotoSansArabic-Bold.ttf"), "dir": "rtl" if ar else "ltr", "align": "right" if ar else "left"}
    level = result["maturity_level_ar"] if ar else result["maturity_level"]
    interp = result["interpretation_ar"] if ar else result["interpretation"]
    h = ["<html><head><meta charset='utf-8'><style>%s</style></head><body>" % css]
    if preliminary:
        h.append("<div class='wm'>%s</div>" % t["prelim"])
    h.append("<h1>%s</h1><div class='meta'>%s: %s &nbsp;|&nbsp; %s: %s &nbsp;|&nbsp; %s: %s</div>" % (
        t["title"], t["org"], _e(org_name), t["ref"], _esc(doc.name), t["date"], formatdate(now_datetime().date())))
    h.append("<div class='hero'><div>%s</div><div class='big'>%s%%</div><span class='pill' style='background:%s'>%s</span><p>%s</p>" % (
        t["score"], result["overall_score"], _esc(result.get("color") or "#0B5C6B"), _e(level), _e(interp)))
    note = result["gating_note_ar"] if ar else result["gating_note"]
    if note:
        h.append("<p><span class='lb'>%s:</span> %s</p>" % (t["note"], _e(note)))
    h.append("<p>%s: %s/%s &nbsp; %s: %s &nbsp; %s: %s</p></div>" % (t["answered"], result["answered_count"], result["question_count"], t["findings"], result["findings_count"], t["immediate"], result["immediate_count"]))
    h.append("<h2>%s</h2><table><tr><th>%s</th><th style='width:60px'>%s</th><th style='width:90px'>%s</th><th style='width:110px'></th></tr>" % (t["sections"], t["section"], t["pct"], t["level"]))
    for s in result["sections"]:
        title = s["title_ar"] if ar and s.get("title_ar") else s["title"]
        lv = s["maturity_level_ar"] if ar else s["maturity_level"]
        h.append("<tr><td>%s</td><td>%s%%</td><td>%s</td><td><div class='bar'><i style='width:%s%%'></i></div></td></tr>" % (_e(title), s["score_pct"], _e(lv), min(100, s["score_pct"])))
    h.append("</table><h2>%s</h2>" % t["actions"])
    if not result["actions"]:
        h.append("<p>%s</p>" % t["none"])
    else:
        for a in result["actions"]:
            g = (lambda k: a.get(k + "_ar") if ar and a.get(k + "_ar") else a.get(k))
            h.append("<div class='act'><div class='ah'>%s</div>"
                     "<div class='ln'>%s: %s</div><div class='ln'>%s: %s</div>"
                     "<div class='ln'>%s: %s</div><div class='ln'>%s: %s</div></div>" % (
                _e(g("short_label")), t["priority"], _e(g("priority")) + " / " + _e(g("timeframe")), t["current"], _e(g("current_text")),
                t["target"], _e(g("recommended_text")), t["owner"], _e(g("owner_role"))))
    h.append("<div class='disc'><span class='lb'>%s</span><br>%s</div></body></html>" % (t["disc"], _e(disc)))
    return "".join(h)


def make_pdf(doc, result, lang, preliminary=False):
    """Self-contained HTML (all CSS and fonts inline) straight to wkhtmltopdf, so it does not depend on built Frappe assets."""
    import pdfkit
    html = render_html(doc, result, lang, preliminary)
    opts = {"page-size": "A4", "margin-top": "14mm", "margin-bottom": "14mm", "margin-left": "12mm", "margin-right": "12mm", "encoding": "UTF-8",
            "footer-center": "[page] / [topage]", "footer-font-size": "8", "disable-javascript": "", "quiet": ""}
    try:
        return pdfkit.from_string(html, False, options=opts)
    except OSError as e:
        frappe.throw(_("The PDF engine (wkhtmltopdf) is not available: {0}").format(e))


def _store(doc, pdf, lang, rtype, result, user):
    version = (frappe.db.count("GRC Report", {"assessment": doc.name, "report_type": rtype, "language": lang}) or 0) + 1
    fname = "%s-%s-%s-v%s.pdf" % (doc.name, rtype.lower(), lang, version)
    f = frappe.get_doc({"doctype": "File", "file_name": fname, "attached_to_doctype": "GRC Assessment", "attached_to_name": doc.name,
                        "is_private": 1, "content": pdf, "grc_question_code": ""})
    f.flags.ignore_permissions = True
    f.insert()
    rep = frappe.get_doc({"doctype": "GRC Report", "assessment": doc.name, "organization": doc.organization, "report_type": rtype, "language": lang,
                          "version": version, "score": result["overall_score"], "maturity_level": result["maturity_level"], "file": f.file_url,
                          "generated_on": now_datetime(), "generated_by": user})
    rep.insert(ignore_permissions=True)
    return rep


def generate_approved_reports(doc, user):
    if not doc.final_result:
        frappe.throw(_("The approved result is missing."))
    result = json.loads(doc.final_result)
    out = []
    for lang in ("en", "ar"):
        out.append(_store(doc, make_pdf(doc, result, lang), lang, "Approved", result, user))
    return out


@frappe.whitelist()
def preliminary_report(name, lang="en"):
    """Staff-only watermarked preview built from the customer's selected answers."""
    from alphax_grc.grc import access, scoring
    if not access.is_staff():
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    doc = frappe.get_doc("GRC Assessment", name)
    doc.check_permission("read")
    res = scoring.compute(workflow.snapshot_of(doc), workflow.selected_answers(doc))
    frappe.local.response.filename = "%s-preliminary-%s.pdf" % (name, lang)
    frappe.local.response.filecontent = make_pdf(doc, res, "ar" if lang == "ar" else "en", True)
    frappe.local.response.type = "download"
