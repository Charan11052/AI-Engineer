def validate_invoice_evidence(evidence):
    """
    Validate whether the extracted invoice evidence
    contains all fields required for reconciliation.

    The validator never infers missing information.
    """

    missing_fields = []

    if not evidence.get("invoice_id"):
        missing_fields.append("invoice_id")

    if evidence.get("amount") is None:
        missing_fields.append("amount")

    if not evidence.get("supplier"):
        missing_fields.append("supplier")

    if missing_fields:
        return {
            "valid": False,
            "missing_fields": missing_fields,
            "decision": "REVIEW",
            "reason": (
                "Required invoice evidence is missing: "
                + ", ".join(missing_fields)
            )
        }

    return {
        "valid": True,
        "missing_fields": [],
        "decision": "PROCEED",
        "reason": "All required invoice evidence is available."
    }