/* AlphaX GRC customer portal. No build step. Hash routing, EN/AR with RTL. */
(function () {
  "use strict";
  var API = "/api/method/alphax_grc.api.";
  var S = { lang: "en", ctx: null, cfg: null, reg: {}, asm: null, sec: 0, saveTimer: null, pending: {}, saving: false };
  try { var sl = localStorage.getItem("grc_lang"); S.lang = sl || (((navigator.language || "").toLowerCase().indexOf("ar") === 0) ? "ar" : "en"); } catch (e) {}

  // ---------------------------------------------------------------- helpers
  function t(k) { var d = window.GRC_I18N[S.lang]; return (d && d[k] != null) ? d[k] : (window.GRC_I18N.en[k] != null ? window.GRC_I18N.en[k] : k); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function L(o, k) { return (S.lang === "ar" && o[k + "_ar"]) ? o[k + "_ar"] : o[k]; }
  function stLabel(s) { return t("st_" + String(s).replace(/ /g, "_")); }
  function fmtDate(d) { if (!d) return "-"; try { return new Date(d).toLocaleDateString(S.lang === "ar" ? "ar-SA" : "en-GB", { year: "numeric", month: "short", day: "numeric" }); } catch (e) { return d; } }
  function toast(msg, bad) { var el = $("#toast"); el.textContent = msg; el.className = "toast show" + (bad ? " bad" : ""); clearTimeout(toast._t); toast._t = setTimeout(function () { el.className = "toast"; }, 3800); }
  function langSwitch() {
    return '<span class="seg" role="group" aria-label="Language"><button type="button" data-act="lang" data-l="en" aria-pressed="' + (S.lang === "en") + '">EN</button><button type="button" data-act="lang" data-l="ar" aria-pressed="' + (S.lang === "ar") + '">\u0639\u0631\u0628\u064a</button></span>';
  }
  function applyLang() { document.documentElement.lang = S.lang; document.documentElement.dir = S.lang === "ar" ? "rtl" : "ltr"; try { localStorage.setItem("grc_lang", S.lang); } catch (e) {} }

  function serverMessage(r, data) {
    try {
      if (data && data._server_messages) { var m = JSON.parse(data._server_messages); if (m.length) { var o = JSON.parse(m[m.length - 1]); return (o.message || "").replace(/<[^>]+>/g, ""); } }
      if (data && data.exception) { var s = String(data.exception).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim(); var i = s.indexOf(":"); return i > -1 ? s.slice(i + 1).trim() : s; }
    } catch (e) {}
    return null;
  }
  function api(method, args, opts) {
    opts = opts || {};
    var body = new FormData();
    Object.keys(args || {}).forEach(function (k) { var v = args[k]; if (v == null) return; body.append(k, (typeof v === "object" && !(v instanceof Blob)) ? JSON.stringify(v) : v); });
    return fetch(API + method, { method: "POST", headers: { "X-Frappe-CSRF-Token": window.GRC.csrf, "Accept": "application/json" }, body: body, credentials: "same-origin" })
      .then(function (r) {
        return r.text().then(function (txt) {
          var data = {}; try { data = JSON.parse(txt); } catch (e) {}
          if (r.status === 401 || r.status === 403 && !serverMessage(r, data)) { var err = new Error(t("err_session")); err.session = true; throw err; }
          if (!r.ok) { throw new Error(serverMessage(r, data) || t("err_generic")); }
          return data.message;
        });
      });
  }
  function download(method, args) {
    var q = Object.keys(args).map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(args[k]); }).join("&");
    window.location.href = API + method + "?" + q;
  }
  function fail(e) { if (e && e.session) { S.ctx = null; go("#/login"); } toast((e && e.message) || t("err_generic"), true); }

  // ---------------------------------------------------------------- layout
  var NAV = [["dashboard", "dashboard", true], ["assessments", "assessments", true], ["messages", "msgs", true], ["organizations", "my_orgs", true], ["organization", "org_title", true], ["members", "members", true],
             ["actions", "actions", false], ["benchmarks", "benchmarks", false], ["frameworks", "frameworks", false]];
  var ICON = { messages: "M4 5h16v11H9l-5 4zM8 9h8M8 12h5", organizations: "M3 21V9l5-3v15M8 21V4l8 4v13M16 21V11l5 2v8", profile: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 4-7 8-7s8 3 8 7", group: "M3 21V10l6-4v15M9 21V3l12 5v13M13 11h4M13 15h4", dashboard: "M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z", assessments: "M6 2h9l5 5v15H6zM14 2v6h6M9 13h8M9 17h8", organization: "M4 21V8l8-5 8 5v13M9 21v-6h6v6", members: "M16 11a4 4 0 100-8 4 4 0 000 8zM3 21c0-4 3-7 7-7s7 3 7 7", actions: "M9 11l3 3 8-8M4 12v8h14", benchmarks: "M4 20V10M10 20V4M16 20v-8M22 20H2", frameworks: "M12 2l9 5-9 5-9-5zM3 12l9 5 9-5M3 17l9 5 9-5" };
  function icon(n) { return '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' + (ICON[n] || "") + '"/></svg>'; }

  function shell(active, inner) {
    var m = S.ctx && S.ctx.membership;
    if (m) m.unread_n = (S.ctx && S.ctx.unread_messages) || 0;
    var navItems = NAV.slice(); if (m && m.has_subsidiaries) navItems.splice(6, 0, ["group", "group", true]);
    var orgs = (S.ctx && S.ctx.organizations) || [];
    var cur = m ? (S.lang === "ar" && m.organization.legal_name_ar || m.organization.legal_name) : "";
    var switcher = '<div class="orgsw"><small>' + t("switch_org") + (orgs.length > 1 ? " (" + orgs.length + ")" : "") + "</small>" + (orgs.length > 1 ? '<select data-switch="1">' + orgs.map(function (o) { return '<option value="' + esc(o.name) + '"' + (m && o.name === m.organization.name ? " selected" : "") + ">" + esc(S.lang === "ar" && o.legal_name_ar || o.legal_name) + "</option>"; }).join("") + "</select>" : '<div class="orgone">' + esc(cur) + "</div>") + "</div>";
    var nav = navItems.map(function (n) {
      if (!n[2]) return '<span class="nav disabled" aria-disabled="true">' + icon(n[0]) + "<span>" + t(n[1]) + '</span><em>' + t("coming_soon") + "</em></span>";
      return '<a class="nav' + (active === n[0] ? " on" : "") + '" href="#/' + n[0] + '">' + icon(n[0]) + "<span>" + t(n[1]) + "</span>" + (n[0] === "messages" && m && m.unread_n ? '<b class="dot">' + m.unread_n + "</b>" : "") + "</a>";
    }).join("");
    return '<div class="layout"><aside class="side"><div class="brand"><img src="/assets/alphax_grc/images/alphax_icon.png" alt=""><div><b>AlphaX GRC</b><span>GRC &amp; Audit</span></div></div>' + switcher + "<nav>" + nav + "</nav>" +
      '<div class="side-foot"><a class="who" href="#/profile">' + icon("profile") + '<span><strong>' + esc(S.ctx.full_name) + "</strong><small>" + esc(S.ctx.user) + "</small></span></a>" +
      '' + langSwitch() + ' <button class="btn ghost sm" data-act="logout">' + t("signout") + "</button></div></aside>" +
      '<main class="main" id="main">' + inner + '<footer class="foot">' + esc(t("disclaimer")) + "</footer></main></div>";
  }
  function pubShell(inner) {
    return '<div class="auth"><div class="auth-card"><div class="auth-top"><div class="brand dark"><img src="/assets/alphax_grc/images/alphax_icon.png" alt=""><div><b>AlphaX GRC</b><span>GRC &amp; Audit</span></div></div>' +
      '<div><a class="link" href="/grc-home">&larr; ' + (S.lang === "ar" ? "الموقع" : "Website") + '</a> &nbsp; ' + langSwitch() + "</div></div>" + inner + "</div></div>";
  }
  function render(html) { $("#app").innerHTML = html; window.scrollTo(0, 0); }
  function field(id, label, opts) {
    opts = opts || {};
    var c = '<div class="f"><label for="' + id + '">' + label + "</label>";
    if (opts.options) { c += '<select id="' + id + '"><option value="">' + t("choose") + "</option>" + opts.options.map(function (o) { return '<option value="' + esc(o.v) + '"' + (o.v === opts.value ? " selected" : "") + ">" + esc(o.l) + "</option>"; }).join("") + "</select>"; }
    else c += '<input id="' + id + '" type="' + (opts.type || "text") + '" value="' + esc(opts.value || "") + '"' + (opts.ph ? ' placeholder="' + esc(opts.ph) + '"' : "") + (opts.auto ? ' autocomplete="' + opts.auto + '"' : "") + (opts.readonly ? " readonly" : "") + (opts.dir ? ' dir="' + opts.dir + '"' : "") + ">";
    return c + (opts.hint ? '<small class="hint">' + opts.hint + "</small>" : "") + "</div>";
  }
  function val(id) { var el = document.getElementById(id); return el ? el.value.trim() : ""; }
  function busy(btn, on) { if (!btn) return; btn.disabled = on; btn.classList.toggle("busy", on); }

  // ---------------------------------------------------------------- auth screens
  function viewLogin() {
    render(pubShell('<h1>' + t("login_title") + '</h1><form id="f-login" novalidate>' + field("usr", t("email"), { type: "email", auto: "username", dir: "ltr" }) +
      field("pwd", t("password"), { type: "password", auto: "current-password" }) +
      '<button class="btn primary block" type="submit">' + t("signin") + '</button></form><p class="aux"><a class="link" href="#/forgot">' + t("forgot") + "</a></p>" +
      '<p class="aux">' + t("no_account") + ' <a class="link" href="#/register">' + t("register") + "</a></p>"));
    $("#f-login").addEventListener("submit", function (e) {
      e.preventDefault(); var b = $("button[type=submit]", e.target); busy(b, true);
      var fd = new FormData(); fd.append("usr", val("usr")); fd.append("pwd", document.getElementById("pwd").value);
      fetch("/api/method/login", { method: "POST", body: fd, headers: { "X-Frappe-CSRF-Token": window.GRC.csrf, "Accept": "application/json" }, credentials: "same-origin" })
        .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(r.status === 401 ? (S.lang === "ar" ? "بيانات الدخول غير صحيحة." : "Incorrect email or password.") : (serverMessage(r, d) || t("err_generic"))); }); })
        .then(function () { var tok = (new URLSearchParams(window.location.search)).get("invite"); window.location.href = "/grc" + (tok ? "?invite=" + encodeURIComponent(tok) : ""); })
        .catch(function (err) { busy(b, false); toast(err.message, true); });
    });
  }

  function viewRegister() {
    var inv = (new URLSearchParams(window.location.search)).get("invite") || "";
    var step = S.reg.step || 1;
    var steps = [t("step_details"), t("step_verify"), t("step_org")];
    var bar = '<ol class="steps">' + steps.map(function (s, i) { return '<li class="' + (i + 1 === step ? "on" : i + 1 < step ? "done" : "") + '"><i>' + (i + 1) + "</i>" + s + "</li>"; }).join("") + "</ol>";
    var body = "";
    if (S.reg.invite) body += '<p class="note">' + t("invited_to") + " <b>" + esc(S.lang === "ar" ? S.reg.invite.organization_ar : S.reg.invite.organization) + "</b> (" + esc(t("r_" + S.reg.invite.role.replace(/ /g, "_"))) + ")</p>";
    if (S.reg.invite && S.reg.invite.has_account) {
      render(pubShell("<h1>" + t("register_title") + "</h1>" + body + '<p class="note warn">' + t("invite_has_account") + '</p><a class="btn primary block" href="#/login">' + t("signin") + "</a>")); return;
    }
    if (step === 1) {
      body += '<p class="note">' + t("have_account") + ' <a class="link" href="#/login"><b>' + t("signin") + '</b></a> &middot; <a class="link" href="#/forgot">' + t("forgot") + "</a></p>" +
        '<form id="f-r1" novalidate>' + field("r_name", t("full_name"), { value: S.reg.name, auto: "name" }) + field("r_email", t("email"), { type: "email", value: S.reg.email, auto: "email", dir: "ltr", readonly: !!S.reg.invite }) +
        '<button class="btn primary block" type="submit">' + t("send_code") + "</button></form>";
    } else if (step === 2) {
      body += '<p class="note">' + t("code_sent") + " <b dir=\"ltr\">" + esc(S.reg.email) + "</b></p><p class=\"muted\"><small>" + t("code_help") + "</small></p>" + (S.reg.test_code ? '<p class="note warn">' + t("test_code") + ": <b dir=\"ltr\">" + esc(S.reg.test_code) + "</b></p>" : "") +
        '<form id="f-r2" novalidate>' + field("r_code", t("code"), { auto: "one-time-code", dir: "ltr", ph: "123456" }) + '<button class="btn primary block" type="submit">' + t("verify") + "</button></form>" +
        '<p class="aux"><button class="link" id="resend" data-act="resend" disabled>' + t("resend") + '</button> &middot; <a class="link" href="#/login">' + t("signin") + '</a> &middot; <button class="link" data-act="reg-back">' + t("back") + "</button></p>";
    } else {
      var sectors = (S.cfg && S.cfg.sectors || []).map(function (s) { return { v: s, l: s }; });
      body += '<form id="f-r3" novalidate>' + (S.reg.invite ? "" : '<h2>' + t("org_details") + "</h2>" + '<div class="grid2">' + field("o_legal", t("legal_name"), { dir: "ltr" }) + field("o_legal_ar", t("legal_name_ar"), { dir: "rtl" }) +
        field("o_sector", t("sector"), { options: sectors }) + field("o_city", t("city")) + field("o_cr", t("cr"), { dir: "ltr" }) + field("o_web", t("website"), { dir: "ltr" }) + "</div>") +
        field("r_pwd", t("password"), { type: "password", auto: "new-password", hint: t("pwd_hint") }) + '<button class="btn primary block" type="submit">' + t("create") + "</button></form>";
    }
    render(pubShell("<h1>" + t("register_title") + "</h1>" + bar + body + '<p class="aux">' + t("have_account") + ' <a class="link" href="#/login">' + t("signin") + "</a></p>"));
    var f1 = $("#f-r1"), f2 = $("#f-r2"), f3 = $("#f-r3");
    if (f2) cooldown();
    if (f1) f1.addEventListener("submit", function (e) {
      e.preventDefault(); var b = $("button[type=submit]", f1); busy(b, true); S.reg.name = val("r_name"); S.reg.email = val("r_email");
      api("auth.register_start", { email: S.reg.email, full_name: S.reg.name, language: S.lang, invite_token: inv || null }).then(function (r) { S.reg.step = 2; S.reg.test_code = r.test_code; viewRegister(); }).catch(function (er) { busy(b, false); fail(er); });
    });
    if (f2) f2.addEventListener("submit", function (e) {
      e.preventDefault(); var b = $("button[type=submit]", f2); busy(b, true);
      api("auth.register_verify", { email: S.reg.email, code: val("r_code") }).then(function (r) { S.reg.token = r.reg_token; S.reg.step = 3; viewRegister(); }).catch(function (er) { busy(b, false); fail(er); });
    });
    if (f3) f3.addEventListener("submit", function (e) {
      e.preventDefault(); var b = $("button[type=submit]", f3); busy(b, true);
      var org = S.reg.invite ? null : { legal_name: val("o_legal"), legal_name_ar: val("o_legal_ar"), sector: val("o_sector"), city: val("o_city"), commercial_registration: val("o_cr"), website: val("o_web") };
      api("auth.register_complete", { email: S.reg.email, reg_token: S.reg.token, password: document.getElementById("r_pwd").value, organization: org }).then(function () { S.reg = {}; window.location.href = "/grc"; }).catch(function (er) { busy(b, false); fail(er); });
    });
  }

  function cooldown() {
    var b = $("#resend"); if (!b) return; var left = 45; clearInterval(cooldown._i);
    function tick() { if (!document.getElementById("resend")) { clearInterval(cooldown._i); return; } b.disabled = left > 0; b.textContent = left > 0 ? t("resend") + " (" + left + ")" : t("resend"); left--; }
    tick(); cooldown._i = setInterval(tick, 1000);
  }

  function viewForgot() {
    render(pubShell("<h1>" + t("forgot_title") + '</h1><p class="muted">' + t("forgot_text") + '</p><form id="f-forgot" novalidate>' + field("fg_email", t("email"), { type: "email", auto: "username", dir: "ltr" }) +
      '<button class="btn primary block" type="submit">' + t("send_reset") + '</button></form><p class="aux"><a class="link" href="#/login">' + t("signin") + "</a></p>"));
    $("#f-forgot").addEventListener("submit", function (e) {
      e.preventDefault(); var b = $("button[type=submit]", e.target); busy(b, true);
      api("auth.request_password_reset", { email: val("fg_email") }).then(function () { busy(b, false); toast(t("reset_sent")); }).catch(function (er) { busy(b, false); fail(er); });
    });
  }

  // ---------------------------------------------------------------- dashboard & lists
  function badge(s) { return '<span class="badge s-' + String(s).replace(/ /g, "_") + '">' + stLabel(s) + "</span>"; }
  function progress(a, b) { var p = b ? Math.round(a / b * 100) : 0; return '<div class="prog"><i style="width:' + p + '%"></i></div><small>' + a + " / " + b + "</small>"; }

  function viewDashboard() {
    api("portal.dashboard").then(function (d) {
      var m = S.ctx.membership;
      var open = d.open, rel = d.latest_released;
      var h = "<header class=\"ph\"><div><h1>" + t("welcome") + ", " + esc(S.ctx.full_name.split(" ")[0]) + "</h1></div>" +
        (m.can_edit && !open ? '<button class="btn primary" data-act="start">' + t("start_assessment") + "</button>" : "") + "</header>";
      var sc = d.score;
      h += '<div class="kpis"><div class="kpi k1"><small>' + t("kpi_score") + '</small><b>' + (sc && sc.score != null ? Math.round(sc.score * 10) / 10 + "%" : "&ndash;") + '</b><span>' + (sc ? esc(sc.level || "") : t("kpi_none")) + '</span></div>' +
        '<div class="kpi k2"><small>' + t("kpi_active") + '</small><b>' + d.active_count + '</b><span>' + t("assessments") + '</span></div>' +
        '<div class="kpi k3"><small>' + t("kpi_released") + '</small><b>' + d.released_count + '</b><span>' + t("scorecard") + "</span></div></div>";
      h += '<div class="cards">';
      if (open) {
        h += '<section class="card hl"><h3>' + esc(open.title) + "</h3>" + badge(open.status) + '<p class="muted">' + t("na_" + open.next_action) + "</p>" + progress(open.answered, open.total) +
          '<a class="btn primary" href="#/assessments/' + open.name + '">' + t("continue") + "</a></section>";
      }
      if (rel) {
        h += '<section class="card"><h3>' + t("scorecard") + "</h3><p class=\"muted\">" + esc(rel.title) + '</p><a class="btn" href="#/assessments/' + rel.name + '/scorecard">' + t("view") + "</a></section>";
      }
      h += '<section class="card"><h3>' + t("assessments") + '</h3><p class="big">' + d.assessments.length + '</p><a class="link" href="#/assessments">' + t("view") + "</a></section></div>";
      if (!d.assessments.length) h += '<p class="empty">' + t("no_assessments") + "</p>";
      render(shell("dashboard", h));
    }).catch(fail);
  }

  function viewAssessments() {
    api("portal.list_assessments").then(function (rows) {
      var m = S.ctx.membership;
      var hasOpen = rows.some(function (r) { return r.status === "Draft" || r.status === "In Progress"; });
      var h = '<header class="ph"><h1>' + t("assessments") + "</h1>" + (m.can_edit && !hasOpen ? '<button class="btn primary" data-act="start">' + t("start_assessment") + "</button>" : "") + "</header>";
      if (!rows.length) h += '<p class="empty">' + t("no_assessments") + "</p>";
      else h += '<div class="tablewrap"><table class="tbl"><thead><tr><th>' + t("title") + "</th><th>" + t("status") + "</th><th>" + t("progress") + "</th><th>" + t("due") + "</th><th></th></tr></thead><tbody>" +
        rows.map(function (r) {
          var late = r.due_date && new Date(r.due_date) < new Date() && ["Draft", "In Progress", "Clarification Required"].indexOf(r.status) > -1;
          return "<tr><td><b>" + esc(r.title) + "</b><br><small>" + esc(r.name) + "</small></td><td>" + badge(r.status) + "</td><td>" + progress(r.answered, r.total) + "</td><td>" + fmtDate(r.due_date) + (late ? ' <span class="late">' + t("overdue") + "</span>" : "") + "</td>" +
            '<td class="r"><a class="btn sm" href="#/assessments/' + r.name + '">' + (r.editable ? t("continue") : t("open")) + "</a>" + (r.released ? ' <a class="btn sm" href="#/assessments/' + r.name + '/scorecard">' + t("scorecard") + "</a>" : "") + "</td></tr>";
        }).join("") + "</tbody></table></div>";
      render(shell("assessments", h));
    }).catch(fail);
  }

  // ---------------------------------------------------------------- assessment stepper
  var OPTS = ["A", "B", "C", "D"];
  function secQuestions(snap, code) { return snap.questions.filter(function (q) { return q.section_code === code; }); }
  function answeredCount() { var n = 0; S.asm.snapshot.questions.forEach(function (q) { if (S.asm.answers[q.question_code] && S.asm.answers[q.question_code].selected_option) n++; }); return n; }

  function viewAssessment(name) {
    if (!S.asm || S.asm.name !== name) S.sec = 0;
    api("portal.get_assessment", { name: name }).then(function (a) { S.asm = a; S.sec = Math.min(S.sec, a.snapshot.sections.length - 1); S.pending = {}; drawAssessment(); }).catch(function (e) { fail(e); if (!e.session) go("#/assessments"); });
  }

  function setSaveState(k) { var el = $("#savestate"); if (el) { el.textContent = t(k); el.className = "savestate " + k; } }

  function drawAssessment() {
    var a = S.asm, snap = a.snapshot, edit = a.editable;
    var total = snap.questions.length, done = answeredCount();
    var sections = snap.sections.map(function (s, i) {
      var qs = secQuestions(snap, s.section_code), d = qs.filter(function (q) { return (a.answers[q.question_code] || {}).selected_option; }).length;
      return '<li><button class="sec' + (i === S.sec ? " on" : "") + (d === qs.length ? " full" : "") + '" data-sec="' + i + '"><i>' + (i + 1) + "</i><span>" + esc(L(s, "title")) + "</span><em>" + d + "/" + qs.length + "</em></button></li>";
    }).join("");
    var s = snap.sections[S.sec], qs = secQuestions(snap, s.section_code);
    var clar = a.clarifications || [];
    var openReq = clar.filter(function (c) { return c.kind === "Request" && c.status === "Open"; });

    var h = '<header class="ph"><div><a class="link" href="#/assessments">&larr; ' + t("assessments") + "</a><h1>" + esc(S.lang === "ar" && snap.template_name_ar || snap.template_name) + "</h1><div>" + badge(a.status) + ' <small class="muted">' + esc(a.name) + "</small></div></div>" +
      '<div class="ph-r"><button class="btn sm" data-pdf-resp="en">' + t("dl_answers") + ' PDF</button> <button class="btn sm" data-act="activity">' + t("activity") + '</button> <span id="savestate" class="savestate"></span>' + (a.released ? '<a class="btn" href="#/assessments/' + a.name + '/scorecard">' + t("scorecard") + "</a>" : "") + "</div></header>";
    h += '<section class="card" id="activity-box" hidden></section>';
    if (a.can_edit && ["Submitted", "Under Review", "Resubmitted"].indexOf(a.status) > -1) h += '<section class="card"><b>' + t("change_title") + '</b><p class="muted">' + t("change_text") + '</p><textarea id="chg" rows="2" placeholder="' + t("change_ph") + '"></textarea><button class="btn sm primary" data-act="reqchange">' + t("change_send") + "</button></section>";
    h += '<p class="muted"><a class="link" href="#/messages/' + a.name + '">' + t("msg_about") + "</a></p>";
    if (!edit) h += '<p class="note">' + (a.can_edit ? t("readonly") : t("viewer_note")) + "</p>";
    h += '<p class="muted next">' + t("na_" + a.next_action) + "</p>";
    h += '<div class="prog wide"><i style="width:' + Math.round(done / total * 100) + '%"></i></div><small class="muted">' + done + " " + t("of") + " " + total + " " + t("answered") + "</small>";

    if (clar.length) {
      h += '<section class="card clar"><h3>' + t("clar_title") + "</h3>" + clar.map(function (c) {
        var mine = c.author_type === "Customer";
        var reply = (!mine && c.status === "Open" && a.status === "Clarification Required" && a.can_edit) ? '<div class="reply"><textarea id="rp-' + esc(c.name) + '" rows="2" placeholder="' + t("clar_reply") + '"></textarea><button class="btn sm primary" data-reply="' + esc(c.name) + '" data-q="' + esc(c.question_code || "") + '">' + t("send_reply") + "</button></div>" : "";
        return '<div class="msg ' + (mine ? "me" : "them") + '"><small>' + (mine ? t("you") : t("reviewer")) + (c.question_code ? " &middot; " + esc(c.question_code) : " &middot; " + t("general")) + " &middot; " + fmtDate(c.creation) + "</small><p>" + esc(c.message) + "</p>" + reply + "</div>";
      }).join("") + "</section>";
    }

    h += '<div class="work"><ol class="secs" aria-label="' + t("sections") + '">' + sections + "</ol><div class=\"qs\">";
    if (S.sec === 0 && (snap.introduction || snap.answer_rule)) {
      h += '<details class="card intro"><summary>' + t("intro") + "</summary>" + (snap.introduction ? "<p>" + esc(S.lang === "ar" && snap.introduction_ar || snap.introduction) + "</p>" : "") +
        (snap.answer_rule ? "<p><b>" + t("answer_rule") + ":</b> " + esc(S.lang === "ar" && snap.answer_rule_ar || snap.answer_rule) + "</p>" : "") + "</details>";
    }
    h += "<h2>" + esc(L(s, "title")) + "</h2>" + (s.reference ? '<p class="muted ref">' + esc(L(s, "reference")) + "</p>" : "");
    qs.forEach(function (q) {
      var ans = a.answers[q.question_code] || {}, files = a.evidence.filter(function (f) { return f.question_code === q.question_code; });
      h += '<section class="card q" id="q-' + q.question_code + '"><div class="qh"><span class="qc">' + q.question_code + "</span><h3>" + esc(L(q, "short_label")) + "</h3></div><p>" + esc(L(q, "question_text")) + "</p>" +
        '<div class="opts" role="radiogroup" aria-label="' + t("select_option") + '">' + OPTS.map(function (o) {
          var txt = L(q, "option_" + o.toLowerCase()); if (!txt) return "";
          return '<label class="opt' + (ans.selected_option === o ? " on" : "") + '"><input type="radio" name="o-' + q.question_code + '" value="' + o + '"' + (ans.selected_option === o ? " checked" : "") + (edit ? "" : " disabled") + "><i>" + o + "</i><span>" + esc(txt) + "</span></label>";
        }).join("") + ((snap.allow_na && q.allow_na) ? '<label class="opt na' + (ans.selected_option === "N/A" ? " on" : "") + '"><input type="radio" name="o-' + q.question_code + '" value="N/A"' + (ans.selected_option === "N/A" ? " checked" : "") + (edit ? "" : " disabled") + "><i>-</i><span>" + t("na_label") + "</span></label>" : "") + "</div>" +
        '<div class="f"><label>' + t("comment") + '</label><textarea data-cm="' + q.question_code + '" rows="2" maxlength="2000"' + (edit ? "" : " disabled") + ">" + esc(ans.comment || "") + "</textarea></div>" +
        '<div class="ev"><b>' + t("evidence") + "</b> " + (edit ? '<label class="btn sm">' + t("attach") + '<input type="file" class="hide" data-up="' + q.question_code + '"></label>' : "") +
        (files.length ? "<ul>" + files.map(function (f) { return '<li><a href="#" data-dl="' + f.id + '">' + esc(f.file_name) + "</a> <small>" + Math.max(1, Math.round(f.size / 1024)) + " KB</small>" + (edit ? ' <button class="x" title="' + t("delete") + '" data-del="' + f.id + '">&times;</button>' : "") + "</li>"; }).join("") + "</ul>" : '<small class="muted"> ' + t("no_evidence") + "</small>") + "</div></section>";
    });
    h += '<div class="pager">' + (S.sec > 0 ? '<button class="btn" data-sec-go="-1">' + t("prev") + "</button>" : "<span></span>") +
      (S.sec < snap.sections.length - 1 ? '<button class="btn primary" data-sec-go="1">' + t("next") + "</button>" : submitBtn(a, done, total, openReq)) + "</div></div></div>";
    render(shell("assessments", h));
    setSaveState("saved");
  }
  function submitBtn(a, done, total, openReq) {
    if (!a.can_edit) return "<span></span>";
    if (a.status === "Clarification Required") return '<button class="btn primary" data-act="resubmit"' + (openReq.length || done < total ? " disabled" : "") + ">" + t("resubmit") + "</button>";
    if (a.status === "Draft" || a.status === "In Progress") return '<button class="btn primary" data-act="submit"' + (done < total ? ' disabled title="' + t("missing_answers") + '"' : "") + ">" + t("submit") + "</button>";
    return "<span></span>";
  }

  function updateProgress() {
    var a = S.asm, snap = a.snapshot, total = snap.questions.length, done = answeredCount();
    $$(".sec").forEach(function (b, i) {
      var qs = secQuestions(snap, snap.sections[i].section_code), d = qs.filter(function (q) { return (a.answers[q.question_code] || {}).selected_option; }).length;
      $("em", b).textContent = d + "/" + qs.length; b.classList.toggle("full", d === qs.length);
    });
    var bar = $(".prog.wide i"); if (bar) bar.style.width = Math.round(done / total * 100) + "%";
    var sm = $(".prog.wide + small"); if (sm) sm.textContent = done + " " + t("of") + " " + total + " " + t("answered");
    var sb = $("[data-act=submit],[data-act=resubmit]");
    if (sb) { var openReq = (a.clarifications || []).filter(function (c) { return c.kind === "Request" && c.status === "Open"; }).length; sb.disabled = done < total || (sb.getAttribute("data-act") === "resubmit" && openReq > 0); }
  }

  function queueSave(code, patch) {
    S.pending[code] = Object.assign(S.pending[code] || { question_code: code }, patch);
    var cur = S.asm.answers[code] || (S.asm.answers[code] = {});
    Object.keys(patch).forEach(function (k) { cur[k] = patch[k]; });
    updateProgress(); setSaveState("saving"); clearTimeout(S.saveTimer); S.saveTimer = setTimeout(flushSave, 700);
  }
  function flushSave() { return flushNow().catch(function () {}); }
  function flushNow() {
    clearTimeout(S.saveTimer);
    var items = Object.keys(S.pending).map(function (k) { return S.pending[k]; });
    if (!items.length) return S.saving || Promise.resolve();
    var prev = S.saving || Promise.resolve();
    S.pending = {};
    S.saving = prev.catch(function () {}).then(function () { return api("portal.save_answers", { name: S.asm.name, items: items }); }).then(function (r) {
      S.asm.status = r.status; S.asm.answered = r.answered; setSaveState(Object.keys(S.pending).length ? "saving" : "saved"); S.saving = null;
    }).catch(function (e) {
      S.saving = null; items.forEach(function (it) { S.pending[it.question_code] = Object.assign(it, S.pending[it.question_code] || {}); });
      setSaveState("save_failed"); if (e.session) fail(e); else S.saveTimer = setTimeout(flushSave, 4000); throw e;
    });
    return S.saving;
  }
  function refreshAssessment(keepSec) { var sec = S.sec; return flushNow().catch(function () {}).then(function () { return api("portal.get_assessment", { name: S.asm.name }); }).then(function (a) { S.asm = a; S.sec = keepSec ? sec : S.sec; drawAssessment(); }); }

  // ---------------------------------------------------------------- scorecard
  function viewScorecard(name) {
    api("portal.get_scorecard", { name: name }).then(function (sc) {
      var r = sc.final || null, p = sc.preliminary;
      var h = '<header class="ph"><div><a class="link" href="#/assessments/' + name + '">&larr; ' + t("assessments") + "</a><h1>" + t("scorecard") + "</h1><div>" + esc(sc.title) + " " + badge(sc.status) + "</div></div></header>";
      if (r) {
        h += '<section class="card hero"><div><small>' + t("overall") + '</small><div class="score" style="color:' + esc(r.color || "#0B5C6B") + '">' + r.overall_score + '%</div></div><div><span class="lvl" style="background:' + esc(r.color || "#0B5C6B") + '">' + esc(S.lang === "ar" ? r.maturity_level_ar : r.maturity_level) + "</span><p>" + esc(S.lang === "ar" ? r.interpretation_ar : r.interpretation) + "</p>" +
          ((S.lang === "ar" ? r.gating_note_ar : r.gating_note) ? '<p class="note">' + esc(S.lang === "ar" ? r.gating_note_ar : r.gating_note) + "</p>" : "") + "</div></section>";
        h += '<div class="btnrow"><b>' + t("download_pdf") + ':</b> <button class="btn" data-pdf="en">' + t("pdf_en") + '</button> <button class="btn" data-pdf="ar">' + t("pdf_ar") + "</button></div>";
        h += "<h2>" + t("by_section") + '</h2><div class="tablewrap"><table class="tbl"><tbody>' + r.sections.map(function (s) {
          return "<tr><td>" + esc(S.lang === "ar" && s.title_ar ? s.title_ar : s.title) + '</td><td style="width:38%"><div class="prog wide"><i style="width:' + Math.min(100, s.score_pct) + "%;background:" + esc(s.color || "") + '"></i></div></td><td><b>' + s.score_pct + "%</b></td><td>" + esc(S.lang === "ar" ? s.maturity_level_ar : s.maturity_level) + "</td></tr>";
        }).join("") + "</tbody></table></div>";
        h += "<h2>" + t("recommended") + "</h2>" + (r.actions.length ? r.actions.map(function (x) {
          return '<section class="card act p-' + x.current_option + '"><div class="qh"><span class="qc">' + esc(x.question_code) + "</span><h3>" + esc(S.lang === "ar" ? x.short_label_ar || x.short_label : x.short_label) + '</h3><span class="badge pri">' + esc(S.lang === "ar" ? x.priority_ar : x.priority) + " &middot; " + esc(S.lang === "ar" ? x.timeframe_ar : x.timeframe) + "</span></div>" +
            "<p><b>" + t("current_state") + ":</b> " + esc(S.lang === "ar" ? x.current_text_ar || x.current_text : x.current_text) + "</p><p><b>" + t("next_level") + ":</b> " + esc(S.lang === "ar" ? x.recommended_text_ar || x.recommended_text : x.recommended_text) + "</p><small class=\"muted\">" + t("owner") + ": " + esc(S.lang === "ar" ? x.owner_role_ar || x.owner_role : x.owner_role) + "</small></section>";
        }).join("") : "<p class=\"empty\">-</p>");
      } else {
        if (p) h += '<section class="card hero"><div><small>' + t("preliminary") + '</small><div class="score">' + p.overall_score + '%</div></div><div><span class="lvl muted-bg">' + esc(S.lang === "ar" ? p.maturity_level_ar : p.maturity_level) + "</span><p>" + t("preliminary_note") + "</p></div></section>";
        h += '<p class="note">' + t("report_pending") + "</p>";
      }
      render(shell("assessments", h));
    }).catch(function (e) { fail(e); });
  }

  // ---------------------------------------------------------------- organization & members
  function viewOrganization() {
    api("portal.get_organization").then(function (o) {
      var admin = S.ctx.membership.is_admin, ro = !admin;
      var sectors = (S.cfg && S.cfg.sectors || []).map(function (s) { return { v: s, l: s }; });
      var h = '<header class="ph"><h1>' + t("org_title") + '</h1></header><form class="card" id="f-org" novalidate><div class="grid2">' + field("g_legal", t("legal_name"), { value: o.legal_name, readonly: ro, dir: "ltr" }) + field("g_legal_ar", t("legal_name_ar"), { value: o.legal_name_ar, readonly: ro, dir: "rtl" }) +
        field("g_sector", t("sector"), { options: sectors, value: o.sector }) + field("g_city", t("city"), { value: o.city, readonly: ro }) + field("g_cr", t("cr"), { value: o.commercial_registration, readonly: ro, dir: "ltr" }) + field("g_web", t("website"), { value: o.website, readonly: ro, dir: "ltr" }) +
        field("g_cn", t("contact_name"), { value: o.primary_contact_name, readonly: ro }) + field("g_ce", t("contact_email"), { value: o.primary_contact_email, readonly: ro, dir: "ltr" }) + "</div>" +
        (admin ? '<button class="btn primary" type="submit">' + t("save") + "</button>" : '<p class="muted">' + t("only_admin") + "</p>") + "</form>" +
        '<section class="card"><h3>' + t("notif_title") + '</h3><p class="muted">' + t("notif_text") + '</p><label class="chk"><input type="checkbox" data-notify="me"' + (S.ctx.membership.notify_me ? " checked" : "") + "> " + t("notif_me") + "</label>" +
        (admin ? '<label class="chk"><input type="checkbox" data-notify="org"' + (S.ctx.membership.notify_org ? " checked" : "") + "> " + t("notif_org") + "</label>" : "") + "</section>";
      render(shell("organization", h));
      if (ro) $$("#f-org select").forEach(function (s) { s.disabled = true; });
      var f = $("#f-org");
      if (admin) f.addEventListener("submit", function (e) {
        e.preventDefault(); var b = $("button[type=submit]", f); busy(b, true);
        api("portal.update_organization", { organization: { legal_name: val("g_legal"), legal_name_ar: val("g_legal_ar"), sector: val("g_sector"), city: val("g_city"), commercial_registration: val("g_cr"), website: val("g_web"), primary_contact_name: val("g_cn"), primary_contact_email: val("g_ce") } })
          .then(function () { busy(b, false); toast(t("saved_ok")); }).catch(function (er) { busy(b, false); fail(er); });
      });
    }).catch(fail);
  }

  function viewGroup() {
    api("portal.group_overview").then(function (rows) {
      var h = '<header class="ph"><h1>' + t("group") + '</h1></header><p class="note">' + t("group_note") + "</p>";
      if (!rows.length) h += '<p class="empty">' + t("group_empty") + "</p>";
      rows.forEach(function (o) {
        h += '<section class="card"><h3>' + esc(S.lang === "ar" && o.legal_name_ar || o.legal_name) + "</h3>" + (o.assessments.length ? '<div class="tablewrap"><table class="tbl"><tbody>' + o.assessments.map(function (a) {
          return "<tr><td>" + esc(a.title) + "<br><small>" + esc(a.name) + "</small></td><td>" + badge(a.status) + "</td><td>" + (a.released ? "<b>" + a.final_score + "%</b> " + esc(a.final_level || "") : "-") + '</td><td class="r">' + (a.released ? '<a class="btn sm" href="#/assessments/' + a.name + '/scorecard">' + t("scorecard") + "</a>" : "") + "</td></tr>";
        }).join("") + "</tbody></table></div>" : '<p class="muted">' + t("no_assessments") + "</p>") + "</section>";
      });
      render(shell("group", h));
    }).catch(fail);
  }

  function viewNewOrg() {
    var sectors = (S.cfg && S.cfg.sectors || []).map(function (s) { return { v: s, l: s }; });
    var admins = ((S.ctx && S.ctx.organizations) || []).filter(function (o) { return o.role === "Org Admin"; }).map(function (o) { return { v: o.name, l: S.lang === "ar" && o.legal_name_ar || o.legal_name }; });
    var h = '<header class="ph"><h1>' + t("add_org") + '</h1></header><form class="card" id="f-new" novalidate><p class="muted">' + t("add_org_text") + '</p><div class="grid2">' + field("n_legal", t("legal_name"), { dir: "ltr" }) + field("n_legal_ar", t("legal_name_ar"), { dir: "rtl" }) +
      field("n_sector", t("sector"), { options: sectors }) + field("n_city", t("city")) + field("n_cr", t("cr"), { dir: "ltr" }) + field("n_parent", t("parent_org"), { options: admins, hint: t("parent_hint") }) + '</div><button class="btn primary" type="submit">' + t("create") + "</button></form>";
    render(shell("organization", h));
    $("#f-new").addEventListener("submit", function (e) {
      e.preventDefault(); var b = $("button[type=submit]", e.target); busy(b, true);
      api("portal.create_organization", { organization: { legal_name: val("n_legal"), legal_name_ar: val("n_legal_ar"), sector: val("n_sector"), city: val("n_city"), commercial_registration: val("n_cr") }, parent_organization: val("n_parent") || null })
        .then(function (c) { S.ctx = c; S.asm = null; toast(t("saved_ok")); go("#/dashboard"); }).catch(function (er) { busy(b, false); fail(er); });
    });
  }

  function viewMembers() {
    api("portal.list_members").then(function (d) {
      var roles = ["Org Admin", "Assessor", "Action Owner", "Viewer"];
      var ropts = function (sel) { return roles.map(function (r) { return '<option value="' + r + '"' + (r === sel ? " selected" : "") + ">" + t("r_" + r.replace(/ /g, "_")) + "</option>"; }).join(""); };
      var h = '<header class="ph"><h1>' + t("members_title") + "</h1></header>";
      h += '<div class="tablewrap"><table class="tbl"><thead><tr><th>' + t("full_name") + "</th><th>" + t("role") + "</th><th></th></tr></thead><tbody>" + d.members.filter(function (m) { return m.status === "Active"; }).map(function (m) {
        return "<tr><td><b>" + esc(m.full_name || m.user) + "</b><br><small dir=\"ltr\">" + esc(m.user) + "</small></td><td>" + (d.can_manage ? '<select data-role="' + esc(m.name) + '">' + ropts(m.member_role) + "</select>" : t("r_" + m.member_role.replace(/ /g, "_"))) + '</td><td class="r">' + (d.can_manage ? '<button class="btn sm danger" data-rm="' + esc(m.name) + '">' + t("remove") + "</button>" : "") + "</td></tr>";
      }).join("") + "</tbody></table></div>";
      if (d.can_manage) {
        h += '<section class="card"><h3>' + t("invite") + '</h3><form id="f-inv" class="inline" novalidate>' + field("i_email", t("email"), { type: "email", dir: "ltr" }) + '<div class="f"><label for="i_role">' + t("role") + '</label><select id="i_role">' + ropts("Assessor") + '</select></div><button class="btn primary" type="submit">' + t("invite") + '</button></form><div id="inv-out"></div></section>';
        if (d.invitations.length) h += "<h3>" + t("pending_invites") + '</h3><div class="tablewrap"><table class="tbl"><tbody>' + d.invitations.map(function (i) { return "<tr><td dir=\"ltr\">" + esc(i.email) + "</td><td>" + t("r_" + i.member_role.replace(/ /g, "_")) + "</td><td>" + fmtDate(i.expires_on) + '</td><td class="r"><button class="btn sm" data-revoke="' + esc(i.name) + '">' + t("revoke") + "</button></td></tr>"; }).join("") + "</tbody></table></div>";
      } else h += '<p class="muted">' + t("only_admin") + "</p>";
      render(shell("members", h));
      var f = $("#f-inv");
      if (f) f.addEventListener("submit", function (e) {
        e.preventDefault(); var b = $("button[type=submit]", f); busy(b, true);
        api("portal.invite_member", { email: val("i_email"), role: document.getElementById("i_role").value }).then(function (r) {
          busy(b, false); toast(t("invite_sent")); $("#inv-out").innerHTML = '<p class="note">' + t("invite_link") + ':<br><input id="inv-link" readonly dir="ltr" value="' + esc(r.link) + '"> <button class="btn sm" type="button" data-act="copy">' + t("copy") + "</button></p>";
        }).catch(function (er) { busy(b, false); fail(er); });
      });
    }).catch(fail);
  }


  function viewOrganizations() {
    api("portal.list_organizations").then(function (rows) {
      var h = '<header class="ph"><div><h1>' + t("my_orgs") + '</h1><p class="muted">' + t("my_orgs_text") + '</p></div><a class="btn primary" href="#/neworg">' + t("add_org") + "</a></header>";
      h += '<div class="tablewrap"><table class="tbl"><thead><tr><th>' + t("switch_org") + "</th><th>" + t("role") + "</th><th>" + t("assessments") + "</th><th>" + t("kpi_released") + '</th><th></th></tr></thead><tbody>' + rows.map(function (o) {
        return "<tr><td><b>" + esc(S.lang === "ar" && o.legal_name_ar || o.legal_name) + "</b>" + (o.active ? ' <span class="badge">' + t("current") + "</span>" : "") + (o.parent ? "<br><small>" + t("is_sub") + "</small>" : "") + "</td><td>" + t("r_" + o.role.replace(/ /g, "_")) + "</td><td>" + o.assessments + " (" + o.open + " " + t("open_n") + ")</td><td>" + o.released + '</td><td class="r">' + (o.active ? "" : '<button class="btn sm" data-switch-btn="1">' + t("switch_to") + "</button>") + "</td></tr>";
      }).join("") + "</tbody></table></div>";
      render(shell("organizations", h));
      $$("[data-switch-btn]").forEach(function (b, i) { var o = rows.filter(function (x) { return !x.active; })[i]; b.value = o.name; b.addEventListener("click", function () { api("portal.switch_organization", { organization: o.name }).then(function (c) { S.ctx = c; S.asm = null; go("#/dashboard"); }).catch(fail); }); });
    }).catch(fail);
  }

  function viewMessages(aname) {
    aname = aname || (location.hash.split("/")[2] || null);
    api("portal.list_messages", aname ? { assessment: aname } : {}).then(function (rows) {
      if (S.ctx && S.ctx.unread_messages) S.ctx.unread_messages = 0;
      var h = '<header class="ph"><div><h1>' + t("msgs") + '</h1><p class="muted">' + t("msgs_text") + (S.ctx.support_email ? " " + t("msgs_email") + ' <a href="mailto:' + esc(S.ctx.support_email) + '">' + esc(S.ctx.support_email) + "</a>." : "") + "</p></div>" + (aname ? '<a class="btn sm" href="#/messages">' + t("all_msgs") + "</a>" : "") + "</header>";
      h += '<section class="card thread">' + (rows.length ? rows.map(function (r) {
        return '<div class="msg ' + (r.sender_type === "Staff" ? "them" : "me") + '"><small><b>' + esc(r.sender_name) + "</b> &middot; " + esc(String(r.creation).slice(0, 16)) + (r.kind === "Change Request" ? " &middot; " + t("change_title") : "") + (r.assessment ? " &middot; " + esc(r.assessment) : "") + "</small><div>" + esc(r.body).replace(/\n/g, "<br>") + "</div></div>";
      }).join("") : '<p class="empty">' + t("msgs_empty") + "</p>") + "</section>";
      h += '<section class="card"><textarea id="msgbody" rows="3" placeholder="' + t("msg_ph") + '"></textarea><button class="btn primary" data-act="sendmsg" data-a="' + esc(aname || "") + '">' + t("msg_send") + "</button></section>";
      render(shell("messages", h));
    }).catch(fail);
  }

  function viewProfile() {
    var p = S.ctx.profile || {};
    var h = '<header class="ph"><h1>' + t("profile") + '</h1></header><section class="card"><div class="grid2">' + field("pf_name", t("full_name"), { value: S.ctx.full_name }) + field("pf_email", t("email"), { value: S.ctx.user, readonly: true, dir: "ltr" }) + field("pf_mobile", t("mobile"), { value: p.mobile_no || "", dir: "ltr" }) +
      '<div class="f"><label>' + t("lang_label") + "</label>" + langSwitch() + '<small class="hint muted">' + t("lang_hint") + "</small></div></div>" +
      '<button class="btn primary" data-act="saveprofile">' + t("save") + '</button></section><section class="card"><h3>' + t("change_pw") + '</h3><div class="grid2">' + field("pw_old", t("pw_old"), { type: "password" }) + "<div></div>" + field("pw_new", t("pw_new"), { type: "password", hint: t("pw_hint") }) + field("pw_new2", t("pw_new2"), { type: "password" }) +
      '</div><button class="btn primary" data-act="savepw">' + t("change_pw") + "</button></section>";
    render(shell("profile", h));
  }

  function viewSetup() {
    var sectors = (S.cfg && S.cfg.sectors || []).map(function (s) { return { v: s, l: s }; });
    var staff = S.ctx.is_staff;
    render('<div class="auth"><div class="auth-card"><div class="auth-top"><div class="brand dark"><img src="/assets/alphax_grc/images/alphax_icon.png" alt=""><div><b>AlphaX GRC</b><span>GRC &amp; Audit</span></div></div><div>' + langSwitch() + ' <button class="btn ghost sm" data-act="logout">' + t("signout") + "</button></div></div>" +
      (staff ? "<h1>" + t("welcome") + '</h1><p class="note">' + t("staff_note") + '</p><p class="muted"><b>' + esc(S.ctx.full_name) + "</b> &middot; " + esc((S.ctx.staff_roles || []).join(", ")) + "<br><small>" + t("staff_customer_hint") + '</small></p><a class="btn primary" href="/app">' + t("open_desk") + "</a>" :
        "<h1>" + t("setup_org") + "</h1><p>" + t("setup_org_text") + '</p><form id="f-setup" novalidate><div class="grid2">' + field("o_legal", t("legal_name"), { dir: "ltr" }) + field("o_legal_ar", t("legal_name_ar"), { dir: "rtl" }) + field("o_sector", t("sector"), { options: sectors }) + field("o_city", t("city")) + "</div>" +
        '<button class="btn primary" type="submit">' + t("save") + '</button></form><p class="aux">' + t("join_with_invite") + "</p>") + "</div></div>");
    var f = $("#f-setup");
    if (f) f.addEventListener("submit", function (e) {
      e.preventDefault(); var b = $("button[type=submit]", f); busy(b, true);
      api("portal.create_organization", { organization: { legal_name: val("o_legal"), legal_name_ar: val("o_legal_ar"), sector: val("o_sector"), city: val("o_city") } }).then(function (c) { S.ctx = c; go("#/dashboard"); route(); }).catch(function (er) { busy(b, false); fail(er); });
    });
  }

  // ---------------------------------------------------------------- events
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-act],[data-pdf-resp],[data-sec],[data-sec-go],[data-reply],[data-dl],[data-del],[data-pdf],[data-rm],[data-revoke]");
    if (!el) return;
    var act = el.getAttribute("data-act");
    if (act === "lang") { var nl = el.getAttribute("data-l") || (S.lang === "ar" ? "en" : "ar"); if (nl === S.lang) return; S.lang = nl; applyLang(); if (S.ctx) api("portal.set_language", { language: S.lang }).catch(function () {}); route(true); return; }
    if (act === "reqchange") { var cv = ($("#chg") || {}).value; if (!cv || !cv.trim()) return toast(t("change_ph"), true); busy(el, true); api("portal.request_change", { name: S.asm.name, message: cv }).then(function () { toast(t("change_sent")); $("#chg").value = ""; busy(el, false); }).catch(function (er) { busy(el, false); fail(er); }); return; }
    if (act === "sendmsg") { var mv = ($("#msgbody") || {}).value; if (!mv || !mv.trim()) return; busy(el, true); api("portal.send_message", { body: mv, assessment: el.getAttribute("data-a") || null }).then(function () { viewMessages(el.getAttribute("data-a") || null); }).catch(function (er) { busy(el, false); fail(er); }); return; }
    if (act === "saveprofile") { busy(el, true); api("portal.update_profile", { full_name: val("pf_name"), mobile_no: val("pf_mobile") }).then(function (c) { S.ctx = c; busy(el, false); toast(t("saved_ok")); route(); }).catch(function (er) { busy(el, false); fail(er); }); return; }
    if (act === "savepw") { if (val("pw_new") !== val("pw_new2")) return toast(t("pw_mismatch"), true); busy(el, true); api("portal.change_password", { old_password: val("pw_old"), new_password: val("pw_new") }).then(function () { busy(el, false); ["pw_old", "pw_new", "pw_new2"].forEach(function (i) { document.getElementById(i).value = ""; }); toast(t("pw_changed")); }).catch(function (er) { busy(el, false); fail(er); }); return; }
    if (act === "logout") { fetch("/api/method/logout", { method: "POST", headers: { "X-Frappe-CSRF-Token": window.GRC.csrf }, credentials: "same-origin" }).then(function () { window.location.href = "/grc"; }); return; }
    if (act === "resend") { S.reg.step = 1; var rb = el; busy(rb, true); api("auth.register_start", { email: S.reg.email, full_name: S.reg.name, language: S.lang, invite_token: ((new URLSearchParams(window.location.search)).get("invite")) || null }).then(function (r) { S.reg.test_code = r.test_code; S.reg.step = 2; toast(t("code_resent")); viewRegister(); }).catch(function (er) { S.reg.step = 2; busy(rb, false); fail(er); }); return; }
    if (act === "activity") {
      var box = $("#activity-box"); if (!box) return; if (!box.hidden) { box.hidden = true; return; }
      api("portal.get_activity", { name: S.asm.name }).then(function (rows) {
        box.innerHTML = "<h3>" + t("activity") + "</h3>" + (rows.length ? '<ul class="tl">' + rows.map(function (r) {
          var who = r.by_type === "Staff" ? t("grc_team") : r.by_type === "System" ? t("system") : esc(r.by);
          return "<li><small>" + new Date(r.at).toLocaleString(S.lang === "ar" ? "ar-SA" : "en-GB") + " &middot; " + who + '</small><div><b>' + esc(t("ev_" + r.event_type)) + "</b> " + esc(r.detail || "") + "</div></li>";
        }).join("") + "</ul>" : '<p class="muted">-</p>'); box.hidden = false;
      }).catch(fail); return;
    }
    if (act === "reg-back") { S.reg.step = 1; viewRegister(); return; }
    if (act === "copy") { var i = $("#inv-link"); i.select(); try { document.execCommand("copy"); toast(t("copied")); } catch (er) {} return; }
    if (act === "start") { busy(el, true); api("portal.start_assessment").then(function (n) { go("#/assessments/" + n); }).catch(function (er) { busy(el, false); fail(er); }); return; }
    if (act === "submit" || act === "resubmit") {
      if (!window.confirm(t(act === "submit" ? "submit_confirm" : "resubmit_confirm"))) return;
      flushNow().then(function () { return api(act === "submit" ? "portal.submit_assessment" : "portal.resubmit_assessment", { name: S.asm.name }); }).then(function () { toast(t("submitted_ok")); return refreshAssessment(true); }).catch(fail);
      return;
    }
    if (el.hasAttribute("data-sec")) { flushSave(); S.sec = +el.getAttribute("data-sec"); drawAssessment(); return; }
    if (el.hasAttribute("data-sec-go")) { flushSave(); S.sec += +el.getAttribute("data-sec-go"); drawAssessment(); return; }
    if (el.hasAttribute("data-reply")) {
      var cname = el.getAttribute("data-reply"), box = document.getElementById("rp-" + cname); if (!box.value.trim()) return;
      busy(el, true); api("portal.add_clarification_reply", { name: S.asm.name, question_code: el.getAttribute("data-q"), message: box.value }).then(function () { toast(t("reply_sent")); refreshAssessment(true); }).catch(function (er) { busy(el, false); fail(er); }); return;
    }
    if (el.hasAttribute("data-dl")) { e.preventDefault(); download("portal.download_evidence", { file_id: el.getAttribute("data-dl") }); return; }
    if (el.hasAttribute("data-del")) { if (!window.confirm(t("delete") + "?")) return; api("portal.delete_evidence", { file_id: el.getAttribute("data-del") }).then(function () { refreshAssessment(true); }).catch(fail); return; }
    if (el.hasAttribute("data-pdf-resp")) { download("portal.download_responses", { name: S.asm.name, lang: S.lang }); return; }
    if (el.hasAttribute("data-pdf")) { download("portal.download_report", { name: location.hash.split("/")[2], lang: el.getAttribute("data-pdf") }); return; }
    if (el.hasAttribute("data-rm")) { if (!window.confirm(t("confirm_remove"))) return; api("portal.remove_member", { name: el.getAttribute("data-rm") }).then(viewMembers).catch(fail); return; }
    if (el.hasAttribute("data-revoke")) { api("portal.revoke_invitation", { name: el.getAttribute("data-revoke") }).then(viewMembers).catch(fail); return; }
  });
  document.addEventListener("change", function (e) {
    var el = e.target;
    if (el.matches && el.matches(".opts input[type=radio]")) {
      var code = el.name.slice(2); $$('input[name="' + el.name + '"]').forEach(function (r) { r.closest(".opt").classList.toggle("on", r.checked); });
      queueSave(code, { selected_option: el.value }); return;
    }
    if (el.hasAttribute && el.hasAttribute("data-up")) {
      var f = el.files[0]; if (!f) return; var fd = new FormData(); fd.append("name", S.asm.name); fd.append("question_code", el.getAttribute("data-up")); fd.append("file", f);
      toast(t("saving"));
      fetch(API + "portal.upload_evidence", { method: "POST", headers: { "X-Frappe-CSRF-Token": window.GRC.csrf, "Accept": "application/json" }, body: fd, credentials: "same-origin" })
        .then(function (r) { return r.text().then(function (tx) { var d = {}; try { d = JSON.parse(tx); } catch (x) {} if (!r.ok) throw new Error(serverMessage(r, d) || t("err_generic")); }); })
        .then(function () { toast(t("saved")); refreshAssessment(true); }).catch(function (er) { toast(er.message, true); });
      return;
    }
    if (el.hasAttribute && (el.hasAttribute("data-switch") || el.hasAttribute("data-switch-btn"))) { api("portal.switch_organization", { organization: el.value }).then(function (c) { S.ctx = c; S.asm = null; if (location.hash === "#/dashboard") route(); else go("#/dashboard"); }).catch(fail); return; }
    if (el.hasAttribute && el.hasAttribute("data-notify")) { var k = el.getAttribute("data-notify"); api("portal.set_notifications", k === "me" ? { for_me: el.checked ? 1 : 0 } : { for_org: el.checked ? 1 : 0 }).then(function (c) { S.ctx = c; toast(t("saved_ok")); }).catch(function (er) { el.checked = !el.checked; fail(er); }); return; }
    if (el.hasAttribute && el.hasAttribute("data-role")) { api("portal.change_member_role", { name: el.getAttribute("data-role"), role: el.value }).then(function () { toast(t("saved_ok")); }).catch(function (er) { fail(er); viewMembers(); }); }
  });
  document.addEventListener("input", function (e) {
    var el = e.target; if (el.hasAttribute && el.hasAttribute("data-cm")) queueSave(el.getAttribute("data-cm"), { comment: el.value });
  });
  window.addEventListener("beforeunload", function (e) { if (Object.keys(S.pending).length || S.saving) { e.preventDefault(); e.returnValue = ""; } });

  // ---------------------------------------------------------------- router
  function go(h) { if (location.hash === h) route(); else location.hash = h; }
  function route() {
    applyLang();
    var h = (location.hash || "#/").replace(/^#\/?/, ""), p = h.split("/");
    if (!S.ctx) {
      if (p[0] === "register") return viewRegister();
      if (p[0] === "forgot") return viewForgot();
      return viewLogin();
    }
    if (!S.ctx.membership) return viewSetup();
    if (p[0] === "assessments" && p[1] && p[2] === "scorecard") return viewScorecard(p[1]);
    if (p[0] === "assessments" && p[1]) return viewAssessment(p[1]);
    switch (p[0]) {
      case "assessments": return viewAssessments();
      case "organization": return viewOrganization();
      case "neworg": return viewNewOrg();
      case "organizations": return viewOrganizations();
      case "messages": return viewMessages();
      case "profile": return viewProfile();
      case "group": return viewGroup();
      case "members": return viewMembers();
      default: return viewDashboard();
    }
  }
  window.addEventListener("hashchange", function () { flushSave(); route(); });

  function boot() {
    applyLang();
    var inviteTok = (new URLSearchParams(window.location.search)).get("invite");
    var pcfg = fetch(API + "auth.site_config", { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (d) { S.cfg = d.message; }).catch(function () {});
    var pctx = fetch(API + "portal.get_context", { credentials: "same-origin", headers: { "Accept": "application/json" } }).then(function (r) { return r.ok ? r.json().then(function (d) { S.ctx = d.message; }) : null; }).catch(function () {});
    Promise.all([pcfg, pctx]).then(function () {
      if (S.ctx && inviteTok && !S.ctx.is_staff) {
        return api("portal.accept_invitation", { token: inviteTok }).then(function (c) { S.ctx = c; toast(t("invite_accepted")); }).catch(function (e) { toast(e.message, true); }).then(function () { history.replaceState(null, "", "/grc#/dashboard"); });
      }
    }).then(function () {
      if (!S.ctx && inviteTok) {
        return fetch(API + "auth.invitation_info?token=" + encodeURIComponent(inviteTok), { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
          if (d && d.message) { S.reg = { invite: d.message, email: d.message.email, step: 1 }; if (location.hash.indexOf("#/register") !== 0) location.hash = "#/register"; }
        }).catch(function () {});
      }
    }).then(route);
  }
  boot();
})();
