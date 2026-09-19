import os
import json


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DATASET_B_DIR = os.path.join(
    BASE_DIR,
    "dataset_b"
)


# Find first events.jsonl
event_file = None

for root, dirs, files in os.walk(DATASET_B_DIR):

    if "events.jsonl" in files:
        event_file = os.path.join(
            root,
            "events.jsonl"
        )
        break


if event_file is None:
    raise FileNotFoundError(
        "Could not find events.jsonl in dataset_b"
    )


print("=" * 70)
print("DATASET B EVENT SCHEMA CHECK")
print("=" * 70)

print()
print("File:")
print(event_file)

print()

with open(
    event_file,
    "r",
    encoding="utf-8"
) as f:

    for i in range(5):

        line = f.readline()

        if not line:
            break

        event = json.loads(line)

        print("=" * 70)
        print(f"EVENT {i + 1}")
        print("=" * 70)

        print()
        print("TOP-LEVEL KEYS:")
        print(
            list(event.keys())
        )

        print()
        print("FULL EVENT:")

        print(
            json.dumps(
                event,
                indent=2,
                ensure_ascii=False
            )
        )

        print()