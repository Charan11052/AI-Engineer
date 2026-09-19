from pathlib import Path
import json
from datetime import datetime
from collections import Counter


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_A = PROJECT_DIR / "data" / "dataset_a"


def parse_ts(ts):
    if not ts:
        return None

    return datetime.fromisoformat(
        ts.replace("Z", "+00:00")
    ).timestamp() * 1000


def app_identity(app):
    if not app:
        return None

    return (
        app.get("app_name"),
        app.get("process_name"),
        app.get("process_id"),
        app.get("window_title"),
    )


def load_gt_starts(manifest_path):
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    starts = []

    for process in manifest.get("processes", []):
        for execution in process.get("executions", []):
            ts = execution.get("start_ts")

            if ts:
                starts.append(parse_ts(ts))

    return sorted(starts)


def nearest_distance(timestamp_ms, gt_starts):
    if not gt_starts:
        return None

    return min(
        abs(timestamp_ms - gt)
        for gt in gt_starts
    )


def main():

    all_distances = []

    total_sessions = 0
    total_gt_starts = 0
    total_transitions = 0

    near_counts = Counter()

    transition_examples = []

    for session_dir in sorted(DATASET_A.iterdir()):

        if not session_dir.is_dir():
            continue

        manifest_path = session_dir / "gt_manifest.json"

        if not manifest_path.exists():
            continue

        total_sessions += 1

        gt_starts = load_gt_starts(manifest_path)

        total_gt_starts += len(gt_starts)

        for path in session_dir.rglob("events.jsonl"):

            with path.open("r", encoding="utf-8") as f:

                for line in f:

                    line = line.strip()

                    if not line:
                        continue

                    event = json.loads(line)

                    if event.get("event_type") != "app_switch":
                        continue

                    payload = event.get("payload", {})

                    previous = payload.get(
                        "previous_app", {}
                    )

                    new = payload.get(
                        "new_app", {}
                    )

                    # Ignore app_switch events that
                    # do not actually change identity.
                    if app_identity(previous) == app_identity(new):
                        continue

                    timestamp_ms = parse_ts(
                        event.get("timestamp_iso")
                    )

                    if timestamp_ms is None:
                        continue

                    distance = nearest_distance(
                        timestamp_ms,
                        gt_starts
                    )

                    if distance is None:
                        continue

                    distance_sec = distance / 1000

                    total_transitions += 1
                    all_distances.append(distance_sec)

                    if distance_sec <= 0.5:
                        near_counts["<=0.5"] += 1

                    if distance_sec <= 1:
                        near_counts["<=1"] += 1

                    if distance_sec <= 2:
                        near_counts["<=2"] += 1

                    if distance_sec <= 5:
                        near_counts["<=5"] += 1

                    if distance_sec <= 10:
                        near_counts["<=10"] += 1

                    if distance_sec <= 20:
                        near_counts["<=20"] += 1

                    if distance_sec > 20:
                        near_counts[">20"] += 1

                    if len(transition_examples) < 50:
                        transition_examples.append({
                            "session": event.get("session_id"),
                            "timestamp": event.get(
                                "timestamp_iso"
                            ),
                            "distance_sec": distance_sec,
                            "previous_app": previous.get(
                                "app_name"
                            ),
                            "previous_title": previous.get(
                                "window_title"
                            ),
                            "new_app": new.get(
                                "app_name"
                            ),
                            "new_title": new.get(
                                "window_title"
                            ),
                        })

    print("=" * 100)
    print("DATASET A — IDENTITY TRANSITION vs GT START DISTANCE")
    print("=" * 100)

    print(f"Sessions analyzed        : {total_sessions}")
    print(f"GT starts                : {total_gt_starts}")
    print(
        f"Real identity transitions: "
        f"{total_transitions}"
    )

    print("\nDISTANCE TO NEAREST GT START")
    print("-" * 100)

    if total_transitions:

        for label in [
            "<=0.5",
            "<=1",
            "<=2",
            "<=5",
            "<=10",
            "<=20",
            ">20",
        ]:

            count = near_counts[label]

            print(
                f"{label:8s}s : "
                f"{count:6d} "
                f"({count / total_transitions * 100:6.2f}%)"
            )

    print("\nTRANSITIONS PER SESSION")
    print("-" * 100)

    session_transition_counts = Counter()

    for session_dir in DATASET_A.iterdir():

        if not session_dir.is_dir():
            continue

        count = 0

        for path in session_dir.rglob("events.jsonl"):

            with path.open("r", encoding="utf-8") as f:

                for line in f:

                    line = line.strip()

                    if not line:
                        continue

                    event = json.loads(line)

                    if event.get("event_type") != "app_switch":
                        continue

                    payload = event.get("payload", {})

                    previous = payload.get(
                        "previous_app", {}
                    )

                    new = payload.get(
                        "new_app", {}
                    )

                    if app_identity(previous) != app_identity(new):
                        count += 1

        session_transition_counts[
            session_dir.name
        ] = count

    counts = list(
        session_transition_counts.values()
    )

    if counts:

        print(
            f"Min transitions/session : {min(counts)}"
        )

        print(
            f"Median transitions/session : "
            f"{sorted(counts)[len(counts)//2]}"
        )

        print(
            f"Max transitions/session : {max(counts)}"
        )

    print("\nFIRST 50 REAL TRANSITIONS")
    print("-" * 100)

    for i, x in enumerate(
        transition_examples,
        1
    ):

        print(
            f"\n#{i} "
            f"distance={x['distance_sec']:.3f}s"
        )

        print(
            f"  {x['previous_app']} | "
            f"{x['previous_title']}"
        )

        print("       ↓")

        print(
            f"  {x['new_app']} | "
            f"{x['new_title']}"
        )

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()