import json
from pathlib import Path
from collections import Counter
from statistics import mean, median


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "outputs" / "dataset_b_segments_v6.jsonl"


def load_segments():
    segments = []

    with OUTPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                segments.append(json.loads(line))

    return segments


def main():

    print("=" * 70)
    print("DATASET B V5 SEGMENT VALIDATION")
    print("=" * 70)

    segments = load_segments()

    print(f"\nSegments loaded: {len(segments)}")

    # ============================================================
    # 1. STRUCTURE
    # ============================================================

    print("\n" + "-" * 70)
    print("1. STRUCTURE")
    print("-" * 70)

    required_fields = [
        "segment_id",
        "session",
        "chunk",
        "task",
        "business_area",
        "start_timestamp_ms",
        "end_timestamp_ms",
        "duration_seconds",
        "event_count",
        "applications",
        "supporting_tasks",
        "completion_evidence",
        "completion_event_index",
        "start_event_index",
        "end_event_index",
        "event_type_counts",
        "confidence",
    ]

    structure_errors = []

    for i, segment in enumerate(segments):

        missing = [
            field
            for field in required_fields
            if field not in segment
        ]

        if missing:
            structure_errors.append(
                (i, segment.get("segment_id"), missing)
            )

    if not structure_errors:
        print("PASS: All segments contain the expected fields.")

    else:
        print(
            f"FAIL: {len(structure_errors)} segments "
            "have missing fields."
        )

        for item in structure_errors[:10]:
            print(
                f"  Segment {item[0]}: "
                f"{item[2]}"
            )

    # ============================================================
    # 2. DUPLICATE IDS
    # ============================================================

    print("\n" + "-" * 70)
    print("2. DUPLICATE SEGMENT IDS")
    print("-" * 70)

    ids = [
        segment.get("segment_id")
        for segment in segments
    ]

    id_counts = Counter(ids)

    duplicates = {
        k: v
        for k, v in id_counts.items()
        if k is not None and v > 1
    }

    if not duplicates:
        print("PASS: No duplicate segment IDs.")

    else:
        print(
            f"FAIL: {len(duplicates)} duplicate IDs found."
        )

        for segment_id, count in list(
            duplicates.items()
        )[:10]:
            print(
                f"  {segment_id}: {count} occurrences"
            )

    # ============================================================
    # 3. TIMESTAMP / DURATION CONSISTENCY
    # ============================================================

    print("\n" + "-" * 70)
    print("3. TIMESTAMP / DURATION CONSISTENCY")
    print("-" * 70)

    timestamp_errors = []

    for segment in segments:

        start = segment.get("start_timestamp_ms")
        end = segment.get("end_timestamp_ms")
        reported_duration = segment.get(
            "duration_seconds"
        )

        if start is None or end is None:
            timestamp_errors.append(
                (segment, "missing timestamp")
            )
            continue

        calculated_duration = (
            end - start
        ) / 1000.0

        if reported_duration is None:
            timestamp_errors.append(
                (segment, "missing duration")
            )
            continue

        # Allow tiny rounding differences.
        if abs(
            calculated_duration -
            float(reported_duration)
        ) > 0.01:

            timestamp_errors.append(
                (
                    segment,
                    (
                        f"duration mismatch: "
                        f"calculated={calculated_duration:.3f}, "
                        f"reported={reported_duration}"
                    )
                )
            )

    if not timestamp_errors:
        print(
            "PASS: Timestamp and duration values "
            "are consistent."
        )

    else:
        print(
            f"FAIL: {len(timestamp_errors)} "
            "timestamp/duration problems."
        )

        for segment, error in timestamp_errors[:10]:
            print(
                f"  {segment.get('segment_id')}: "
                f"{error}"
            )

    # ============================================================
    # 4. EVENT INDEX CONSISTENCY
    # ============================================================

    print("\n" + "-" * 70)
    print("4. EVENT INDEX CONSISTENCY")
    print("-" * 70)

    index_errors = []

    for segment in segments:

        start_index = segment.get(
            "start_event_index"
        )

        end_index = segment.get(
            "end_event_index"
        )

        event_count = segment.get(
            "event_count"
        )

        if (
            start_index is None
            or end_index is None
            or event_count is None
        ):
            index_errors.append(
                (
                    segment,
                    "missing event index/count"
                )
            )
            continue

        expected_count = (
            end_index - start_index + 1
        )

        if expected_count != event_count:
            index_errors.append(
                (
                    segment,
                    (
                        f"expected {expected_count} "
                        f"events but reported "
                        f"{event_count}"
                    )
                )
            )

    if not index_errors:
        print(
            "PASS: Event indices match event counts."
        )

    else:
        print(
            f"FAIL: {len(index_errors)} "
            "event-index problems."
        )

        for segment, error in index_errors[:10]:
            print(
                f"  {segment.get('segment_id')}: "
                f"{error}"
            )

    # ============================================================
    # 5. COMPLETION EVIDENCE
    # ============================================================

    print("\n" + "-" * 70)
    print("5. COMPLETION EVIDENCE")
    print("-" * 70)

    no_completion = []

    for segment in segments:

        evidence = segment.get(
            "completion_evidence"
        )

        if (
            evidence is None
            or not str(evidence).strip()
        ):
            no_completion.append(segment)

    if not no_completion:
        print(
            "PASS: Every segment has "
            "completion evidence."
        )

    else:
        print(
            f"FAIL: {len(no_completion)} "
            "segments have no completion evidence."
        )

        for segment in no_completion[:10]:
            print(
                f"  {segment.get('segment_id')}"
            )

    # ============================================================
    # 6. TASK / AREA CONSISTENCY
    # ============================================================

    print("\n" + "-" * 70)
    print("6. TASK / BUSINESS AREA CONSISTENCY")
    print("-" * 70)

    expected_area = {

        "HR_ATTENDANCE": "HR",
        "HR_ONBOARDING": "HR",
        "HR_PAYROLL": "HR",

        "FINANCE_INVOICE": "Finance",
        "FINANCE_PAYMENT": "Finance",
        "FINANCE_BUDGET": "Finance",

        "LOGISTICS_INVENTORY": "Logistics",
        "LOGISTICS_ORDER": "Logistics",
        "LOGISTICS_CONTRACT": "Logistics",
        "LOGISTICS_SUPPLIER": "Logistics",
    }

    inconsistencies = []

    for segment in segments:

        task = segment.get("task")
        area = segment.get("business_area")

        if task in expected_area:

            if expected_area[task] != area:

                inconsistencies.append(
                    (
                        segment,
                        expected_area[task],
                        area
                    )
                )

    if not inconsistencies:
        print(
            "PASS: Task and business-area "
            "assignments are consistent."
        )

    else:
        print(
            f"FAIL: {len(inconsistencies)} "
            "task/area inconsistencies."
        )

        for segment, expected, actual in (
            inconsistencies[:10]
        ):
            print(
                f"  {segment.get('segment_id')}: "
                f"{segment.get('task')} -> "
                f"expected {expected}, "
                f"got {actual}"
            )

    # ============================================================
    # 7. DURATION SANITY
    # ============================================================

    print("\n" + "-" * 70)
    print("7. DURATION SANITY")
    print("-" * 70)

    durations = []
    negative = []
    zero = []

    for segment in segments:

        duration = float(
            segment["duration_seconds"]
        )

        durations.append(duration)

        if duration < 0:
            negative.append(segment)

        if duration == 0:
            zero.append(segment)

    print(
        f"Min duration: "
        f"{min(durations):.3f}s"
    )

    print(
        f"Median duration: "
        f"{median(durations):.3f}s"
    )

    print(
        f"Mean duration: "
        f"{mean(durations):.3f}s"
    )

    print(
        f"Max duration: "
        f"{max(durations):.3f}s"
    )

    if not negative:
        print(
            "PASS: No negative durations."
        )
    else:
        print(
            f"FAIL: {len(negative)} "
            "negative durations."
        )

    print(
        f"Zero-duration segments: "
        f"{len(zero)}"
    )

    # ============================================================
    # 8. VERY SHORT SEGMENTS
    # ============================================================

    print("\n" + "-" * 70)
    print("8. VERY SHORT SEGMENTS (<0.5s)")
    print("-" * 70)

    very_short = [
        segment
        for segment in segments
        if float(
            segment["duration_seconds"]
        ) < 0.5
    ]

    print(
        f"Count: {len(very_short)}"
    )

    if very_short:

        print("\nExamples:")

        for segment in very_short[:15]:

            print(
                f"  {segment.get('segment_id')} | "
                f"{segment.get('task')} | "
                f"{segment.get('duration_seconds')}s | "
                f"{segment.get('completion_evidence', '')[:120]}"
            )

    # ============================================================
    # 9. LONG SEGMENTS
    # ============================================================

    print("\n" + "-" * 70)
    print("9. LONG SEGMENTS (>60s)")
    print("-" * 70)

    long_segments = [
        segment
        for segment in segments
        if float(
            segment["duration_seconds"]
        ) > 60
    ]

    print(
        f"Count: {len(long_segments)}"
    )

    if long_segments:

        for segment in sorted(
            long_segments,
            key=lambda x: float(
                x["duration_seconds"]
            ),
            reverse=True
        )[:15]:

            print(
                f"  "
                f"{segment['duration_seconds']:.2f}s | "
                f"{segment['task']} | "
                f"{segment['segment_id']}"
            )

    # ============================================================
    # 10. TASK DISTRIBUTION
    # ============================================================

    print("\n" + "-" * 70)
    print("10. TASK DISTRIBUTION")
    print("-" * 70)

    task_counts = Counter(
        segment.get("task")
        for segment in segments
    )

    for task, count in sorted(
        task_counts.items()
    ):
        print(
            f"{task:25s} {count:4d}"
        )

    # ============================================================
    # 11. BUSINESS AREA DISTRIBUTION
    # ============================================================

    print("\n" + "-" * 70)
    print("11. BUSINESS AREA DISTRIBUTION")
    print("-" * 70)

    area_counts = Counter(
        segment.get("business_area")
        for segment in segments
    )

    for area, count in sorted(
        area_counts.items()
    ):
        print(
            f"{area:15s} {count:4d}"
        )

    # ============================================================
    # 12. SUPPORTING TASKS
    # ============================================================

    print("\n" + "-" * 70)
    print("12. SUPPORTING TASK ANALYSIS")
    print("-" * 70)

    multiple_support = []

    for segment in segments:

        supporting = segment.get(
            "supporting_tasks",
            []
        )

        if len(supporting) > 1:
            multiple_support.append(segment)

    print(
        "Segments with multiple supporting "
        f"tasks: {len(multiple_support)}"
    )

    print(
        "\nThis is informational only. "
        "Supporting-task evidence does not "
        "automatically indicate a bad segment."
    )

    # ============================================================
    # 13. CONFIDENCE
    # ============================================================

    print("\n" + "-" * 70)
    print("13. CONFIDENCE")
    print("-" * 70)

    confidence_counts = Counter(
        segment.get("confidence")
        for segment in segments
    )

    for confidence, count in sorted(
        confidence_counts.items()
    ):
        print(
            f"{str(confidence):10s} {count:4d}"
        )

    # ============================================================
    # FINAL SUMMARY
    # ============================================================

    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    checks = {

        "Structure":
            not structure_errors,

        "Duplicate IDs":
            not duplicates,

        "Timestamp/duration consistency":
            not timestamp_errors,

        "Event index consistency":
            not index_errors,

        "Completion evidence":
            not no_completion,

        "Task/area consistency":
            not inconsistencies,

        "No negative durations":
            not negative,
    }

    for name, passed in checks.items():

        print(
            f"{'PASS' if passed else 'CHECK'}  "
            f"{name}"
        )

    print("\n" + "=" * 70)
    print("INTERPRETATION")
    print("=" * 70)

    print(
        "This validation checks whether the generated "
        "segments are structurally coherent and contain "
        "credible completion evidence."
    )

    print(
        "The remaining question is semantic: "
        "whether V5 missed real executions or merged "
        "multiple executions."
    )


if __name__ == "__main__":
    main()