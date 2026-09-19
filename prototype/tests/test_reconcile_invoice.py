import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reconcile_invoice import (
    load_reference_data,
    reconcile_invoice
)


REFERENCE = load_reference_data()


def test_matching_supplier_and_amount():
    invoice = {
        "invoice_id": "TEST-001",
        "amount": 385000,
        "supplier": "株式会社山田製作所"
    }

    result = reconcile_invoice(invoice, REFERENCE)

    assert result["decision"] == "APPROVE"


def test_amount_mismatch():
    invoice = {
        "invoice_id": "TEST-002",
        "amount": 400000,
        "supplier": "株式会社山田製作所"
    }

    result = reconcile_invoice(invoice, REFERENCE)

    assert result["decision"] == "REVIEW"
    assert result["reference_amount"] == 385000


def test_missing_supplier():
    invoice = {
        "invoice_id": "TEST-003",
        "amount": 385000,
        "supplier": None
    }

    result = reconcile_invoice(invoice, REFERENCE)

    assert result["decision"] == "REVIEW"


def test_unknown_supplier():
    invoice = {
        "invoice_id": "TEST-004",
        "amount": 385000,
        "supplier": "Unknown Supplier"
    }

    result = reconcile_invoice(invoice, REFERENCE)

    assert result["decision"] == "REVIEW"


def test_missing_invoice_id():
    invoice = {
        "amount": 385000,
        "supplier": "株式会社山田製作所"
    }

    result = reconcile_invoice(invoice, REFERENCE)

    assert result["decision"] == "REVIEW"


def test_missing_amount():
    invoice = {
        "invoice_id": "TEST-006",
        "supplier": "株式会社山田製作所"
    }

    result = reconcile_invoice(invoice, REFERENCE)

    assert result["decision"] == "REVIEW"


if __name__ == "__main__":
    tests = [
        test_matching_supplier_and_amount,
        test_amount_mismatch,
        test_missing_supplier,
        test_unknown_supplier,
        test_missing_invoice_id,
        test_missing_amount
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print()
    print("All tests passed.")