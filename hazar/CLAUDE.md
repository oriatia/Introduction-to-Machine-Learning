# Hazar — AI tax refund app for Israel

## What we are building
A mobile-first web app that finds Israeli taxpayers money they are owed by the Israel Tax Authority,
prepares the refund request (Form 135, up to 6 past tax years), and routes it to a licensed tax advisor
for approval and submission. Phase 1 serves salaried employees (שכירים). Self-employed (Form 1301) comes later.

Core promise: answer a short chat questionnaire + upload documents → see an estimated refund in under
10 minutes → sign → a licensed advisor submits → track status until the money arrives.

## Non-negotiable principles
1. **The LLM never computes tax.** All numbers come from the deterministic tax engine (`packages/tax_engine`).
   The LLM collects information, extracts documents, explains results, and calls the engine as a tool.
2. **Never invent tax values.** Brackets, credit-point values, caps, ceilings and eligible-locality lists live
   in per-year data files. If a value is unknown, leave a placeholder with `verified: false` and a TODO —
   never guess from memory. The engine must refuse to produce a final result for a year whose tables
   contain unverified values (it may produce an estimate labeled as such).
3. **Every result is explainable.** Each line of an engine result carries `rule_id`, a Hebrew explanation
   template, and a legal reference (section of the Income Tax Ordinance). The UI's "למה?" button shows it.
4. **Humans approve irreversible actions.** Submitting, signing, charging, and sending any document outside
   the system always require explicit approval by the user and/or the advisor. Agents may prepare, never execute.
5. **Privacy by default.** Mask Israeli ID numbers (ת"ז), bank account numbers and full names before any
   text is sent to an external LLM. Encrypt documents at rest with per-user keys. Log every access to a case.
6. **Hebrew-first, RTL-first.** All user-facing strings in `apps/web/locales/he.json` (ru/ar/en later).
   No hard-coded UI strings. Accessibility per Israeli Standard 5568 (WCAG 2.1 AA).
7. **Tests before merge.** Tax engine changes require unit tests + passing regression snapshots.

## Stack
- `apps/web` — Next.js (App Router, TypeScript), Tailwind with RTL, PWA. Contains both the user app and
  the advisor back office (`/advisor`, desktop layout, role-gated).
- `services/api` — Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2.
- `services/worker` — background jobs (arq or Celery on Redis): document extraction, agent runs,
  scheduled automations.
- `packages/tax_engine` — pure Python, no I/O, no network. Imported by the API and worker.
- Postgres 16, Redis, S3-compatible object storage (MinIO locally; an Israel cloud region in production).
- LLM: Anthropic API (Claude) with tool use for agents; a vision-capable model for document extraction.
- Auth: phone number + SMS OTP; roles `user`, `advisor`, `admin`.
- Local dev: `docker compose up` brings up everything. Seed script creates demo users and demo cases.

## Repo layout
apps/web/                  Next.js app (user + advisor)
services/api/              FastAPI app, routers, models, migrations
services/worker/           jobs, agents, schedulers
packages/tax_engine/       engine, rules, per-year tables, tests
packages/tax_engine/tables/{year}.yaml
packages/tax_engine/tests/cases/     advisor-verified test cases (anonymized JSON)
infra/                     docker, compose, deploy
docs/                      architecture notes, ADRs

## Domain model (initial)
- User (phone, verified_at, role)
- Profile (marital status, spouse link, residency, disability flags)
- LifeEvent (type, date_from, date_to, data) — births, degree completion, army discharge, aliyah,
  address/locality changes, employment start/end. Tax-year facts are DERIVED from life events.
- TaxYear (user, year, status)
- Employer / IncomeSource per TaxYear (from Form 106: gross income, tax withheld, credit points used, etc.)
- Document (type: form_106 | form_867 | donation_receipt | insurance | pension | other; storage key;
  extraction JSON; per-field confidence; user_confirmed)
- Case (user, years[], state, advisor_id, fee terms, signed_at, submitted_at, paid_at)
- EngineRun (case, year, engine_version, tables_version, inputs hash, result JSON)
- AgentAction (case, agent, tool, input summary, output summary, approved_by, timestamp)
- AuditLog (actor, action, target, timestamp)

Case states: questionnaire → documents → calculating → qa_review → awaiting_user_signature →
awaiting_advisor → submitted → in_progress_at_authority → approved → paid | needs_info | rejected.
Transitions happen only through a single `case_state.transition()` function that validates and logs.

## Tax engine contract
Input: `YearProfile` (year, personal status on each month of the year, children with birth dates,
degrees, discharge date, aliyah date, locality periods, income sources, deductions/credits documents).
Output: `YearResult` with: taxable income, computed tax, credits applied, total credit points,
tax already withheld, refund (positive) or debt (negative), `lines[]` (rule_id, amount, explanation_he,
legal_ref), `warnings[]`, `is_estimate`, `engine_version`, `tables_version`.

Rules to implement (values from tables, never from code):
- Progressive brackets
- Credit points: resident, woman, children by age, single parent, academic degree, discharged soldier /
  national service, new immigrant, disability — each with its start/end logic
- Multiple employers without tax coordination (תיאום מס)
- Donations credit (section 46), life insurance credit, self pension deposits
- Eligible localities benefit (list + rate + ceiling per year)
- Months of partial-year residency/employment
Each rule is a separate module with its own tests. A rule registry lists all rules with `rule_id`,
supported years, and required inputs — the questionnaire uses it to decide which questions to ask.

## Agents (services/worker/agents)
An orchestrator reads the case state and dispatches one agent at a time. Agents only use their listed tools.
- chat_agent — runs the questionnaire and free chat. Tools: get_profile, upsert_life_event, get_rule_registry,
  estimate_refund.
- document_agent — extracts fields from uploaded images/PDFs. Tools: get_document, save_extraction,
  request_user_confirmation. Low-confidence fields must be confirmed by the user.
- eligibility_agent — cross-checks data and finds missed benefits. Tools: run_engine, list_missing_documents,
  add_finding.
- qa_agent — independent check: re-runs the engine, compares with extracted documents, flags anomalies.
  Does NOT see the eligibility agent's reasoning, only its outputs.
- followup_agent — reminders (WhatsApp/SMS/email), status updates, missing-document chasing.
  Tools: send_message (templates only), schedule_reminder.
- authority_reply_agent (phase 2) — reads a letter from the Tax Authority, explains it, drafts a response
  for the advisor.
Every agent call writes an AgentAction row. PII masking happens in one shared function before any LLM call.

## Scheduled automations
- Feb–Mar yearly: ask every user to upload their new Form 106 and check the previous year.
- December: notify users whose oldest eligible year expires at year end.
- On new life event: re-run eligibility and suggest updating Form 101 with the employer.

## Security
TLS everywhere; encryption at rest; per-user document keys; signed short-lived URLs for files;
RBAC on every endpoint; audit log on every case read; rate limiting on auth; secrets only via env;
retention job deletes raw documents after the configured period; no PII in logs.

## Working rules for Claude Code
- Work sprint by sprint (below). Start each sprint in plan mode and show the plan before writing code.
- Small commits with clear messages. Run lint + type check + tests before saying a task is done.
- When a requirement is ambiguous or needs a legal/tax decision, stop and ask — do not guess.
- Keep this file updated when an architectural decision changes (add an ADR in docs/).

## Sprints (2 weeks each)
1. Infrastructure — monorepo, docker compose, CI (lint, types, tests), SMS OTP auth (mock provider locally),
   Postgres + migrations, encrypted object storage, RTL design system (buttons, cards, chat bubbles, stepper).
   Done = a user can register and log in.
2. Questionnaire + life timeline — LifeEvent model, chat_agent, rule registry driving questions,
   rough estimate screen ("ייתכן שמגיע לך בין X ל-Y").
   Done = an estimate appears after the questionnaire.
   (ADR 0003: until verified tables exist the estimate lists possible benefits per year, without amounts;
   the questionnaire is structured; chat_agent moves to Sprint 7.)
3. Tax engine v1 — brackets + basic credit points for one year, tables with placeholders,
   20 test cases. Done = 20 cases pass.
4. Documents — vault, smart camera upload, Form 106 extraction with confidence, field confirmation screen,
   personal checklist. Done = a photographed 106 is extracted and confirmed.
   (ADR 0004: extraction runs in the worker behind an Extractor interface; mock by default. Claude vision on raw
   images waits for the product owner's privacy decision, ADR 0004 §4.)
5. Tax engine v2 — 6 years, multiple employers, localities, donations, insurance; refund report with
   per-year cards and "למה?". Done = 100 cases pass.
6. Submission — power of attorney + e-signature (provider behind an interface, mock locally),
   Form 135 data package / PDF draft for the advisor, advisor back office v1 (queue, case view, approve/return).
   Done = an advisor approves a real test case.
7. Agents + automations — orchestrator, document chasing, reminders, status tracking, fee payment
   (provider behind an interface). Done = one case runs end to end.
8. Hardening + beta — security review, monitoring, error tracking, performance, closed beta for 50 users.
   Done = 20 cases submitted.
