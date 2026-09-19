from pathlib import Path
import json
from collections import Counter

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_A = PROJECT_DIR / "data" / "dataset_a"

TARGET_SESSION = "ses_20260701-152030-CHAITANYA0BCF"


def load_gt_starts():
    candidates = list(PROJECT_DIR.rglob("gt_manifest.json"))

    target_manifest = None

    for path in candidates:
        if path.parent.name == TARGET_SESSION:
            target_manifest = path
            break

    if target_manifest is None:
        raise FileNotFoundError(
            f"Could not find gt_manifest.json for session {TARGET_SESSION}"
        )

    print("Using GT manifest:")
    print(f"  {target_manifest}")

    with target_manifest.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    starts = []

    for process in manifest.get("processes", []):
        for execution in process.get("executions", []):
            start_ts = execution.get("start_ts")

            if start_ts:
                starts.append(start_ts)

    print(f"GT starts found for target session: {len(starts)}")

    return set(starts)

def main():
    gt_starts = load_gt_starts()

    app_switches = []

    for path in DATASET_A.rglob("events.jsonl"):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                event = json.loads(line)

                if event.get("session_id") != TARGET_SESSION:
                    continue

                if event.get("event_type") != "app_switch":
                    continue

                payload = event.get("payload", {})

                new_app = payload.get("new_app", {})
                previous_app = payload.get("previous_app", {})

                app_switches.append({
                    "timestamp": event.get("timestamp_iso"),
                    "trigger": payload.get("trigger"),
                    "new_app": new_app,
                    "previous_app": previous_app,
                    "active_app": event.get("context", {}).get("active_app"),
                    "extensions": event.get("extensions", {}),
                })

    print("=" * 100)
    print("APP_SWITCH GT SIGNAL ANALYSIS")
    print("=" * 100)

    print(f"GT process starts: {len(gt_starts)}")
    print(f"Total app_switch events: {len(app_switches)}")

    # Find app_switch events that occur within 1 second of a GT start.
    print("\nAPP_SWITCH EVENTS NEAR GT STARTS")
    print("-" * 100)

    gt_start_list = sorted(gt_starts)

    # Convert timestamps to milliseconds.
    from datetime import datetime

    def parse(ts):
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000

    gt_ms = [(ts, parse(ts)) for ts in gt_start_list]

    near_count = 0

    for event in app_switches:
        event_ms = parse(event["timestamp"])

        nearest = None
        nearest_diff = float("inf")

        for gt_ts, gt_timestamp_ms in gt_ms:
            diff = abs(event_ms - gt_timestamp_ms)

            if diff < nearest_diff:
                nearest_diff = diff
                nearest = gt_ts

        if nearest_diff <= 1000:
            near_count += 1

            new_app = event["new_app"]
            prev_app = event["previous_app"]
            active = event["active_app"]

            print(
                f"\nAPP_SWITCH: {event['timestamp']}"
                f"\n  nearest GT start: {nearest}"
                f"\n  difference: {nearest_diff:.1f} ms"
                f"\n  trigger: {event['trigger']}"
                f"\n  new_app: {new_app.get('app_name')} | "
                f"{new_app.get('process_name')} | "
                f"{new_app.get('window_title')}"
                f"\n  previous_app: {prev_app.get('app_name')} | "
                f"{prev_app.get('process_name')} | "
                f"{prev_app.get('window_title')}"
                f"\n  active_app: {active.get('app_name')} | "
                f"{active.get('process_name')} | "
                f"{active.get('window_title')}"
            )

    print("\n" + "=" * 100)
    print(f"App switches within ±1 second of GT starts: {near_count}")
    print("=" * 100)


if __name__ == "__main__":
    main()