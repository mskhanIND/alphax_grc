import json
import frappe
from frappe.tests.utils import FrappeTestCase
from alphax_grc.api import auth, portal
from alphax_grc.grc import access, workflow


def mk_user(email, role="GRC Customer"):
    if not frappe.db.exists("User", email):
        u = frappe.get_doc(dict(doctype="User", email=email, first_name=email.split("@")[0], user_type="Website User" if role == "GRC Customer" else "System User",
                                send_welcome_email=0, roles=[{"role": role}]))
        u.insert(ignore_permissions=True)
    return email


def mk_org(name, admin):
    org = frappe.get_doc(dict(doctype="GRC Organization", legal_name=name, status="Active")).insert(ignore_permissions=True)
    frappe.get_doc(dict(doctype="GRC Organization Member", user=admin, organization=org.name, member_role="Org Admin", status="Active")).insert(ignore_permissions=True)
    return org.name


class TestFlow(FrappeTestCase):
    def test_full_cycle_and_isolation(self):
        a1, a2 = mk_user("a1@one.test"), mk_user("a2@two.test")
        mk_org("One Co", a1); mk_org("Two Co", a2)
        frappe.set_user(a1)
        name = portal.start_assessment()
        data = portal.get_assessment(name)
        self.assertNotIn("points", json.dumps(data["snapshot"]))
        codes = [q["question_code"] for q in data["snapshot"]["questions"]]
        portal.save_answers(name, [{"question_code": c, "selected_option": "C"} for c in codes])
        # foreign user cannot see it
        frappe.set_user(a2)
        for fn in (portal.get_assessment, portal.get_scorecard):
            with self.assertRaises(frappe.DoesNotExistError):
                fn(name)
        with self.assertRaises(frappe.DoesNotExistError):
            portal.save_answers(name, [])
        # missing and foreign give the same error
        with self.assertRaises(frappe.DoesNotExistError):
            portal.get_assessment("ASM-9999-99999")
        frappe.set_user(a1)
        portal.submit_assessment(name)
        sc = portal.get_scorecard(name)
        self.assertEqual(sc["preliminary"]["overall_score"], 75)
        self.assertIsNone(sc["final"])
        with self.assertRaises(frappe.ValidationError):
            portal.save_answers(name, [{"question_code": codes[0], "selected_option": "A"}])
        # customer has no doctype access
        frappe.set_user(a1)
        self.assertFalse(frappe.has_permission("GRC Assessment", "read"))
        # staff cycle
        frappe.set_user("Administrator")
        doc = frappe.get_doc("GRC Assessment", name)
        workflow.start_review(doc, "Administrator")
        doc.reload()
        workflow.request_clarification(doc, "Administrator", "Admin", [{"question_code": codes[0], "message": "Please explain"}])
        frappe.set_user(a1)
        portal.add_clarification_reply(name, codes[0], "Here is why")
        portal.resubmit_assessment(name)
        frappe.set_user("Administrator")
        doc.reload()
        workflow.start_review(doc, "Administrator")
        doc.reload()
        doc.answers[0].reviewer_option = "B"
        doc.save()
        workflow.approve(doc, "Administrator")
        doc.reload()
        self.assertLess(doc.final_score, 75)
        frappe.set_user(a1)
        self.assertIsNone(portal.get_scorecard(name)["final"])  # approved but not released

    def test_release_and_pdf(self):
        a1 = mk_user("a3@three.test")
        mk_org("Three Co", a1)
        frappe.set_user(a1)
        name = portal.start_assessment()
        codes = [q["question_code"] for q in portal.get_assessment(name)["snapshot"]["questions"]]
        portal.save_answers(name, [{"question_code": c, "selected_option": "B"} for c in codes])
        portal.submit_assessment(name)
        frappe.set_user("Administrator")
        doc = frappe.get_doc("GRC Assessment", name)
        workflow.start_review(doc, "Administrator"); doc.reload()
        workflow.approve(doc, "Administrator"); doc.reload()
        workflow.release(doc, "Administrator"); doc.reload()
        self.assertEqual(doc.status, "Report Released")
        reps = frappe.get_all("GRC Report", filters={"assessment": name}, fields=["language", "file"])
        self.assertEqual({r.language for r in reps}, {"en", "ar"})
        frappe.set_user(a1)
        self.assertIsNotNone(portal.get_scorecard(name)["final"])
        portal.download_report(name, "ar")
        self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"))

    def test_reminders(self):
        from alphax_grc.grc import tasks
        a1 = mk_user("a4@four.test")
        mk_org("Four Co", a1)
        frappe.set_user(a1)
        name = portal.start_assessment()
        frappe.set_user("Administrator")
        frappe.db.set_value("GRC Assessment", name, "due_date", frappe.utils.add_days(frappe.utils.today(), 3))
        tasks.daily()
        tasks.daily()  # second run the same day must not duplicate
        n = frappe.db.count("GRC Follow Up Log", {"assessment": name})
        self.assertEqual(n, 1)
