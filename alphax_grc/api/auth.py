"""Public registration: email code -> verified token -> password + organization. No user exists before verification.

All guest endpoints are rate limited and never reveal whether an email already has an account.
"""
import hashlib
import hmac
import json
import re
import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, escape_html, validate_email_address

from alphax_grc.grc import access, notify

MAX_CODE_ATTEMPTS = 5
MAX_CODES_PER_HOUR = 5
REG_TOKEN_TTL = 30 * 60
INVITE_DAYS = 7
MAX_ORGS_PER_USER = 25


def _cache():
    c = frappe.cache
    return c() if callable(c) else c


def _h(*parts):
    secret = (frappe.conf.get("encryption_key") or frappe.local.site or "grc").encode()
    return hmac.new(secret, ":".join(parts).encode(), hashlib.sha256).hexdigest()


def clean_email(email):
    email = (email or "").strip().lower()
    if not email or len(email) > 140 or not validate_email_address(email):
        frappe.throw(_("Enter a valid email address."))
    return email


def clean_name(name):
    name = re.sub(r"\s+", " ", (name or "").strip())
    if len(name) < 2 or len(name) > 100:
        frappe.throw(_("Enter your full name."))
    return name


def clean_lang(lang):
    return "ar" if str(lang or "").lower().startswith("ar") else "en"


def _csv(s):
    return [x.strip().lower() for x in (s or "").replace("\n", ",").split(",") if x.strip()]


def check_work_email(email, invited=False):
    s = frappe.get_cached_doc("GRC Settings")
    domain = email.split("@")[-1]
    allowed = _csv(s.allowed_email_domains)
    if allowed and domain not in allowed and not invited:
        frappe.throw(_("Registration is limited to approved company domains. Use your work email address."))
    if cint(s.block_personal_email_domains) and not invited and domain in _csv(s.personal_email_domains):
        frappe.throw(_("Please register with your work email address. Personal email domains are not accepted."))


def password_error(pwd):
    pwd = pwd or ""
    if len(pwd) < 10:
        return _("Use at least 10 characters.")
    if not re.search(r"[A-Za-z]", pwd) or not re.search(r"\d", pwd):
        return _("Use at least one letter and one number.")
    if len(pwd) > 128:
        return _("The password is too long.")
    return None


# ------------------------------------------------------------------ invitations
def hash_token(token):
    return hashlib.sha256((token or "").encode()).hexdigest()


def find_invitation(token):
    """Return a Pending, unexpired invitation for a raw token, or None."""
    if not token or len(token) > 200:
        return None
    name = frappe.db.get_value("GRC Invitation", {"token_hash": hash_token(token)}, "name")
    if not name:
        return None
    inv = frappe.get_doc("GRC Invitation", name)
    if inv.status != "Pending":
        return None
    if inv.expires_on and frappe.utils.get_datetime(inv.expires_on) < frappe.utils.now_datetime():
        frappe.db.set_value("GRC Invitation", inv.name, "status", "Expired")
        return None
    if frappe.db.get_value("GRC Organization", inv.organization, "status") != "Active":
        return None
    return inv


def create_invitation(organization, email, role, invited_by):
    token = secrets.token_urlsafe(32)
    inv = frappe.get_doc({
        "doctype": "GRC Invitation", "organization": organization, "email": email, "member_role": role, "status": "Pending",
        "expires_on": frappe.utils.add_days(frappe.utils.now_datetime(), INVITE_DAYS), "invited_by": invited_by, "token_hash": hash_token(token),
    })
    inv.insert(ignore_permissions=True)
    link = notify.portal_url("?invite=" + token + "#/register")
    return inv, token, link


def accept_invitation_for(user, inv):
    """Create the membership for an existing user and mark the invitation accepted."""
    if frappe.db.exists("GRC Organization Member", {"user": user, "organization": inv.organization, "status": "Active"}):
        frappe.throw(_("This account is already a member of this organization."))
    if len(access.get_memberships(user)) >= MAX_ORGS_PER_USER:
        frappe.throw(_("This account belongs to the maximum number of organizations."))
    frappe.get_doc({
        "doctype": "GRC Organization Member", "user": user, "organization": inv.organization,
        "member_role": inv.member_role, "status": "Active", "invited_by": inv.invited_by,
    }).insert(ignore_permissions=True)
    inv.db_set({"status": "Accepted", "accepted_by": user, "accepted_on": frappe.utils.now_datetime()})


# ------------------------------------------------------------------ guest endpoints
@frappe.whitelist(allow_guest=True)
@rate_limit(limit=30, seconds=3600)
def invitation_info(token):
    inv = find_invitation(token)
    if not inv:
        frappe.throw(_("This invitation is invalid or has expired."))
    org = frappe.db.get_value("GRC Organization", inv.organization, ["legal_name", "legal_name_ar"], as_dict=True)
    return {"email": inv.email, "has_account": bool(frappe.db.exists("User", {"name": inv.email, "enabled": 1})), "role": inv.member_role, "organization": org.legal_name, "organization_ar": org.legal_name_ar or org.legal_name}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=15, seconds=3600)
def register_start(email, full_name, language="en", invite_token=None):
    email = clean_email(email)
    full_name = clean_name(full_name)
    lang = clean_lang(language)
    s = frappe.get_cached_doc("GRC Settings")

    inv = None
    if invite_token:
        inv = find_invitation(invite_token)
        if not inv:
            frappe.throw(_("This invitation is invalid or has expired."))
        if inv.email.strip().lower() != email:
            frappe.throw(_("This invitation was issued to a different email address."))
    check_work_email(email, invited=bool(inv))

    cache = _cache()
    cool_key = "grc:otp:cool:" + _h(email)
    if cache.get_value(cool_key):
        frappe.throw(_("Please wait a minute before requesting another code."))
    cache.set_value(cool_key, 1, expires_in_sec=45)
    count_key = "grc:otp:count:" + _h(email)
    n = cint(cache.get_value(count_key) or 0)
    if n >= MAX_CODES_PER_HOUR:
        frappe.throw(_("Too many verification requests. Try again later."))
    cache.set_value(count_key, n + 1, expires_in_sec=3600)

    sent = True
    code_for_test = None
    if frappe.db.exists("User", {"name": email, "enabled": 1}):
        sent = notify.send(email, notify.tr("exists_subject", lang), notify.tr("exists_body", lang, url=notify.portal_url()), lang, full_name, now=True)
    else:
        code = "%06d" % secrets.randbelow(1000000)
        ttl = max(5, cint(s.verification_code_ttl_minutes) or 15)
        cache.set_value("grc:otp:" + _h(email), {"h": _h(email, code), "attempts": 0, "name": full_name, "lang": lang,
                                                 "invite": invite_token or ""}, expires_in_sec=ttl * 60)
        sent = notify.send(email, notify.tr("code_subject", lang), notify.tr("code_body", lang, code=code, minutes=ttl), lang, full_name, now=True)
        if not sent and cint(s.show_code_when_email_unavailable):
            code_for_test = code
    return {"status": "code_sent", "email_sent": bool(sent), "test_code": code_for_test}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=30, seconds=3600)
def register_verify(email, code):
    email = clean_email(email)
    cache = _cache()
    key = "grc:otp:" + _h(email)
    rec = cache.get_value(key)
    if not rec:
        frappe.throw(_("The code is invalid or has expired. Request a new one."))
    if cint(rec.get("attempts")) >= MAX_CODE_ATTEMPTS:
        cache.delete_value(key)
        frappe.throw(_("Too many attempts. Request a new code."))
    code = re.sub(r"\D", "", code or "")
    if not hmac.compare_digest(rec["h"], _h(email, code)):
        rec["attempts"] = cint(rec.get("attempts")) + 1
        cache.set_value(key, rec, expires_in_sec=15 * 60)
        frappe.throw(_("The code is invalid or has expired. Request a new one."))
    cache.delete_value(key)
    token = secrets.token_urlsafe(24)
    cache.set_value("grc:reg:" + _h(email), {"h": _h(email, token), "name": rec["name"], "lang": rec["lang"], "invite": rec.get("invite", "")},
                    expires_in_sec=REG_TOKEN_TTL)
    return {"reg_token": token, "full_name": rec["name"], "invited": bool(rec.get("invite"))}


ORG_FIELDS = ("legal_name", "legal_name_ar", "sector", "city", "commercial_registration", "website", "primary_contact_name", "primary_contact_email")


def clean_org_values(values):
    if isinstance(values, str):
        values = json.loads(values or "{}")
    values = values or {}
    out = {}
    for k in ORG_FIELDS:
        v = (values.get(k) or "").strip()
        if len(v) > 200:
            frappe.throw(_("{0} is too long.").format(k))
        out[k] = v
    if out.get("primary_contact_email") and not validate_email_address(out["primary_contact_email"]):
        frappe.throw(_("Enter a valid contact email."))
    sectors = frappe.get_meta("GRC Organization").get_field("sector").options.split("\n")
    if out.get("sector") and out["sector"] not in sectors:
        frappe.throw(_("Choose a sector from the list."))
    return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=3600)
def register_complete(email, reg_token, password, organization=None):
    email = clean_email(email)
    cache = _cache()
    key = "grc:reg:" + _h(email)
    rec = cache.get_value(key)
    if not rec or not hmac.compare_digest(rec["h"], _h(email, reg_token or "")):
        frappe.throw(_("Your verification has expired. Please start again."))
    err = password_error(password)
    if err:
        frappe.throw(err)
    if frappe.db.exists("User", email):
        cache.delete_value(key)
        frappe.throw(_("This email cannot be registered. Try signing in."))

    inv = None
    if rec.get("invite"):
        inv = find_invitation(rec["invite"])
        if not inv or inv.email.strip().lower() != email:
            frappe.throw(_("This invitation is invalid or has expired."))
    org_values = None
    if not inv:
        org_values = clean_org_values(organization or {})
        if not org_values.get("legal_name"):
            frappe.throw(_("Enter your organization's legal name."))

    cache.delete_value(key)
    parts = rec["name"].split(" ", 1)
    user = frappe.get_doc({
        "doctype": "User", "email": email, "first_name": parts[0], "last_name": parts[1] if len(parts) > 1 else "",
        "enabled": 1, "user_type": "Website User", "send_welcome_email": 0, "language": rec["lang"], "new_password": password,
        "roles": [{"role": "GRC Customer"}],
    })
    user.flags.ignore_permissions = True
    user.insert()

    if inv:
        accept_invitation_for(email, inv)
    else:
        org = frappe.get_doc(dict(doctype="GRC Organization", status="Active", created_by_user=email, preferred_language=rec["lang"],
                                  primary_contact_name=org_values.get("primary_contact_name") or rec["name"],
                                  primary_contact_email=org_values.get("primary_contact_email") or email,
                                  **{k: v for k, v in org_values.items() if k not in ("primary_contact_name", "primary_contact_email")}))
        org.insert(ignore_permissions=True)
        frappe.get_doc({"doctype": "GRC Organization Member", "user": email, "organization": org.name, "member_role": "Org Admin", "status": "Active"}).insert(ignore_permissions=True)

    frappe.local.login_manager.login_as(email)
    return {"status": "registered", "home": "/grc"}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=3600)
def submit_consultation(full_name, email, message="", phone="", organization_name="", sector="", preferred_language="en", source_page="", company_website=""):
    # honeypot: real visitors never fill the hidden "company_website" field
    if (company_website or "").strip():
        return {"status": "received"}
    email = clean_email(email)
    full_name = clean_name(full_name)
    doc = frappe.get_doc({
        "doctype": "GRC Consultation Request", "full_name": full_name, "email": email, "phone": (phone or "")[:40],
        "organization_name": (organization_name or "")[:140], "sector": (sector or "")[:80], "preferred_language": clean_lang(preferred_language),
        "message": (message or "")[:3000], "source_page": (source_page or "")[:140], "status": "New",
    })
    doc.insert(ignore_permissions=True)
    notify.send(notify.staff_notification_recipients(), notify.tr("consult_subject", "en", name=full_name),
                notify.tr("consult_body", "en", name=escape_html(full_name), email=escape_html(email), phone=escape_html(phone or "-"),
                          org=escape_html(organization_name or "-"), message=escape_html(message or "")), "en")
    return {"status": "received"}


@frappe.whitelist(allow_guest=True)
def site_config():
    s = frappe.get_cached_doc("GRC Settings")
    return {
        "platform_name": s.platform_name, "provider_name": s.provider_name,
        "block_personal_email": bool(cint(s.block_personal_email_domains)),
        "sectors": [x for x in frappe.get_meta("GRC Organization").get_field("sector").options.split("\n") if x],
    }


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=3600)
def request_password_reset(email):
    """Always answers the same way, whether or not the email has an account."""
    email = clean_email(email)
    try:
        if frappe.db.exists("User", {"name": email, "enabled": 1}) and "GRC Customer" in frappe.get_roles(email):
            user = frappe.get_doc("User", email)
            user.flags.ignore_permissions = True
            user.reset_password(send_email=True)
    except Exception:
        frappe.log_error(title="GRC password reset failed", message=frappe.get_traceback())
    return {"status": "requested"}
