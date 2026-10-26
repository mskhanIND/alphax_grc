import json

import frappe
from frappe.tests.utils import FrappeTestCase

from alphax_grc.api import portal
from alphax_grc.grc import workflow
from alphax_grc.tests.test_flow import mk_org, mk_user


def _submitted(u, label):
    mk_org(label, u)
    frappe.set_user(u)
    name = portal.start_assessment()
    codes = [q["question_code"] for q in portal.get_assessment(name)["snapshot"]["questions"]]
    portal.save_answers(name, [{"question_code": c, "selected_option": "C"} for c in codes])
    portal.submit_assessment(name)
    return name


class TestV04(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def test_list_organizations_counts(self):
        u = mk_user("lo@x.test"); o1 = mk_org("LO One", u)
        frappe.set_user(u)
        portal.create_organization({"legal_name": "LO Two", "sector": "Insurance"})
        portal.start_assessment()
        rows = portal.list_organizations()
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(1 for r in rows if r["active"]), 1)
        self.assertEqual(max(r["assessments"] for r in rows), 1)

    def test_messages_both_ways_and_isolation(self):
        u = mk_user("m1@x.test"); v = mk_user("m2@y.test")
        mk_org("Msg A", u); mk_org("Msg B", v)
        frappe.set_user(u)
        portal.send_message("Hello team")
        frappe.set_user("Administrator")
        org = frappe.db.get_value("GRC Organization Member", {"user": u}, "organization")
        frappe.get_doc({"doctype": "GRC Message", "organization": org, "body": "Hi, how can we help?"}).insert()
        frappe.set_user(u)
        self.assertEqual(portal.get_context()["unread_messages"], 1)
        rows = portal.list_messages()
        self.assertEqual([r["sender_type"] for r in rows], ["Customer", "Staff"])
        self.assertEqual(rows[1]["sender_name"], "GRC team")  # staff names are not shown to customers
        self.assertEqual(portal.get_context()["unread_messages"], 0)
        frappe.set_user(v)
        self.assertEqual(portal.list_messages(), [])

    def test_change_request_and_return_for_edit(self):
        u = mk_user("cr@x.test")
        name = _submitted(u, "CR Co")
        portal.request_change(name, "Q3 is wrong")
        self.assertTrue(frappe.db.exists("GRC Message", {"assessment": name, "kind": "Change Request"}))
        frappe.set_user("Administrator")
        doc = frappe.get_doc("GRC Assessment", name)
        workflow.request_clarification(doc, "Administrator", "Admin", [{"question_code": "", "message": "Please correct Q3"}])
        frappe.set_user(u)
        self.assertTrue(portal.get_assessment(name)["editable"])
        with self.assertRaises(frappe.ValidationError):
            portal.request_change(name, "again")  # no longer submitted

    def test_responses_pdf_and_foreign_access(self):
        u = mk_user("pdf@x.test"); w = mk_user("pdf2@y.test")
        name = _submitted(u, "PDF Co"); mk_org("Other Co", w)
        from alphax_grc.grc import reports
        a = frappe.get_doc("GRC Assessment", name)
        for lang in ("en", "ar"):
            data = reports.responses_pdf(a, lang)
            self.assertTrue(data.startswith(b"%PDF"))
        frappe.set_user(w)
        with self.assertRaises(frappe.DoesNotExistError):
            portal.download_responses(name)

    def test_profile_and_password(self):
        u = mk_user("pw@x.test"); mk_org("PW Co", u)
        frappe.set_user(u)
        portal.update_profile("New Name", "0500000000")
        self.assertEqual(portal.get_context()["full_name"], "New Name")
        with self.assertRaises(frappe.ValidationError):
            portal.change_password("wrong-old", "Str0ng!Passw0rd#1")
        with self.assertRaises(frappe.ValidationError):
            portal.change_password("x", "short")
