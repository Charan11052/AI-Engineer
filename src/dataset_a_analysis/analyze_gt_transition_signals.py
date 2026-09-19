from pathlib import Path
import json
from datetime import datetime


PROJECT_DIR = Path(__file__).resolve().parents[2]

DATASET_A = PROJECT_DIR / "data" / "dataset_a"

GT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_execution_intervals.jsonl"
)


TARGET_SESSION = "ses_20260701-152030-CHAITANYA0BCF"


def load_gt():
    records = []

    with GT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                records.append(json.loads(line))

    return records


def load_session_events(session_id):
    events = []

    for path in DATASET_A.rglob("events.jsonl"):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                if event.get("session_id") == session_id:
                    events.append(event)

    events.sort(key=lambda e: e["timestamp_ms"])

    return events


def fmt_ms(ms):
    return datetime.fromtimestamp(
        ms / 1000.0
    ).strftime("%H:%M:%S.%f")[:-3]


def app_name(event):
    context = event.get("context", {})
    active_app = context.get("active_app", {})

    if not isinstance(active_app, dict):
        return None

    return (
        active_app.get("app_name")
        or active_app.get("process_name")
    )


def find_first_event_at_or_after(events, timestamp_ms):
    for i, event in enumerate(events):
        if event["timestamp_ms"] >= timestamp_ms:
            return i

    return None


def main():
    gt = [
        x
        for x in load_gt()
        if x.get("session_id") == TARGET_SESSION
    ]

    events = load_session_events(TARGET_SESSION)

    print("=" * 120)
    print("GT TRANSITION SIGNAL ANALYSIS")
    print("=" * 120)

    print(f"Session       : {TARGET_SESSION}")
    print(f"Raw events    : {len(events)}")
    print(f"GT executions : {len(gt)}")

    print()
    print(
        "For every GT execution after the first, "
        "we inspect the raw events around its start."
    )

    for i, execution in enumerate(gt):
        if i == 0:
            continue

        start_ts = execution.get("start_ts")

        if not start_ts:
            continue

        start_dt = datetime.fromisoformat(
            start_ts.replace("Z", "+00:00")
        )

        start_ms = int(
            start_dt.timestamp() * 1000
        )

        idx = find_first_event_at_or_after(
            events,
            start_ms
        )

        if idx is None:
            continue

        print()
        print("-" * 120)

        print(
            f"GT {execution.get('execution_id')} "
            f"process={execution.get('process_code')} "
            f"variant={execution.get('process_variant')} "
            f"start={start_ts}"
        )

        print(
            f"Raw event index at start: {idx}"
        )

        print()
        print(
            f"{'offset':>9} "
            f"{'time':>15} "
            f"{'event_type':30} "
            f"{'app':30}"
        )

        # Show 5 events before and 10 after.
        begin = max(0, idx - 5)
        end = min(len(events), idx + 11)

        for j in range(begin, end):
            event = events[j]

            offset = (
                event["timestamp_ms"] - start_ms
            ) / 1000.0

            print(
                f"{offset:9.3f} "
                f"{fmt_ms(event['timestamp_ms']):>15} "
                f"{event.get('event_type', '?'):30} "
                f"{str(app_name(event)):30}"
            )


if __name__ == "__main__":
    main()