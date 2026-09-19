import json
from pathlib import Path

from reconcile_invoice import reconcile_invoice, load_reference_data


DEMO_FILE = (
    Path(__file__).parent.parent
    / "data"
    / "demo_cases.json"
)


def main():
    reference_data = load_reference_data()

    with open(DEMO_FILE, "r", encoding="utf-8") as f:
        invoices = json.load(f)

    print("\nFINANCE INVOICE RECONCILIATION")
    print("=" * 70)

    for invoice in invoices:
        result = reconcile_invoice(invoice, reference_data)

        print(f"\nInvoice : {invoice.get('invoice_id')}")
        print(f"Amount  : {invoice.get('amount')}")
        print(f"Supplier: {invoice.get('supplier')}")
        print(f"Decision: {result['decision']}")
        print(f"Reason  : {result['reason']}")


if __name__ == "__main__":
    main()