---
verity_spec: "1.0.0"
source_key: payments-api
project: payment-service
title: Payment API Specification
spec_version: "1.0"
language: en
---

# Requirements
## REQ-001: Refund window
Refund requests MUST be accepted only within 30 days.

### Constraints
- A later request MUST return REFUND_WINDOW_EXPIRED.

### Edge cases
- A request at exactly 30 days is accepted.

### References
- API-001
- AC-001

## REQ-002: Partial refund
The API MUST support partial refunds.

### References
- API-001

## REQ-003: Idempotent refunds
Retrying a refund with the same idempotency_key MUST return the original result.

# API definitions
## API-001: POST /refunds
Request fields are payment_id, amount and idempotency_key.

# Acceptance criteria
## AC-001: Late refund
A payment older than 30 days returns REFUND_WINDOW_EXPIRED.
References: REQ-001

# References
- Internal payments architecture, section 4.2.