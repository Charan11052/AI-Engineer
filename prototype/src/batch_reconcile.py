import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from reconcile_invoice import extract_invoice, reconcile_invoice


SEGMENTS_FILE = (
    Path(__file__).parent.parent.parent
    / "outputs"
    / "dataset_b"
    / "dataset_b_segments_v8.jsonl"
)

OUTPUT_FILE = (
    Path(__file__).parent.parent
    / "data"
    / "reconciliation_results.jsonl"
)


def main():
    results = []
    seen_invoices = set()

    with open(SEGMENTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            segment = json.loads(line)

            if segment.get("task") != "FINANCE_INVOICE":
                continue

            text = segment.get("completion_evidence", "")

            try:
                invoice = extract_invoice(text)
            except ValueError:
                continue

            invoice_id = invoice["invoice_id"]

            # Avoid processing the same invoice more than once.
            if invoice_id in seen_invoices:
                continue

            seen_invoices.add(invoice_id)

            result = reconcile_invoice(invoice, text)

            result["segment_id"] = segment["segment_id"]
            result["duration_seconds"] = segment["duration_seconds"]

            results.append(result)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for result in results:
            f.write(
                json.dumps(result, ensure_ascii=False) + "\n"
            )

    approve_count = sum(
        r["decision"] == "APPROVE" for r in results
    )

    review_count = sum(
        r["decision"] == "REVIEW" for r in results
    )

    print("FINANCE INVOICE AUTOMATION")
    print("=" * 50)
    print(f"Unique invoices processed : {len(results)}")
    print(f"Auto-approved             : {approve_count}")
    print(f"Human review              : {review_count}")
    print(f"Output                    : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()