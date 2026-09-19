import json
from pathlib import Path
from collections import Counter, defaultdict
import statistics


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_A_DIR = PROJECT_DIR / "data" / "dataset_a"


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


def main():

    print("=" * 70)
    print("DATASET A — SCREENSHOT CONTEXT ANALYSIS")
    print("=" * 70)

    events_by_session = load_events()

    total_screenshots = 0

    previous_gap_values = []
    next_gap_values = []

    next_event_types = Counter()
    previous_event_types = Counter()

    same_app_next = 0
    changed_app_next = 0

    # How many screenshots are followed by a transition
    transition_after = Counter()

    for session_id, events in events_by_session.items():

        for i, event in enumerate(events):

            if event.get("event_type") != "screenshot_smart":
                continue

            total_screenshots += 1

            timestamp = int(event["timestamp_ms"])

            # --------------------------------------------------
            # Previous event
            # --------------------------------------------------

            if i > 0:

                previous = events[i - 1]

                previous_timestamp = int(
                    previous["timestamp_ms"]
                )

                previous_gap = (
                    timestamp - previous_timestamp
                ) / 1000.0

                previous_gap_values.append(previous_gap)

                previous_event_types[
                    previous.get("event_type")
                ] += 1

            # --------------------------------------------------
            # Next event
            # --------------------------------------------------

            if i + 1 < len(events):

                next_event = events[i + 1]

                next_timestamp = int(
                    next_event["timestamp_ms"]
                )

                next_gap = (
                    next_timestamp - timestamp
                ) / 1000.0

                next_gap_values.append(next_gap)

                next_event_types[
                    next_event.get("event_type")
                ] += 1

                # --------------------------------------------------
                # App transition
                # --------------------------------------------------

                current_context = event.get("context") or {}
                current_app = (
                    current_context.get("active_app") or {}
                ).get("app_name")

                next_context = next_event.get("context") or {}
                next_app = (
                    next_context.get("active_app") or {}
                ).get("app_name")

                if current_app == next_app:
                    same_app_next += 1
                else:
                    changed_app_next += 1

                # --------------------------------------------------
                # Transition categories
                # --------------------------------------------------

                transition_types = {
                    "app_switch",
                    "browser_navigation",
                    "mouse_click",
                    "window_state_change",
                    "window_title_change",
                }

                if next_event.get("event_type") in transition_types:
                    transition_after[
                        next_event.get("event_type")
                    ] += 1

    # ----------------------------------------------------------
    # Results
    # ----------------------------------------------------------

    print()
    print(f"Sessions loaded : {len(events_by_session):,}")
    print(f"Screenshots     : {total_screenshots:,}")

    print()
    print("Gap BEFORE screenshot")
    print("-" * 70)

    if previous_gap_values:

        values = sorted(previous_gap_values)

        print(
            f"Median : "
            f"{statistics.median(values):.4f}s"
        )

        print(
            f"Mean   : "
            f"{statistics.mean(values):.4f}s"
        )

        for threshold in [0.1, 0.25, 0.5, 1, 2, 3, 5, 8]:

            count = sum(
                1
                for value in values
                if value > threshold
            )

            percentage = (
                100 * count / len(values)
            )

            print(
                f"> {threshold:>4g}s : "
                f"{count:>6,} "
                f"({percentage:6.2f}%)"
            )

    print()
    print("Gap AFTER screenshot")
    print("-" * 70)

    if next_gap_values:

        values = sorted(next_gap_values)

        print(
            f"Median : "
            f"{statistics.median(values):.4f}s"
        )

        print(
            f"Mean   : "
            f"{statistics.mean(values):.4f}s"
        )

        for threshold in [0.1, 0.25, 0.5, 1, 2, 3, 5, 8]:

            count = sum(
                1
                for value in values
                if value > threshold
            )

            percentage = (
                100 * count / len(values)
            )

            print(
                f"> {threshold:>4g}s : "
                f"{count:>6,} "
                f"({percentage:6.2f}%)"
            )

    print()
    print("Previous event before screenshot")
    print("-" * 70)

    for event_type, count in previous_event_types.most_common(15):

        percentage = (
            100 * count / total_screenshots
        )

        print(
            f"{str(event_type):30s} "
            f"{count:6,} "
            f"({percentage:6.2f}%)"
        )

    print()
    print("Next event after screenshot")
    print("-" * 70)

    for event_type, count in next_event_types.most_common(15):

        percentage = (
            100 * count / total_screenshots
        )

        print(
            f"{str(event_type):30s} "
            f"{count:6,} "
            f"({percentage:6.2f}%)"
        )

    print()
    print("App continuity after screenshot")
    print("-" * 70)

    total_with_next = same_app_next + changed_app_next

    print(
        f"Same app   : {same_app_next:,} "
        f"({100 * same_app_next / total_with_next:.2f}%)"
    )

    print(
        f"Changed app: {changed_app_next:,} "
        f"({100 * changed_app_next / total_with_next:.2f}%)"
    )

    print()
    print("Transition immediately after screenshot")
    print("-" * 70)

    for event_type, count in transition_after.most_common():

        percentage = (
            100 * count / total_screenshots
        )

        print(
            f"{str(event_type):30s} "
            f"{count:6,} "
            f"({percentage:6.2f}%)"
        )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()