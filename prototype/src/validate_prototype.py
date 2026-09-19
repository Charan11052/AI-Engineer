import json
import re
from pathlib import Path


SEGMENTS_FILE = (
    Path(__file__).parent.parent.parent
    / "outputs"
    / "dataset_b"
    / "dataset_b_segments_v8.jsonl"
)


def main():
    seen = set()
    total = 0
    approve = 0
    review = 0

    invoice_pattern = re.compile(r"INV-\d{4}-\d+")
    amount_pattern = re.compile(r"金額：([\d,]+)円")

    with open(SEGMENTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            segment = json.loads(line)

            if segment.get("task") != "FINANCE_INVOICE":
                continue

            text = segment.get("completion_evidence", "")

            invoice_match = invoice_pattern.search(text)
            amount_match = amount_pattern.search(text)

            if not invoice_match or not amount_match:
                continue

            invoice_id = invoice_match.group(0)

            if invoice_id in seen:
                continue

            seen.add(invoice_id)

            total += 1

            # Supplier identity is not reliably available
            # in the extracted Dataset B evidence.
            review += 1

    print()
    print("PROTOTYPE VALIDATION")
    print("=" * 50)
    print(f"Unique Dataset B invoices : {total}")
    print(f"APPROVE                   : {approve}")
    print(f"REVIEW                    : {review}")
    print()
    print("Supplier identity is not reliably available")
    print("in the extracted Dataset B invoice evidence.")
    print("Therefore these cases are safely routed to review.")


if __name__ == "__main__":
    main()