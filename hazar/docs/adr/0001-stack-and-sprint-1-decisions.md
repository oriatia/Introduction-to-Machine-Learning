# ADR 0001 — Stack and Sprint 1 decisions

Status: accepted (2026-09-30)

## Context
CLAUDE.md fixes the overall stack. Sprint 1 needed a few more choices, approved by the product owner.

## Decisions
1. **Repository location.** The recommended home is a new private repository. Until it exists, the project
   lives self-contained under `hazar/` in the current repository; nothing outside `hazar/` depends on it
   except the CI workflow, so it can be moved with `git subtree split --prefix=hazar`.
2. **Package managers.** pnpm for the web app, uv (workspace) for all Python packages.
3. **CI.** GitHub Actions.
4. **Sessions.** Opaque random session token in an httpOnly, Secure, SameSite=Lax cookie; session data in
   Redis with a TTL. Chosen over JWT for instant revocation (logout, role change, compromise).
5. **Worker.** arq (asyncio, same model as FastAPI) on Redis.
6. **Document encryption.** Envelope encryption: each user has a data key (DEK, AES-256-GCM) stored
   wrapped by a master key (KEK). Locally the KEK comes from an env var; in production a cloud KMS in an
   Israel region implements the same `KeyWrapper` interface. Objects are encrypted before they reach
   S3/MinIO, in addition to any server-side encryption.
7. **External providers** (SMS now; signature, payments, WhatsApp later) sit behind interfaces with mock
   implementations selected by env.
8. **Hosting target.** Open. Only the `ObjectStorage` and `KeyWrapper` interfaces depend on it.
