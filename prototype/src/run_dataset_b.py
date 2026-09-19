import json
import re
from pathlib import Path

from extract_invoice_evidence import extract_invoice_evidence
from validate_invoice_evidence import validate_invoice_evidence
from reconcile_invoice import (
    load_reference_data,
    reconcile_invoice,
)
from audit_log import log_decision

PROJECT_ROOT = Path(__file__).parent.parent.parent

SEGMENTS_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "dataset_b"
    / "dataset_b_segments_v8.jsonl"
)

OUTPUT_FILE = (
    Path(__file__).parent.parent
    / "data"
    / "dataset_b_reconciliation.jsonl"
)


def main():

    reference_data = load_reference_data()

    results = []
    seen_invoices = set()

    with open(
        SEGMENTS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            if not line.strip():
                continue

            segment = json.loads(line)

            if segment.get("task") != "FINANCE_INVOICE":
                continue

            evidence_text = segment.get(
                "completion_evidence",
                ""
            )

            # --------------------------------------------------
            # 1. Extract observed invoice evidence
            # --------------------------------------------------

            evidence = extract_invoice_evidence(
                evidence_text
            )

            if evidence.get("invoice_id") is None:
                continue

            invoice_id = evidence["invoice_id"]

            # --------------------------------------------------
            # Deduplicate repeated observations
            # --------------------------------------------------

            if invoice_id in seen_invoices:
                continue

            seen_invoices.add(invoice_id)

            # Supplier is intentionally unknown.
            #
            # Dataset B contains no reliable supplier evidence
            # in the extracted event text, so we never infer it.
            evidence["supplier"] = None
            evidence["supplier_source"] = None

            # --------------------------------------------------
            # 2. Validate evidence
            # --------------------------------------------------

            validation = validate_invoice_evidence(
                evidence
            )

            # --------------------------------------------------
            # 3. Reconcile only if evidence is complete
            # --------------------------------------------------

            if validation["valid"]:

                reconciliation = reconcile_invoice(
                    evidence,
                    reference_data
                )

            else:

                reconciliation = {
                    "decision": "REVIEW",
                    "reason": validation["reason"]
                }

            # --------------------------------------------------
            # 4. Write audit record
            # --------------------------------------------------

            audit_record = log_decision(
                evidence,
                validation,
                reconciliation
            )

            # --------------------------------------------------
            # 5. Store result for Dataset B report
            # --------------------------------------------------

            results.append({
                **evidence,
                **reconciliation,
                "evidence_valid": validation["valid"],
                "missing_fields": validation[
                    "missing_fields"
                ],
                "source_segment": segment[
                    "segment_id"
                ],
                "observed_duration_seconds":
                    segment[
                        "duration_seconds"
                    ],
            })

    # ----------------------------------------------------------
    # Save reconciliation results
    # ----------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for result in results:

            f.write(
                json.dumps(
                    result,
                    ensure_ascii=False
                )
                + "\n"
            )

    approve = sum(
        r["decision"] == "APPROVE"
        for r in results
    )

    review = sum(
        r["decision"] == "REVIEW"
        for r in results
    )

    invalid_evidence = sum(
        not r["evidence_valid"]
        for r in results
    )

    print()
    print("=" * 70)
    print("DATASET B — END-TO-END INVOICE AUTOMATION")
    print("=" * 70)

    print()
    print("PIPELINE")
    print("-" * 70)
    print("1. Evidence extraction       : COMPLETE")
    print("2. Evidence validation       : COMPLETE")
    print("3. Deterministic reconcile   : COMPLETE")
    print("4. Audit logging             : COMPLETE")

    print()
    print("RESULTS")
    print("-" * 70)
    print(
        f"Unique invoices processed : {len(results)}"
    )
    print(
        f"APPROVE                   : {approve}"
    )
    print(
        f"REVIEW                    : {review}"
    )
    print(
        f"Incomplete evidence       : {invalid_evidence}"
    )

    print()
    print("OUTPUTS")
    print("-" * 70)
    print(
        f"Reconciliation : {OUTPUT_FILE}"
    )

    print()
    print(
        "Audit log      : "
        + str(
            Path(__file__).parent.parent
            / "data"
            / "reconciliation_audit.jsonl"
        )
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()