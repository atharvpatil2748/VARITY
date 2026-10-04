# Payments architecture

## Overview
The payments service accepts refund requests from the public API and
settles them through the ledger pipeline. Every write is recorded before
the caller receives a response.

## Refund retry policy
Failed refund settlement attempts are retried three times with
exponential backoff. A retry MUST reuse the original idempotency key so
the ledger never double-pays a refund. After the third failure the
refund enters the manual review queue.

## Storage
Refund state lives in the ledger database. Ledger rows are append only
and carry the settlement reference for auditing.