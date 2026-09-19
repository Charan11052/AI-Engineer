from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[2]

SEGMENTS_FILE = (
    ROOT
    / "outputs"
    / "dataset_b"
    / "dataset_b_segments_v8.jsonl"
)


def load_segments():
    segments = []

    with SEGMENTS_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:
            line = line.strip()

            if line:
                segments.append(
                    json.loads(line)
                )

    return segments


def main():

    print("=" * 70)
    print("DATASET B V8 — PROTOTYPE VALIDATION")
    print("=" * 70)

    if not SEGMENTS_FILE.exists():

        print(
            f"ERROR: V8 segments not found:\n"
            f"{SEGMENTS_FILE}"
        )

        return

    segments = load_segments()

    print()
    print(
        f"V8 segments loaded : "
        f"{len(segments)}"
    )

    if not segments:
        print("ERROR: No segments found.")
        return

    # --------------------------------------------------------
    # BASIC STRUCTURAL CHECK
    # --------------------------------------------------------

    required = [
        "task"
    ]

    missing_required = 0

    for segment in segments:

        for field in required:

            if field not in segment:

                missing_required += 1

                break

    print()
    print("=" * 70)
    print("STRUCTURAL VALIDATION")
    print("=" * 70)

    print(
        f"Segments checked      : "
        f"{len(segments)}"
    )

    print(
        f"Missing task field    : "
        f"{missing_required}"
    )

    # --------------------------------------------------------
    # START / END CHECK
    # --------------------------------------------------------

    invalid_intervals = 0

    for segment in segments:

        start = (
            segment.get("start_timestamp_ms")
            or segment.get("start_ts_ms")
            or segment.get("start_time_ms")
        )

        end = (
            segment.get("end_timestamp_ms")
            or segment.get("end_ts_ms")
            or segment.get("end_time_ms")
        )

        if (
            start is None
            or end is None
            or float(end) <= float(start)
        ):

            invalid_intervals += 1

    print(
        f"Invalid time intervals : "
        f"{invalid_intervals}"
    )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    confidence_counts = {}

    for segment in segments:

        confidence = segment.get(
            "start_confidence",
            "unknown"
        )

        confidence_counts[
            confidence
        ] = confidence_counts.get(
            confidence,
            0
        ) + 1

    print()
    print("=" * 70)
    print("START CONFIDENCE")
    print("=" * 70)

    for confidence, count in sorted(
        confidence_counts.items()
    ):

        print(
            f"{confidence:<15} "
            f"{count}"
        )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    passed = (
        len(segments) > 0
        and missing_required == 0
        and invalid_intervals == 0
    )

    print()
    print("=" * 70)

    if passed:
        print("PROTOTYPE INPUT VALIDATION: PASS")
    else:
        print("PROTOTYPE INPUT VALIDATION: REVIEW")

    print("=" * 70)


if __name__ == "__main__":
    main()