def reject_duplicate_refund(request_id, seen):
    # REQ-002: duplicate refund requests must be rejected.
    if request_id in seen:
        return "REFUND_DUPLICATE"
    seen.add(request_id)
    return "OK"
