# ADR 0003 — Sprint 2: estimate without amounts, structured questionnaire

Status: accepted (2026-10-01, product owner: "do what's needed" on the recommended options)

## Context
CLAUDE.md asks Sprint 2 to end with a rough estimate screen ("ייתכן שמגיע לך בין X ל-Y"). The tax engine and
advisor-verified tables arrive in Sprint 3, and principle 2 forbids inventing tax values.

## Decisions
1. **No amounts before verified tables.** The Sprint 2 estimate lists the benefits that *may* apply, per tax year,
   and which documents will be needed. The X–Y range is added when the engine can compute it from verified tables.
2. **Structured questionnaire.** Questions are defined in code, driven by the rule registry (each rule declares the
   facts it needs; a question is asked only if some rule needs the fact it provides). The UI renders them as chat
   bubbles with buttons and date pickers. No LLM is needed for the core flow.
3. **chat_agent deferred.** Free-text chat with Claude moves to Sprint 7 with the other agents. The shared PII-masking
   function (`hazar_api.privacy.mask_for_llm`) is built now so it exists before any LLM call does.
4. **Screening is relevance only.** `hazar_tax_engine.screening` decides which rules *might* apply in which window
   years from the user's facts. It encodes no ages, durations, caps, or amounts; every finding says it still needs
   to be checked by the engine and the advisor.
5. **Answers are the source of truth** for questionnaire-derived data. Profile fields and LifeEvents with
   `source="questionnaire"` are re-derived from the answers on every change, so editing an answer can never leave
   stale events behind. Events from other sources (documents, advisor) are untouched.

## Open items for the tax advisor
- The exact boundary of the refund window (`REFUND_WINDOW_YEARS = 6`, years Y-6..Y-1) — confirm.
- `legal_ref` for every rule in the registry is a placeholder (`None`, `legal_ref_verified=False`) until reviewed.
- Placeholder Hebrew titles/explanations in the registry need wording review.
