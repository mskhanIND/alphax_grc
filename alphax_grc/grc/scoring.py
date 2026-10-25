"""Server-side scoring for GRC assessments.

Pure Python (no frappe import) so it can be unit tested anywhere. Ported from the prototype's
src/utils/scoring.ts and checked against the 20-question Excel reference.

The `snapshot` is the frozen copy of a template version taken when an assessment is created:

    {
      "points": {"A": 25, "B": 50, "C": 75, "D": 100},
      "weighting_method": "Equal" | "Section Weights",
      "enable_gating": 0 | 1,
      "allow_na": 0 | 1,
      "bands": [{level_name, level_name_ar, min_score, max_score, color, interpretation, interpretation_ar}],
      "sections": [{section_code, title, title_ar, reference, reference_ar, weight, owner_role, owner_role_ar}],
      "questions": [{question_code, section_code, short_label, question_text, option_a..d (+_ar),
                     allow_na, is_gating, gate_trigger, gate_cap_level}]
    }

`answers` is a dict {question_code: "A" | "B" | "C" | "D" | "N/A" | ""}.
"""

LETTERS = ("A", "B", "C", "D")
LEVEL_NAMES = {"A": "Ad hoc", "B": "Foundational", "C": "Established", "D": "Leading", "N/A": "Not applicable"}
LEVEL_NAMES_AR = {"A": "ارتجالي", "B": "تأسيسي", "C": "راسخ", "D": "رائد", "N/A": "لا ينطبق"}
LETTER_AR = {"A": "أ", "B": "ب", "C": "ج", "D": "د", "N/A": "لا ينطبق"}

PRIORITY = {
    "A": {"priority": "Immediate", "priority_ar": "فوري", "timeframe": "0–3 months", "timeframe_ar": "من 0 إلى 3 أشهر", "days": 90},
    "B": {"priority": "High", "priority_ar": "مرتفع", "timeframe": "3–6 months", "timeframe_ar": "من 3 إلى 6 أشهر", "days": 180},
    "C": {"priority": "Medium", "priority_ar": "متوسط", "timeframe": "6–12 months", "timeframe_ar": "من 6 إلى 12 شهراً", "days": 365},
}

DEFAULT_POINTS = {"A": 25.0, "B": 50.0, "C": 75.0, "D": 100.0}


def _truthy(v):
    return bool(int(v)) if isinstance(v, (int, float, str)) and str(v).strip() not in ("", "None") else bool(v)


def _round1(x):
    return round(x * 10 + 1e-9) / 10 if x >= 0 else round(x * 10) / 10


def band_for(pct, bands):
    """Highest band whose min_score <= pct (bands sorted ascending by min_score)."""
    chosen = bands[0]
    for band in bands:
        if pct + 1e-9 >= float(band["min_score"]):
            chosen = band
    return chosen


def band_index(level_name, bands):
    name = (level_name or "").strip().lower()
    for i, b in enumerate(bands):
        if b["level_name"].strip().lower() == name:
            return i
    return None


def sorted_bands(snapshot):
    return sorted(snapshot["bands"], key=lambda b: float(b["min_score"]))


def points_map(snapshot):
    p = snapshot.get("points") or {}
    return {k: float(p.get(k, DEFAULT_POINTS[k])) for k in LETTERS}


def option_text(question, letter, lang="en"):
    key = "option_%s" % letter.lower()
    if lang == "ar":
        return question.get(key + "_ar") or question.get(key) or ""
    return question.get(key) or ""


def effective_option(selected, reviewer_option=None):
    """The reviewer's adjusted answer wins when present."""
    return (reviewer_option or "").strip() or (selected or "").strip()


def normalise_answer(question, option, snapshot):
    """Return the option if it is usable under the snapshot policy, else ''.
    N/A only counts when the policy allows it AND the question permits it."""
    opt = (option or "").strip()
    if opt in LETTERS:
        return opt
    if opt == "N/A" and _truthy(snapshot.get("allow_na")) and _truthy(question.get("allow_na")):
        return "N/A"
    return ""


def is_valid_option(question, option, snapshot):
    return normalise_answer(question, option, snapshot) != "" or (option or "").strip() == ""


def compute(snapshot, answers, scored_only_from_answers=True):
    """Score a set of answers against a frozen snapshot. Returns a JSON-serialisable dict."""
    bands = sorted_bands(snapshot)
    pts = points_map(snapshot)
    max_pt = max(pts.values())
    questions = snapshot["questions"]
    gating_on = _truthy(snapshot.get("enable_gating"))

    sec_rows = {}
    for s in snapshot["sections"]:
        sec_rows[s["section_code"]] = {
            "section_code": s["section_code"],
            "title": s.get("title") or s.get("section_title") or "",
            "title_ar": s.get("title_ar") or s.get("section_title_ar") or "",
            "reference": s.get("reference") or "",
            "reference_ar": s.get("reference_ar") or "",
            "owner_role": s.get("owner_role") or "",
            "owner_role_ar": s.get("owner_role_ar") or "",
            "weight": float(s.get("weight") or 1.0),
            "answered": 0,
            "applicable": 0,
            "points": 0.0,
            "max_points": 0.0,
        }

    answered = na = findings = immediate = 0
    total_pts = total_max = 0.0
    gate_hits = []
    actions = []

    for q in questions:
        code = q["question_code"]
        sec = sec_rows.get(q["section_code"])
        opt = normalise_answer(q, answers.get(code), snapshot)

        if opt == "":
            # unanswered: counts toward the maximum (scores zero), same as the Excel reference
            total_max += max_pt
            if sec:
                sec["applicable"] += 1
                sec["max_points"] += max_pt
            continue

        answered += 1
        if opt == "N/A":
            na += 1
            continue

        p = pts[opt]
        total_pts += p
        total_max += max_pt
        if sec:
            sec["answered"] += 1
            sec["applicable"] += 1
            sec["points"] += p
            sec["max_points"] += max_pt

        if opt in ("A", "B"):
            findings += 1
        if opt == "A":
            immediate += 1

        if opt != "D":
            nxt = LETTERS[LETTERS.index(opt) + 1]
            pr = PRIORITY[opt]
            actions.append({
                "question_code": code,
                "section_code": q["section_code"],
                "short_label": q.get("short_label") or "",
                "short_label_ar": q.get("short_label_ar") or "",
                "current_option": opt,
                "current_text": option_text(q, opt),
                "current_text_ar": option_text(q, opt, "ar"),
                "recommended_text": option_text(q, nxt),
                "recommended_text_ar": option_text(q, nxt, "ar"),
                "priority": pr["priority"], "priority_ar": pr["priority_ar"],
                "timeframe": pr["timeframe"], "timeframe_ar": pr["timeframe_ar"],
                "days": pr["days"],
                "is_finding": opt in ("A", "B"),
                "owner_role": (sec or {}).get("owner_role", ""),
                "owner_role_ar": (sec or {}).get("owner_role_ar", ""),
            })

        if gating_on and _truthy(q.get("is_gating")) and q.get("gate_cap_level"):
            trig = (q.get("gate_trigger") or "A").strip()
            letters = {"A", "B"} if trig == "A or B" else {"A"}
            if opt in letters:
                gate_hits.append((code, q.get("short_label") or "", opt, q["gate_cap_level"], q.get("short_label_ar") or ""))

    sections = []
    for code, sec in sec_rows.items():
        mx = sec["max_points"]
        pct = _round1(sec["points"] / mx * 100) if mx else 0.0
        sec["score_pct"] = pct
        if mx:
            b = band_for(pct, bands)
            sec["maturity_level"], sec["maturity_level_ar"], sec["color"] = b["level_name"], b.get("level_name_ar") or b["level_name"], b.get("color") or ""
        else:
            sec["maturity_level"] = sec["maturity_level_ar"] = "N/A"
            sec["color"] = ""
        sections.append(sec)

    if snapshot.get("weighting_method") == "Section Weights":
        scored = [s for s in sections if s["max_points"] > 0 and s["weight"] > 0]
        wsum = sum(s["weight"] for s in scored)
        overall = _round1(sum(s["score_pct"] * s["weight"] for s in scored) / wsum) if wsum else 0.0
    else:
        overall = _round1(total_pts / total_max * 100) if total_max else 0.0

    score_band = band_for(overall, bands)
    final_band = score_band
    gating_note = gating_note_ar = ""
    if gate_hits:
        score_idx = band_index(score_band["level_name"], bands)
        cap_idx, trig_hit = None, None
        for hit in gate_hits:
            idx = band_index(hit[3], bands)
            if idx is not None and (cap_idx is None or idx < cap_idx):
                cap_idx, trig_hit = idx, hit
        if cap_idx is not None and score_idx is not None and score_idx > cap_idx:
            final_band = bands[cap_idx]
            gating_note = ("Overall level capped at %s because gating question %s (%s) was answered %s. "
                           "The score alone would indicate %s.") % (final_band["level_name"], trig_hit[0], trig_hit[1], trig_hit[2], score_band["level_name"])
            gating_note_ar = ("تم تحديد المستوى العام عند «%s» لأن السؤال الحاكم %s (%s) أُجيب عنه بالمستوى (%s). ولولا ذلك لأشارت النتيجة إلى المستوى «%s».") % (
                final_band.get("level_name_ar") or final_band["level_name"], trig_hit[0], trig_hit[4] or trig_hit[1],
                LETTER_AR.get(trig_hit[2], trig_hit[2]), score_band.get("level_name_ar") or score_band["level_name"])

    ranked = sorted([s for s in sections if s["max_points"] > 0], key=lambda s: s["score_pct"], reverse=True)
    actions.sort(key=lambda a: (a["days"], a["question_code"]))

    return {
        "sections": sections,
        "overall_score": overall,
        "overall_points": total_pts,
        "max_points": total_max,
        "score_level": score_band["level_name"],
        "maturity_level": final_band["level_name"],
        "maturity_level_ar": final_band.get("level_name_ar") or final_band["level_name"],
        "color": final_band.get("color") or "",
        "interpretation": final_band.get("interpretation") or "",
        "interpretation_ar": final_band.get("interpretation_ar") or "",
        "gating_note": gating_note,
        "gating_note_ar": gating_note_ar,
        "answered_count": answered,
        "question_count": len(questions),
        "na_count": na,
        "findings_count": findings,
        "immediate_count": immediate,
        "strongest_section": ranked[0]["section_code"] if ranked else "",
        "weakest_section": ranked[-1]["section_code"] if ranked else "",
        "actions": actions,
    }
