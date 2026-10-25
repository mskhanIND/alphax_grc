# AlphaX GRC & Audit Platform (`alphax_grc`)

Frappe v15 app: public website + customer portal (`/grc`) + Desk workspace for the GRC team.
Phase 1: 20-question Internal Audit Maturity Assessment (IIA GIAS), bilingual EN/AR, review workflow, scored PDF reports.

## Install (test site)
```bash
cd ~/frappe-bench
bench get-app /path/to/alphax_grc        # or git URL / unzipped folder
bench --site <site> install-app alphax_grc
bench build --app alphax_grc
bench --site <site> migrate
bench --site <site> enable-scheduler
```
Then in Desk:
1. **Email Account**: set a default *outgoing* account (verification codes, invitations, notifications). Without it, tick **GRC Settings > Show code when email unavailable** (test only) and the code appears on screen.
2. **GRC Settings**: *Block personal email domains* is ON by default. Turn it off for testers using gmail etc. Set staff notification email and public site URL.
3. Demo staff (optional): `bench --site <site> execute alphax_grc.grc.install.create_demo_staff` prints logins for a manager, consultant and reviewer.
4. Staff 2FA (recommended for production): `bench --site <site> execute alphax_grc.grc.install.enable_staff_2fa`.

Portal: `https://<site>/grc` | Public site: `https://<site>/` | Staff: `https://<site>/app/alphax-grc`

## Roles
GRC Manager (everything, assigns, releases) | GRC Consultant, GRC Reviewer (only assessments assigned to them; reviewer/manager approve) | GRC Customer (portal only, no Desk, no DocType permissions).

## Workflow
Draft > In Progress > Submitted > Under Review > (Clarification Required > Resubmitted > Under Review) > Approved > Report Released.
Customers see a *Preliminary* scorecard after submit, and the *Approved* scorecard and PDFs only after release.

## Tests
`bench --site <site> run-tests --app alphax_grc` (22 tests: Excel scoring parity, workflow, isolation, PDF, reminders).

## Open decisions (per template-version switches)
Q1 gating cap, Q20 N/A, Q13 manual vs calculated, equal vs section weights. Disclaimer, privacy and terms text are DRAFTS for legal review. See HANDOFF.md.

## v0.2 changes (from the first review round)
- **Multiple organizations per user**, with an organization switcher; optional **parent organization** (holding company). A holding company's Org Admins get a read-only *Group* view: status and released results of subsidiaries only (no answers, comments or evidence).
- **Sign-in and registration**: clear "already registered? sign in" path, forgot password, resend code with cooldown, invitations for existing accounts are accepted after sign-in. GRC team accounts cannot be customer members (use a separate customer email to test the portal).
- **Staff on behalf of customers**: create the organization in Desk, *Invite Customer Admin*, *Enter Answers for Customer* / *Submit for Customer* (marked in the trail), and *Transfer* an assessment to another consultant or reviewer with a required reason.
- **Notifications**: per-user and per-organization switch for reminders and status updates. Verification codes, invitations and clarification requests are always sent.
- **Activity trail**: GRC Activity Log (answers, evidence, status, assignment, clarification, reminders, reports). Customers see a simplified timeline (staff shown as "GRC team"); reviewer adjustments and transfers are staff-only.
- **Slow email diagnosis**: *GRC Settings > Send Test Email* shows how many seconds the mail server took; sends slower than 5 s are written to the Error Log.
After upgrading run `bench --site <site> migrate`.
