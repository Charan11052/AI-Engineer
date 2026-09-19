import json
import sys
from pathlib import Path


REFERENCE_FILE = (
    Path(__file__).parent.parent
    / "data"
    / "reference_suppliers.json"
)


def load_reference_data():
    with open(REFERENCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def reconcile_invoice(invoice, reference_data):
    invoice_id = invoice.get("invoice_id")
    amount = invoice.get("amount")
    supplier = invoice.get("supplier")

    # Safety boundary: never make a financial decision
    # when required evidence is missing.
    if not invoice_id:
        return {
            "decision": "REVIEW",
            "reason": "Invoice ID is missing."
        }

    if amount is None:
        return {
            "invoice_id": invoice_id,
            "decision": "REVIEW",
            "reason": "Invoice amount is missing."
        }

    if not supplier:
        return {
            "invoice_id": invoice_id,
            "amount": amount,
            "decision": "REVIEW",
            "reason": (
                "Supplier identity is unavailable. "
                "Supplier and amount must be verified before approval."
            )
        }

    suppliers = reference_data["suppliers"]

    matches = [
        s
        for s in suppliers
        if s["supplier"] == supplier
    ]

    if not matches:
        return {
            "invoice_id": invoice_id,
            "amount": amount,
            "supplier": supplier,
            "decision": "REVIEW",
            "reason": (
                "Supplier is not present in the reference list."
            )
        }

    reference = matches[0]

    if amount != reference["monthly_amount"]:
        return {
            "invoice_id": invoice_id,
            "amount": amount,
            "supplier": supplier,
            "decision": "REVIEW",
            "reason": (
                f"Amount differs from reference amount "
                f"{reference['monthly_amount']}."
            ),
            "reference_amount": reference["monthly_amount"]
        }

    return {
        "invoice_id": invoice_id,
        "amount": amount,
        "supplier": supplier,
        "decision": "APPROVE",
        "reason": (
            "Supplier and amount match the reference list."
        )
    }
def main():
    if len(sys.argv) != 2:
        print(
            'Usage: python reconcile_invoice.py '
            '"{\\"invoice_id\\":\\"INV-2026-7352\\",'
            '\\"amount\\":393384,\\"supplier\\":null}"'
        )
        sys.exit(1)

    invoice = json.loads(sys.argv[1])
    reference_data = load_reference_data()

    result = reconcile_invoice(invoice, reference_data)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()