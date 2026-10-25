"""Scoring tests. Runs without Frappe:  python3 -m unittest alphax_grc.tests.test_scoring  (from the repo root)."""
import copy
import json
import os
import unittest

from alphax_grc.grc import scoring

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "template_v1.json")


def load_snapshot(**policy):
    with open(DATA) as f:
        d = json.load(f)
    snap = {
        "points": {"A": 25, "B": 50, "C": 75, "D": 100},
        "weighting_method": "Equal",
        "enable_gating": 0,
        "allow_na": 0,
        "bands": d["bands"],
        "sections": d["sections"],
        "questions": d["questions"],
    }
    snap.update(policy)
    return snap


def all_answers(letter):
    return {"Q%d" % i: letter for i in range(1, 21)}


class TestExcelParity(unittest.TestCase):
    """Reference: 20 questions, A=25 B=50 C=75 D=100, overall = points / 2000."""

    def test_question_count_and_max(self):
        snap = load_snapshot()
        self.assertEqual(len(snap["questions"]), 20)
        r = scoring.compute(snap, {})
        self.assertEqual(r["max_points"], 2000)
        self.assertEqual(r["overall_score"], 0.0)
        self.assertEqual(r["maturity_level"], "Critical")

    def test_all_c_is_75_high_boundary(self):
        r = scoring.compute(load_snapshot(), all_answers("C"))
        self.assertEqual(r["overall_points"], 1500)
        self.assertEqual(r["overall_score"], 75.0)
        # 75% is the lower edge of "High" in the Excel (75% - 89%)
        self.assertEqual(r["maturity_level"], "High")

    def test_band_edges_match_excel(self):
        snap = load_snapshot()
        bands = scoring.sorted_bands(snap)
        for pct, expected in [(0, "Critical"), (34.9, "Critical"), (35, "Low"), (54.9, "Low"), (55, "Medium"),
                              (74.9, "Medium"), (75, "High"), (89.9, "High"), (90, "Leading"), (100, "Leading")]:
            self.assertEqual(scoring.band_for(pct, bands)["level_name"], expected, pct)

    def test_all_a_all_d(self):
        self.assertEqual(scoring.compute(load_snapshot(), all_answers("A"))["overall_score"], 25.0)
        r = scoring.compute(load_snapshot(), all_answers("D"))
        self.assertEqual((r["overall_score"], r["maturity_level"]), (100.0, "Leading"))

    def test_mixed_answers_section_scores(self):
        ans = all_answers("B")
        for q in ("Q1", "Q2", "Q3"):
            ans[q] = "D"  # section 1 = 300/300
        r = scoring.compute(load_snapshot(), ans)
        s1 = r["sections"][0]
        self.assertEqual((s1["points"], s1["max_points"], s1["score_pct"]), (300, 300, 100.0))
        s4 = r["sections"][3]
        self.assertEqual((s4["max_points"], s4["score_pct"]), (400, 50.0))
        # 3*100 + 17*50 = 1150 -> 57.5%
        self.assertEqual(r["overall_points"], 1150)
        self.assertEqual(r["overall_score"], 57.5)
        self.assertEqual(r["maturity_level"], "Medium")

    def test_unanswered_scores_zero(self):
        ans = {"Q%d" % i: "D" for i in range(1, 11)}
        r = scoring.compute(load_snapshot(), ans)
        self.assertEqual(r["overall_score"], 50.0)
        self.assertEqual(r["answered_count"], 10)

    def test_rounding_half_up(self):
        # 3 questions of section 1: 25+25+50 = 100/300 = 33.333 -> 33.3
        ans = {"Q1": "A", "Q2": "A", "Q3": "B"}
        r = scoring.compute(load_snapshot(), ans)
        self.assertEqual(r["sections"][0]["score_pct"], 33.3)


class TestPolicy(unittest.TestCase):
    def test_na_ignored_when_policy_off(self):
        ans = all_answers("C")
        ans["Q20"] = "N/A"
        r = scoring.compute(load_snapshot(allow_na=0), ans)
        self.assertEqual(r["na_count"], 0)
        self.assertEqual(r["max_points"], 2000)
        self.assertEqual(r["overall_points"], 1425)

    def test_na_removes_question_when_policy_on(self):
        snap = load_snapshot(allow_na=1)
        for q in snap["questions"]:
            q["allow_na"] = 1 if q["question_code"] == "Q20" else 0
        ans = all_answers("C")
        ans["Q20"] = "N/A"
        r = scoring.compute(snap, ans)
        self.assertEqual(r["na_count"], 1)
        self.assertEqual(r["max_points"], 1900)
        self.assertEqual(r["overall_score"], 75.0)

    def test_na_not_allowed_on_other_questions(self):
        snap = load_snapshot(allow_na=1)
        for q in snap["questions"]:
            q["allow_na"] = 1 if q["question_code"] == "Q20" else 0
        ans = all_answers("C")
        ans["Q5"] = "N/A"
        r = scoring.compute(snap, ans)
        self.assertEqual(r["na_count"], 0)

    def _gating_snap(self, enabled):
        snap = load_snapshot(enable_gating=enabled)
        for q in snap["questions"]:
            if q["question_code"] == "Q1":
                q["is_gating"], q["gate_trigger"], q["gate_cap_level"] = 1, "A", "Low"
        return snap

    def test_gating_off_no_cap(self):
        ans = all_answers("D")
        ans["Q1"] = "A"
        r = scoring.compute(self._gating_snap(0), ans)
        self.assertEqual(r["maturity_level"], r["score_level"])
        self.assertEqual(r["gating_note"], "")

    def test_gating_on_caps_at_low(self):
        ans = all_answers("D")
        ans["Q1"] = "A"
        r = scoring.compute(self._gating_snap(1), ans)
        self.assertGreater(r["overall_score"], 90)
        self.assertEqual(r["score_level"], "Leading")
        self.assertEqual(r["maturity_level"], "Low")
        self.assertIn("capped at Low", r["gating_note"])
        self.assertTrue(r["gating_note_ar"])

    def test_gating_not_triggered_by_other_answer(self):
        ans = all_answers("D")
        ans["Q1"] = "B"
        r = scoring.compute(self._gating_snap(1), ans)
        self.assertEqual(r["maturity_level"], "Leading")

    def test_section_weights(self):
        snap = load_snapshot(weighting_method="Section Weights")
        for s in snap["sections"]:
            s["weight"] = 2 if s["section_code"] == "S1" else 1
        ans = all_answers("A")
        for q in ("Q1", "Q2", "Q3"):
            ans[q] = "D"
        r = scoring.compute(snap, ans)
        # S1=100 (w2), S2..S6=25 (w1 each) -> (200 + 125)/7 = 46.4
        self.assertEqual(r["overall_score"], 46.4)

    def test_custom_points_in_snapshot(self):
        snap = load_snapshot(points={"A": 0, "B": 33, "C": 66, "D": 100})
        r = scoring.compute(snap, all_answers("C"))
        self.assertEqual(r["overall_score"], 66.0)


class TestActionsAndHelpers(unittest.TestCase):
    def test_actions_and_priorities(self):
        ans = all_answers("D")
        ans.update({"Q4": "A", "Q9": "B", "Q12": "C"})
        r = scoring.compute(load_snapshot(), ans)
        by = {a["question_code"]: a for a in r["actions"]}
        self.assertEqual(set(by), {"Q4", "Q9", "Q12"})
        self.assertEqual(by["Q4"]["priority"], "Immediate")
        self.assertEqual(by["Q9"]["priority"], "High")
        self.assertEqual(by["Q12"]["priority"], "Medium")
        self.assertTrue(by["Q4"]["is_finding"] and by["Q9"]["is_finding"] and not by["Q12"]["is_finding"])
        self.assertEqual(r["findings_count"], 2)
        self.assertEqual(r["immediate_count"], 1)
        self.assertEqual([a["question_code"] for a in r["actions"]][0], "Q4")
        # recommendation is the next level's wording
        q4 = next(q for q in load_snapshot()["questions"] if q["question_code"] == "Q4")
        self.assertEqual(by["Q4"]["recommended_text"], q4["option_b"])

    def test_effective_option_prefers_reviewer(self):
        self.assertEqual(scoring.effective_option("B", "C"), "C")
        self.assertEqual(scoring.effective_option("B", ""), "B")
        self.assertEqual(scoring.effective_option("", ""), "")

    def test_is_valid_option(self):
        snap = load_snapshot()
        q = snap["questions"][0]
        self.assertTrue(scoring.is_valid_option(q, "A", snap))
        self.assertTrue(scoring.is_valid_option(q, "", snap))
        self.assertFalse(scoring.is_valid_option(q, "E", snap))
        self.assertFalse(scoring.is_valid_option(q, "N/A", snap))

    def test_snapshot_not_mutated(self):
        snap = load_snapshot()
        before = copy.deepcopy(snap)
        scoring.compute(snap, all_answers("C"))
        self.assertEqual(snap, before)


if __name__ == "__main__":
    unittest.main()
