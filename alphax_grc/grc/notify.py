"""Email helpers. Every send is wrapped so a missing outgoing email account never breaks a user action."""
import time

import frappe
from frappe import _
from frappe.utils import get_url

STRINGS = {
    "en": {
        "greeting": "Hello {name},",
        "signoff": "{provider}",
        "code_subject": "Your verification code",
        "code_body": "Your verification code is <b style='font-size:20px;letter-spacing:3px'>{code}</b>. It expires in {minutes} minutes. If you did not request it, ignore this email.",
        "exists_subject": "You already have an account",
        "exists_body": "Someone tried to register this email address, but an account already exists. Sign in here: <a href='{url}'>{url}</a>. If this was not you, ignore this email.",
        "invite_subject": "{org} invited you to {platform}",
        "invite_body": "{inviter} invited you to join <b>{org}</b> on {platform} as <b>{role}</b>. Open this link to accept (valid for {days} days): <a href='{url}'>{url}</a>",
        "submitted_subject": "Assessment submitted: {title}",
        "submitted_body": "Your assessment <b>{title}</b> was submitted. The GRC team will review it. You will receive a message if clarification is needed.",
        "clarify_subject": "Clarification needed: {title}",
        "clarify_body": "The reviewer asked for clarification on <b>{title}</b>:<br><br><i>{note}</i><br><br>Sign in to reply and resubmit: <a href='{url}'>{url}</a>",
        "released_subject": "Your report is ready: {title}",
        "released_body": "The approved report for <b>{title}</b> is now available. Final level: <b>{level}</b> ({score}%). Sign in to view the scorecard and download the PDF: <a href='{url}'>{url}</a>",
        "reminder_subject": "Reminder: {title}",
        "reminder_body": "{message}<br><br>Continue here: <a href='{url}'>{url}</a>",
        "reminder_default_before": "Your assessment <b>{title}</b> is due on {due} ({days} day(s) left).",
        "reminder_default_overdue": "Your assessment <b>{title}</b> was due on {due} and is overdue.",
        "reminder_default_sla": "A clarification request on <b>{title}</b> is waiting for your reply.",
        "staff_submitted_subject": "Assessment submitted by {org}: {title}",
        "staff_submitted_body": "{org} submitted <b>{title}</b> ({name}). Open it: <a href='{url}'>{url}</a>",
        "manual_reminder": "{message}",
        "msg_subject": "New message from the GRC team",
        "msg_body": "The GRC team wrote to you:<br><br><i>{body}</i><br><br>Reply in the portal: <a href='{url}'>{url}</a>",
        "staff_msg_subject": "New customer message from {org}",
        "staff_change_subject": "Change request from {org}",
        "staff_msg_body": "{name} ({org}) wrote:<br><br><i>{body}</i><br><br>Open it: <a href='{url}'>{url}</a>",
        "consult_subject": "New consultation request from {name}",
        "consult_body": "{name} ({email}, {phone}) from {org} asked for a consultation:<br><br>{message}",
    },
    "ar": {
        "greeting": "مرحباً {name}،",
        "signoff": "{provider}",
        "code_subject": "رمز التحقق الخاص بك",
        "code_body": "رمز التحقق الخاص بك هو <b style='font-size:20px;letter-spacing:3px'>{code}</b>. تنتهي صلاحيته خلال {minutes} دقيقة. إذا لم تطلبه فتجاهل هذه الرسالة.",
        "exists_subject": "لديك حساب مسبقاً",
        "exists_body": "حاول شخص ما تسجيل هذا البريد الإلكتروني، لكن يوجد حساب مسبقاً. سجّل الدخول من هنا: <a href='{url}'>{url}</a>. وإذا لم تكن أنت فتجاهل هذه الرسالة.",
        "invite_subject": "دعتك {org} إلى {platform}",
        "invite_body": "دعاك {inviter} للانضمام إلى <b>{org}</b> على {platform} بدور <b>{role}</b>. افتح الرابط التالي للقبول (صالح لمدة {days} أيام): <a href='{url}'>{url}</a>",
        "submitted_subject": "تم إرسال التقييم: {title}",
        "submitted_body": "تم إرسال تقييمكم <b>{title}</b>. سيقوم فريق الحوكمة بمراجعته، وستصلكم رسالة إذا لزم توضيح.",
        "clarify_subject": "مطلوب توضيح: {title}",
        "clarify_body": "طلب المراجع توضيحاً بشأن <b>{title}</b>:<br><br><i>{note}</i><br><br>سجّلوا الدخول للرد وإعادة الإرسال: <a href='{url}'>{url}</a>",
        "released_subject": "تقريركم جاهز: {title}",
        "released_body": "أصبح التقرير المعتمد الخاص بـ <b>{title}</b> متاحاً. المستوى النهائي: <b>{level}</b> ({score}%). سجّلوا الدخول لعرض بطاقة الأداء وتنزيل ملف PDF: <a href='{url}'>{url}</a>",
        "reminder_subject": "تذكير: {title}",
        "reminder_body": "{message}<br><br>تابعوا من هنا: <a href='{url}'>{url}</a>",
        "reminder_default_before": "موعد تسليم تقييمكم <b>{title}</b> هو {due} (متبقي {days} يوم).",
        "reminder_default_overdue": "كان موعد تسليم تقييمكم <b>{title}</b> في {due} وقد تجاوز الموعد.",
        "reminder_default_sla": "يوجد طلب توضيح على <b>{title}</b> بانتظار ردكم.",
        "staff_submitted_subject": "تقييم مُرسل من {org}: {title}",
        "staff_submitted_body": "أرسلت {org} التقييم <b>{title}</b> ({name}). افتحه: <a href='{url}'>{url}</a>",
        "manual_reminder": "{message}",
        "msg_subject": "رسالة جديدة من فريق الحوكمة",
        "msg_body": "كتب لكم فريق الحوكمة:<br><br><i>{body}</i><br><br>للرد من خلال البوابة: <a href='{url}'>{url}</a>",
        "consult_subject": "طلب استشارة جديد من {name}",
        "consult_body": "طلب {name} ({email}, {phone}) من {org} استشارة:<br><br>{message}",
    },
}


def tr(key, lang="en", **kw):
    lang = lang if lang in STRINGS else "en"
    s = STRINGS[lang].get(key) or STRINGS["en"].get(key) or key
    try:
        return s.format(**kw)
    except (KeyError, IndexError):
        return s


def site_url():
    try:
        u = frappe.db.get_single_value("GRC Settings", "public_site_url")
    except Exception:
        u = None
    return (u or get_url()).rstrip("/")


def portal_url(path=""):
    return site_url() + "/grc" + path


def provider_name():
    try:
        return frappe.db.get_single_value("GRC Settings", "provider_name") or "IRSAA Business Solutions"
    except Exception:
        return "IRSAA Business Solutions"


def platform_name():
    try:
        return frappe.db.get_single_value("GRC Settings", "platform_name") or "AlphaX GRC & Audit Platform"
    except Exception:
        return "AlphaX GRC & Audit Platform"


def _wrap(lang, name, body):
    rtl = lang == "ar"
    greeting = tr("greeting", lang, name=frappe.utils.escape_html(name or ""))
    sign = tr("signoff", lang, provider=frappe.utils.escape_html(provider_name()))
    return (
        "<div style='font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#13232F;max-width:560px;direction:%s;text-align:%s'>"
        "<p>%s</p><p>%s</p><p style='color:#586976'>%s</p></div>" % ("rtl" if rtl else "ltr", "right" if rtl else "left", greeting, body, sign)
    )


def send(recipients, subject, body, lang="en", name="", reference=None, now=False):
    """Queue an email. Returns True if queued, False otherwise. Never raises."""
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [r for r in dict.fromkeys(recipients or []) if r]
    if not recipients:
        return False
    try:
        kwargs = {"recipients": recipients, "subject": subject, "message": _wrap(lang, name, body)}
        if now:
            kwargs["now"] = True
        if reference:
            kwargs["reference_doctype"], kwargs["reference_name"] = reference
        started = time.time()
        frappe.sendmail(**kwargs)
        took = time.time() - started
        if now and took > 5:
            frappe.log_error(title="GRC email slow", message="Sending to %s took %.1f s. Check the outgoing mail server." % (", ".join(recipients), took))
        return True
    except frappe.OutgoingEmailError:
        return False  # no outgoing email account yet: expected on a fresh site, not an error
    except Exception:
        frappe.log_error(title="GRC email could not be queued", message=frappe.get_traceback())
        return False


def has_outgoing_email():
    try:
        from frappe.email.doctype.email_account.email_account import EmailAccount
        return bool(EmailAccount.find_outgoing(match_by_email=None, _raise_error=False))
    except Exception:
        return False


def optional_recipients(organization, emails):
    """Drop people who switched off optional emails (reminders, status updates), personally or for their organization.
    Verification codes, invitations and clarification requests never go through this filter."""
    if not emails:
        return []
    if not frappe.db.get_value("GRC Organization", organization, "notify_reminders"):
        return []
    off = set(frappe.get_all("GRC Organization Member", filters={"organization": organization, "notify_email": 0}, pluck="user"))
    return [e for e in emails if e not in off]


def org_admin_emails(organization):
    return [r.user for r in frappe.get_all(
        "GRC Organization Member", filters={"organization": organization, "status": "Active", "member_role": "Org Admin"}, fields=["user"])]


def staff_notification_recipients():
    emails = []
    s = frappe.db.get_single_value("GRC Settings", "staff_notification_email")
    if s:
        emails.append(s)
    return emails


def user_language(user, default="en"):
    lang = frappe.db.get_value("User", user, "language") or default
    return "ar" if str(lang).lower().startswith("ar") else "en"
