# ADR 0004 — Documents, Form 106 extraction, and the vision-LLM privacy question

Status: accepted for Sprint 4 (2026-10-01). **Open decision for the product owner: §4.**

## Decisions
1. **Vault.** Uploaded files go through `DocumentVault` (ADR 0001 §6): encrypted with the user's key before storage.
   A `documents` row holds metadata only (type, year, size, sha256, status, extraction, confirmed values).
2. **Upload safety.** Max 10 MB; the type is sniffed from magic bytes (JPEG, PNG, WebP, PDF) and must match an
   allow-list, whatever the client claims. Multipart uploads are exempt from the JSON-only rule but must carry the
   `X-Hazar-Upload: 1` header, which a cross-site form cannot send (CSRF defense).
3. **Extraction runs in the worker** (`extract_document` arq job) behind an `Extractor` interface:
   - `mock` (default): deterministic, no network. Reads expected values from a `hazar-mock` PNG text chunk (test
     fixtures); for any other file it returns every field empty with confidence 0, so the user types the values in.
   - `claude`: Claude Opus 5.5 vision with a strict JSON schema; per-field value + confidence. It is told to
     transcribe only, never compute, and not to return personal identifiers.
   Fields below `CONFIDENCE_THRESHOLD` (0.9) are flagged; **every field is shown on the confirmation screen and
   nothing is used until the user confirms** (CLAUDE.md: low-confidence fields must be confirmed by the user).
4. **Open: sending images to an external LLM.** Principle 5 requires masking ID numbers, bank accounts and names
   before text reaches an external LLM. A photo of Form 106 contains the employee's ID number and name, and an image
   cannot be masked with `mask_for_llm`. Options:
   a. Use Claude vision on the raw image under a zero/limited data-retention agreement, and record it in the privacy
      policy and consent text. Best accuracy.
   b. Run OCR locally (e.g. Tesseract with Hebrew), mask the text with `mask_for_llm`, then send only text to Claude.
      Keeps principle 5 literally; weaker on photos.
   c. Redact the identity region of the image before sending (detect it with local OCR, black it out).
   Until decided, `HAZAR_EXTRACTION_PROVIDER` defaults to `mock` and `claude` is refused unless
   `HAZAR_ALLOW_IMAGES_TO_LLM=true` is also set.
5. **Form field codes.** Form 106 fields are stored under semantic names. The official box numbers
   (`form_code`) are left unset until the tax advisor confirms them (principle 2 spirit: no guessed form facts).
6. **Confirmed 106 → IncomeSource.** Confirming a Form 106 creates/updates an `income_sources` row for that tax year and
   employer. That is what the tax engine will consume (Sprints 3/5).
7. **Checklist** is derived, not stored: documents the estimate's findings need, per year, plus Form 106 for each
   window year, each marked missing / uploaded / confirmed from the user's documents.
