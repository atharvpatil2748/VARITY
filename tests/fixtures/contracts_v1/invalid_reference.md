---
verity_spec: "1.0.0"
source_key: payments-api
project: payment-service
title: Dangling Reference Example
spec_version: "1.0"
---

# Requirements
## REQ-001: Refund window
Refund requests MUST be accepted only within 30 days.

# Acceptance criteria
## AC-001: Late refund
A payment older than 30 days returns REFUND_WINDOW_EXPIRED.
References: REQ-999