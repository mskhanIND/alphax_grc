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
