from pathlib import Path
import json
from collections import Counter

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_A = PROJECT_DIR / "data" / "dataset_a"


def app_identity(app):
    if not app:
        return None

    return (
        app.get("app_name"),
        app.get("process_name"),
        app.get("process_id"),
        app.get("window_title"),
    )


def main():
    total = 0
    changed = 0
    unchanged = 0

    change_types = Counter()
    triggers = Counter()

    examples = []

    for path in DATASET_A.rglob("events.jsonl"):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                if event.get("event_type") != "app_switch":
                    continue

                payload = event.get("payload", {})

                previous = payload.get("previous_app", {})
                new = payload.get("new_app", {})

                prev_identity = app_identity(previous)
                new_identity = app_identity(new)

                total += 1
                triggers[payload.get("trigger")] += 1

                if prev_identity != new_identity:
                    changed += 1

                    prev_app = previous.get("app_name")
                    new_app = new.get("app_name")

                    prev_title = previous.get("window_title")
                    new_title = new.get("window_title")

                    if prev_app != new_app:
                        change_type = "app_change"
                    elif prev_title != new_title:
                        change_type = "window_title_change"
                    elif previous.get("process_id") != new.get("process_id"):
                        change_type = "process_change"
                    else:
                        change_type = "other_identity_change"

                    change_types[change_type] += 1

                    if len(examples) < 30:
                        examples.append({
                            "session": event.get("session_id"),
                            "timestamp": event.get("timestamp_iso"),
                            "trigger": payload.get("trigger"),
                            "previous": previous,
                            "new": new,
                            "change_type": change_type,
                        })

                else:
                    unchanged += 1

    print("=" * 100)
    print("DATASET A APP_SWITCH TRANSITION ANALYSIS")
    print("=" * 100)

    print(f"Total app_switch events : {total}")
    print(f"Identity changed        : {changed}")
    print(f"Identity unchanged      : {unchanged}")

    if total:
        print(f"Change rate             : {changed / total * 100:.2f}%")

    print("\nCHANGE TYPES")
    print("-" * 100)

    for key, value in change_types.most_common():
        print(f"{key:25s}: {value}")

    print("\nTRIGGERS")
    print("-" * 100)

    for key, value in triggers.most_common():
        print(f"{str(key):25s}: {value}")

    print("\nFIRST 30 REAL TRANSITIONS")
    print("-" * 100)

    for i, example in enumerate(examples, 1):
        previous = example["previous"]
        new = example["new"]

        print(
            f"\n#{i} [{example['change_type']}] "
            f"{example['timestamp']}"
        )

        print(
            f"  {previous.get('app_name')} | "
            f"{previous.get('window_title')}"
        )

        print("       ↓")

        print(
            f"  {new.get('app_name')} | "
            f"{new.get('window_title')}"
        )

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()