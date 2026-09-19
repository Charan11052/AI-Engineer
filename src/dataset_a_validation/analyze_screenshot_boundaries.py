import json
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
import statistics


PROJECT_DIR = Path(__file__).resolve().parents[2]

DATASET_A_DIR = PROJECT_DIR / "data" / "dataset_a"

GT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_execution_intervals.jsonl"
)


def load_events():
    events_by_session = defaultdict(list)

    files = sorted(DATASET_A_DIR.rglob("events.jsonl"))

    for path in files:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                session_id = event.get("session_id")
                timestamp_ms = event.get("timestamp_ms")

                if session_id is None or timestamp_ms is None:
                    continue

                events_by_session[session_id].append(event)

    for session_id in events_by_session:
        events_by_session[session_id].sort(
            key=lambda e: int(e["timestamp_ms"])
        )

    return events_by_session


def load_gt():
    records = []

    with GT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            records.append(json.loads(line))

    return records


def iso_to_ms(value):
    return int(
        datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).timestamp() * 1000
    )


def find_previous_event(events, timestamp_ms):
    previous = None

    for event in events:
        event_ts = int(event["timestamp_ms"])

        if event_ts >= timestamp_ms:
            break

        previous = event

    return previous


def find_next_event(events, timestamp_ms):
    for event in events:
        event_ts = int(event["timestamp_ms"])

        if event_ts > timestamp_ms:
            return event

    return None


def event_app(event):
    context = event.get("context") or {}
    active_app = context.get("active_app") or {}

    return active_app.get("app_name")


def event_window(event):
    context = event.get("context") or {}
    active_app = context.get("active_app") or {}

    return active_app.get("window_title")


def main():

    print("=" * 70)
    print("DATASET A — SCREENSHOT BOUNDARY ANALYSIS")
    print("=" * 70)

    events_by_session = load_events()
    gt_records = load_gt()

    print(f"\nSessions loaded : {len(events_by_session):,}")
    print(f"GT records      : {len(gt_records):,}")

    # ------------------------------------------------------------
    # Collect all screenshots
    # ------------------------------------------------------------

    screenshots = []

    for session_id, events in events_by_session.items():

        for index, event in enumerate(events):

            if event.get("event_type") != "screenshot_smart":
                continue

            screenshots.append({
                "session_id": session_id,
                "index": index,
                "timestamp_ms": int(event["timestamp_ms"]),
                "app": event_app(event),
                "window": event_window(event),
                "event": event,
            })

    print(f"Screenshots     : {len(screenshots):,}")

    # ------------------------------------------------------------
    # Determine which screenshots immediately precede GT starts
    # ------------------------------------------------------------

    screenshot_timestamps = defaultdict(list)

    for screenshot in screenshots:
        screenshot_timestamps[
            screenshot["session_id"]
        ].append(screenshot)

    boundary_screenshots = []

    for gt in gt_records:

        start_ts = gt.get("start_ts")

        if not start_ts:
            continue

        session_id = gt["session_id"]

        if session_id not in events_by_session:
            continue

        start_ms = iso_to_ms(start_ts)

        previous = find_previous_event(
            events_by_session[session_id],
            start_ms
        )

        if previous is None:
            continue

        if previous.get("event_type") != "screenshot_smart":
            continue

        previous_ts = int(previous["timestamp_ms"])

        gap = (start_ms - previous_ts) / 1000.0

        boundary_screenshots.append({
            "session_id": session_id,
            "timestamp_ms": previous_ts,
            "gap": gap,
            "app": event_app(previous),
            "window": event_window(previous),
            "gt_process": gt.get("process_code"),
        })

    print(
        f"Boundary screenshots: "
        f"{len(boundary_screenshots):,}"
    )

    # ------------------------------------------------------------
    # Basic boundary screenshot statistics
    # ------------------------------------------------------------

    gaps = sorted(
        item["gap"]
        for item in boundary_screenshots
    )

    if gaps:

        print()
        print("Boundary screenshot → GT start gap")
        print("-" * 70)

        print(f"Minimum : {min(gaps):.4f}s")
        print(f"Median  : {statistics.median(gaps):.4f}s")
        print(f"Mean    : {statistics.mean(gaps):.4f}s")

        print()

        thresholds = [
            0.1,
            0.25,
            0.5,
            1,
            2,
            3,
            5,
            8,
            10,
        ]

        for threshold in thresholds:

            count = sum(
                1 for gap in gaps
                if gap > threshold
            )

            percentage = (
                100 * count / len(gaps)
            )

            print(
                f"> {threshold:>5g}s : "
                f"{count:>6,} "
                f"({percentage:6.2f}%)"
            )

    # ------------------------------------------------------------
    # Apps before GT boundary
    # ------------------------------------------------------------

    print()
    print("Apps on boundary screenshots")
    print("-" * 70)

    app_counts = Counter(
        item["app"]
        for item in boundary_screenshots
    )

    for app, count in app_counts.most_common(15):

        percentage = (
            100 * count / len(boundary_screenshots)
        )

        print(
            f"{str(app):30s} "
            f"{count:6,} "
            f"({percentage:6.2f}%)"
        )

    # ------------------------------------------------------------
    # GT process distribution after screenshot
    # ------------------------------------------------------------

    print()
    print("Processes following boundary screenshots")
    print("-" * 70)

    process_counts = Counter(
        item["gt_process"]
        for item in boundary_screenshots
    )

    for process, count in process_counts.most_common():

        percentage = (
            100 * count / len(boundary_screenshots)
        )

        print(
            f"{str(process):10s} "
            f"{count:6,} "
            f"({percentage:6.2f}%)"
        )

    # ------------------------------------------------------------
    # What happens immediately AFTER boundary screenshot?
    # ------------------------------------------------------------

    print()
    print("Event immediately AFTER boundary screenshot")
    print("-" * 70)

    next_event_counts = Counter()

    for item in boundary_screenshots:

        session_id = item["session_id"]
        timestamp_ms = item["timestamp_ms"]

        next_event = find_next_event(
            events_by_session[session_id],
            timestamp_ms
        )

        if next_event:

            next_event_counts[
                next_event.get("event_type")
            ] += 1

    for event_type, count in next_event_counts.most_common(15):

        percentage = (
            100 * count / len(boundary_screenshots)
        )

        print(
            f"{str(event_type):30s} "
            f"{count:6,} "
            f"({percentage:6.2f}%)"
        )

    # ------------------------------------------------------------
    # Window title analysis
    # ------------------------------------------------------------

    print()
    print("Top window titles at boundary screenshots")
    print("-" * 70)

    window_counts = Counter(
        item["window"]
        for item in boundary_screenshots
        if item["window"]
    )

    for window, count in window_counts.most_common(20):

        percentage = (
            100 * count / len(boundary_screenshots)
        )

        print(
            f"{str(window)[:55]:55s} "
            f"{count:6,} "
            f"({percentage:6.2f}%)"
        )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()