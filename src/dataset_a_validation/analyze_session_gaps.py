import json
from pathlib import Path
from collections import defaultdict


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_A = PROJECT_DIR / "data" / "dataset_a"


def main():

    gaps_by_session = defaultdict(list)

    total_events = 0

    for events_file in DATASET_A.rglob("events.jsonl"):

        previous = None

        with events_file.open("r", encoding="utf-8") as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                event = json.loads(line)

                session_id = event.get("session_id")
                timestamp = event.get("timestamp_ms")

                if session_id is None or timestamp is None:
                    continue

                total_events += 1

                if previous is not None:
                    gap = (timestamp - previous) / 1000.0

                    if gap >= 0:
                        gaps_by_session[session_id].append(gap)

                previous = timestamp

    all_gaps = [
        gap
        for gaps in gaps_by_session.values()
        for gap in gaps
    ]

    print("=" * 80)
    print("DATASET A — SESSION-LEVEL EVENT GAP ANALYSIS")
    print("=" * 80)

    print(f"\nSessions : {len(gaps_by_session)}")
    print(f"Events   : {total_events}")
    print(f"Gaps     : {len(all_gaps)}")

    all_gaps.sort()

    print()
    print("=" * 80)
    print("GAP DISTRIBUTION")
    print("=" * 80)

    percentiles = [
        ("P50", 0.50),
        ("P75", 0.75),
        ("P90", 0.90),
        ("P95", 0.95),
        ("P97.5", 0.975),
        ("P99", 0.99),
        ("P99.5", 0.995),
        ("P99.9", 0.999),
    ]

    for name, p in percentiles:

        index = min(
            int(p * len(all_gaps)),
            len(all_gaps) - 1
        )

        print(
            f"{name:6s}: "
            f"{all_gaps[index]:10.3f}s"
        )

    print()
    print("=" * 80)
    print("LONG GAP COUNTS")
    print("=" * 80)

    for threshold in [
        2,
        3,
        4,
        5,
        6,
        8,
        10,
        12,
        15,
        20,
        30,
        60,
    ]:

        count = sum(
            1 for gap in all_gaps
            if gap > threshold
        )

        percentage = (
            100 * count / len(all_gaps)
        )

        print(
            f"> {threshold:2d}s : "
            f"{count:6d} "
            f"({percentage:6.3f}%)"
        )

    # ------------------------------------------------------------
    # SESSION-LEVEL MAXIMUM GAPS
    # ------------------------------------------------------------

    print()
    print("=" * 80)
    print("LARGEST GAP IN EACH SESSION")
    print("=" * 80)

    session_maxes = []

    for session_id, gaps in gaps_by_session.items():

        if gaps:

            session_maxes.append(
                (
                    max(gaps),
                    session_id,
                    len(gaps)
                )
            )

    session_maxes.sort(reverse=True)

    for gap, session_id, gap_count in session_maxes[:20]:

        print(
            f"{gap:10.3f}s | "
            f"{session_id} | "
            f"{gap_count} gaps"
        )


if __name__ == "__main__":
    main()