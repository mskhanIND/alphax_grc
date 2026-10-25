import json

import frappe
from frappe.tests.utils import FrappeTestCase

from alphax_grc.api import auth, portal
from alphax_grc.grc import access, notify, workflow
from alphax_grc.tests.test_flow import mk_org, mk_user


class TestV02(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def test_multi_org_switch_and_isolation(self):
        u = mk_user("multi@group.test"); other = mk_user("other@else.test")
        o1 = mk_org("Multi One", u); mk_org("Else Co", other)
        frappe.set_user(u)
        ctx = portal.create_organization({"legal_name": "Multi Two", "sector": "Insurance"})
        self.assertEqual(len(ctx["organizations"]), 2)
        o2 = ctx["membership"]["organization"]["name"]  # newly created becomes active
        self.assertNotEqual(o1, o2)
        n2 = portal.start_assessment()
        self.assertEqual(frappe.db.get_value("GRC Assessment", n2, "organization"), o2)
        portal.switch_organization(o1)
        self.assertEqual(portal.list_assessments(), [])  # org 1 has none; org 2's is not mixed in
        with self.assertRaises(frappe.DoesNotExistError):
            portal.get_assessment(n2)  # belongs to the other org of the same user: must switch first
        portal.switch_organization(o2)
        self.assertEqual(portal.get_assessment(n2)["name"], n2)
        frappe.set_user(other)
        with self.assertRaises(frappe.DoesNotExistError):
            portal.switch_organization(o1)

    def test_holding_company_is_read_only_and_released_only(self):
        h = mk_user("holding@group.test"); s = mk_user("sub@group.test")
        ho = mk_org("Holding Co", h); so = mk_org("Sub Co", s)
        frappe.db.set_value("GRC Organization", so, "parent_organization", ho)
        frappe.set_user(s)
        name = portal.start_assessment()
        codes = [q["question_code"] for q in portal.get_assessment(name)["snapshot"]["questions"]]
        portal.save_answers(name, [{"question_code": c, "selected_option": "B"} for c in codes])
        portal.submit_assessment(name)
        frappe.set_user(h)
        ov = portal.group_overview()
        self.assertEqual(ov[0]["organization"], so)
        self.assertIsNone(ov[0]["assessments"][0]["final_score"])
        for fn in (portal.get_assessment, portal.get_activity):
            with self.assertRaises(frappe.DoesNotExistError):
                fn(name)  # no answers or trail of a subsidiary
        with self.assertRaises(frappe.DoesNotExistError):
            portal.get_scorecard(name)  # not released yet
        with self.assertRaises(frappe.DoesNotExistError):
            portal.save_answers(name, [])
        frappe.set_user(s)  # a subsidiary admin sees nothing of the parent
        self.assertEqual(portal.group_overview(), [])

    def test_parent_cycle_blocked(self):
        a = mk_user("cyc@x.test"); o1 = mk_org("Cyc A", a); o2 = mk_org("Cyc B", a)
        frappe.db.set_value("GRC Organization", o2, "parent_organization", o1)
        d = frappe.get_doc("GRC Organization", o1); d.parent_organization = o2
        with self.assertRaises(frappe.ValidationError):
            d.save()

    def test_notification_switches_and_activity(self):
        a = mk_user("n1@notify.test"); b = mk_user("n2@notify.test")
        o = mk_org("Notify Co", a)
        frappe.get_doc(dict(doctype="GRC Organization Member", user=b, organization=o, member_role="Assessor", status="Active")).insert(ignore_permissions=True)
        self.assertEqual(sorted(notify.optional_recipients(o, [a, b])), sorted([a, b]))
        frappe.set_user(b); portal.set_notifications(for_me=0)
        self.assertEqual(notify.optional_recipients(o, [a, b]), [a])
        with self.assertRaises(frappe.PermissionError):
            portal.set_notifications(for_org=0)  # only an Org Admin
        frappe.set_user(a); portal.set_notifications(for_org=0)
        self.assertEqual(notify.optional_recipients(o, [a, b]), [])
        portal.set_notifications(for_org=1)
        name = portal.start_assessment()
        codes = [q["question_code"] for q in portal.get_assessment(name)["snapshot"]["questions"]]
        portal.save_answers(name, [{"question_code": codes[0], "selected_option": "A"}])
        trail = portal.get_activity(name)
        self.assertTrue(any(t["event_type"] == "Answer" for t in trail))
        self.assertTrue(any(t["event_type"] == "Status" for t in trail))

    def test_staff_on_behalf_transfer_and_staff_only_entries(self):
        c = mk_user("cust@behalf.test")
        org = mk_org("Behalf Co", c)
        c1 = mk_user("cons1@grc.test", "GRC Consultant"); c2 = mk_user("cons2@grc.test", "GRC Consultant")
        from alphax_grc.alphax_grc.doctype.grc_assessment import grc_assessment as ga
        frappe.set_user("Administrator")
        name = ga.create_for_organization(org, assigned_consultant=c1)
        frappe.set_user(c1)
        codes = [q["question_code"] for q in json.loads(frappe.db.get_value("GRC Assessment", name, "template_snapshot"))["questions"]]
        self.assertEqual(ga.save_answers_for(name, [{"question_code": codes[0], "selected_option": "C"}]), 1)
        row = frappe.get_doc("GRC Assessment", name).answers[0]
        self.assertEqual(row.answered_by, c1); self.assertEqual(row.answered_by_staff, 1)
        with self.assertRaises(frappe.ValidationError):
            ga.transfer(name, "", assigned_consultant=c2)  # reason required
        ga.transfer(name, "Workload", assigned_consultant=c2)
        self.assertEqual(frappe.db.get_value("GRC Assessment", name, "assigned_consultant"), c2)
        frappe.set_user(c1)
        with self.assertRaises(frappe.PermissionError):
            ga.transfer(name, "x", assigned_consultant=c1)  # no longer assigned, not a manager
        frappe.set_user(c)
        trail = portal.get_activity(name)
        self.assertTrue(all(t["by"] in ("GRC team", "System", "cust") or t["by_type"] != "Staff" or t["by"] == "GRC team" for t in trail))
        self.assertFalse(any("Transferred" in (t["detail"] or "") for t in trail))  # staff-only entry hidden
        self.assertFalse(any(c1 in (t["detail"] or "") for t in trail))

    def test_staff_cannot_be_customer_member(self):
        s = mk_user("stf@grc.test", "GRC Consultant"); o = mk_org("Some Co", mk_user("adm@some.test"))
        d = frappe.get_doc(dict(doctype="GRC Organization Member", user=s, organization=o, member_role="Viewer", status="Active"))
        with self.assertRaises(frappe.ValidationError):
            d.insert(ignore_permissions=True)
