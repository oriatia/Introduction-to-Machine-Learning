# ADR 0002 — Local S3-compatible storage: SeaweedFS instead of MinIO

Status: accepted (2026-09-30), revisit if MinIO images become available again

## Context
CLAUDE.md names MinIO for local object storage. During Sprint 1 the `minio/minio` image could not be pulled
(Docker Hub: "repository does not exist or may require docker login"; quay.io blocked), so a local stack
built on it would not start for new developers or in CI.

## Decision
Use SeaweedFS (`chrislusf/seaweedfs`) with its S3 gateway for local development and CI. The API talks to it
only through `S3ObjectStorage` (boto3, standard S3 calls), so production can use any S3-compatible store in an
Israel region. Switching back to MinIO is a change to one compose service and three env vars.

## Consequences
- Local credentials live in `infra/seaweedfs/s3.json` (development-only values).
- Documents are encrypted by the API before upload (ADR 0001 §6), so the choice of store does not affect
  confidentiality.
