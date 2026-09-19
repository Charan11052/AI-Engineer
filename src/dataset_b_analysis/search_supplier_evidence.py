import os
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_B_DIR = BASE_DIR / "data" / "dataset_b"


# ------------------------------------------------------------
# Find all events.jsonl files
# ------------------------------------------------------------

event_files = list(DATASET_B_DIR.rglob("events.jsonl"))

print("=" * 75)
print("DATASET B — SUPPLIER EVIDENCE SEARCH")
print("=" * 75)

print(f"Event files found : {len(event_files)}")
print()


# ------------------------------------------------------------
# Supplier-related keywords / patterns
# ------------------------------------------------------------

keywords = [
    "株式会社",
    "合同会社",
    "有限会社",
    "取引先",
    "仕入先",
    "supplier",
    "請求先",
    "発注先",
    "取引",
]

invoice_pattern = re.compile(
    r"INV-\d{4}-\d+"
)


matches = []

# ------------------------------------------------------------
# Search text-bearing events
# ------------------------------------------------------------

for path in event_files:

    with open(path, "r", encoding="utf-8") as f:

        for line_number, line in enumerate(f, 1):

            line = line.strip()

            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Try common text fields
            text_parts = []

            for key in [
                "text",
                "text_input",
                "value",
                "content",
                "description",
                "window_title",
                "title",
            ]:
                value = event.get(key)

                if isinstance(value, str) and value.strip():
                    text_parts.append(value)

            text = " ".join(text_parts)

            if not text:
                continue

            # Search supplier-related evidence
            found_keywords = [
                keyword
                for keyword in keywords
                if keyword.lower() in text.lower()
            ]

            invoice_ids = invoice_pattern.findall(text)

            if found_keywords or invoice_ids:

                matches.append({
                    "file": str(path.relative_to(BASE_DIR)),
                    "line": line_number,
                    "event_type": (
                        event.get("event")
                        or event.get("event_type")
                        or event.get("type")
                    ),
                    "keywords": found_keywords,
                    "invoice_ids": invoice_ids,
                    "text": text[:1000],
                })


# ------------------------------------------------------------
# Results
# ------------------------------------------------------------

print(f"Supplier-related evidence events : {len(matches)}")
print()

for item in matches[:100]:

    print("-" * 75)

    print("File       :", item["file"])
    print("Line       :", item["line"])
    print("Event type :", item["event_type"])

    if item["keywords"]:
        print(
            "Keywords   :",
            ", ".join(item["keywords"])
        )

    if item["invoice_ids"]:
        print(
            "Invoice IDs:",
            ", ".join(item["invoice_ids"])
        )

    print("Text       :", item["text"])


print()
print("=" * 75)
print(
    f"Displayed {min(len(matches), 100)} of {len(matches)} matches"
)
print("=" * 75)