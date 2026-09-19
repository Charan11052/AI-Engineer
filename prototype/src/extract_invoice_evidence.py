import re


INVOICE_PATTERN = re.compile(
    r"INV-\d{4}-\d+"
)

AMOUNT_PATTERN = re.compile(
    r"金額：([\d,]+)円"
)


def extract_invoice_evidence(text):
    """
    Extract only explicitly observed invoice information.

    No inference is performed.
    Missing fields remain None.
    """

    invoice_match = INVOICE_PATTERN.search(text)
    amount_match = AMOUNT_PATTERN.search(text)

    invoice_id = (
        invoice_match.group(0)
        if invoice_match
        else None
    )

    amount = None

    if amount_match:
        amount = int(
            amount_match.group(1).replace(",", "")
        )

    return {
        "invoice_id": invoice_id,
        "amount": amount,
        "supplier": None,
        "supplier_source": None,
    }
    