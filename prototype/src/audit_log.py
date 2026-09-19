import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

AUDIT_FILE = (
    BASE_DIR
    / "data"
    / "reconciliation_audit.jsonl"
)


def log_decision(
    evidence,
    validation,
    reconciliation=None
):
    """
    Write one auditable record for every invoice decision.

    The log records observed evidence, validation status,
    decision, and reason. No sensitive information is inferred.
    """

    result = reconciliation or validation

    record = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "invoice_id": evidence.get("invoice_id"),

        "amount": evidence.get("amount"),

        "supplier": evidence.get("supplier"),

        "supplier_source": evidence.get(
            "supplier_source"
        ),

        "evidence_valid": validation.get(
            "valid"
        ),

        "missing_fields": validation.get(
            "missing_fields",
            []
        ),

        "decision": result.get(
            "decision"
        ),

        "reason": result.get(
            "reason"
        ),

        "rules_version": "v1"
    }

    AUDIT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        AUDIT_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )

    return record