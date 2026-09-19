from pathlib import Path
import json
from collections import defaultdict


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "outputs" / "dataset_b"
SEGMENTS_FILE = OUTPUT_DIR / "dataset_b_segments_v8.jsonl"

OUTPUT_FILE = OUTPUT_DIR / "dataset_b_automation_roi_v8.json"


# ============================================================
# CONFIGURATION
# ============================================================

# Scenario assumption:
# automation is assumed to remove 70% of the observed execution
# time for the selected automation opportunity.
AUTOMATION_SAVING_RATE = 0.70


# ============================================================
# LOAD
# ============================================================

def load_segments():

    if not SEGMENTS_FILE.exists():
        raise FileNotFoundError(
            f"V8 segments not found:\n{SEGMENTS_FILE}"
        )

    segments = []

    with SEGMENTS_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            segments.append(
                json.loads(line)
            )

    return segments


# ============================================================
# HELPERS
# ============================================================

def get_duration(segment):

    if segment.get("duration_seconds") is not None:
        return float(
            segment["duration_seconds"]
        )

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

    if start is not None and end is not None:

        return max(
            0.0,
            (float(end) - float(start)) / 1000.0
        )

    return 0.0


def get_task(segment):

    return (
        segment.get("task")
        or segment.get("task_type")
        or segment.get("task_name")
        or "UNKNOWN"
    )


def get_area(segment):

    return (
        segment.get("business_area")
        or segment.get("businessArea")
        or "UNKNOWN"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("DATASET B V8 — AUTOMATION ROI ANALYSIS")
    print("=" * 70)

    segments = load_segments()

    print()
    print(f"V8 segments loaded : {len(segments)}")

    if not segments:
        print("No segments found.")
        return

    # --------------------------------------------------------
    # GROUP BY TASK
    # --------------------------------------------------------

    grouped = defaultdict(list)

    for segment in segments:

        task = get_task(segment)

        duration = get_duration(segment)

        grouped[task].append(duration)

    # --------------------------------------------------------
    # TASK ROI
    # --------------------------------------------------------

    results = []

    for task, durations in grouped.items():

        execution_count = len(durations)

        total_seconds = sum(durations)

        average_seconds = (
            total_seconds / execution_count
            if execution_count
            else 0
        )

        potential_saving_seconds = (
            total_seconds *
            AUTOMATION_SAVING_RATE
        )

        remaining_seconds = (
            total_seconds -
            potential_saving_seconds
        )

        average_saving_seconds = (
            average_seconds *
            AUTOMATION_SAVING_RATE
        )

        results.append({

            "task": task,

            "execution_count":
                execution_count,

            "total_observed_seconds":
                round(
                    total_seconds,
                    2
                ),

            "average_execution_seconds":
                round(
                    average_seconds,
                    2
                ),

            "assumed_automation_saving_rate":
                AUTOMATION_SAVING_RATE,

            "potential_saving_seconds":
                round(
                    potential_saving_seconds,
                    2
                ),

            "potential_saving_minutes":
                round(
                    potential_saving_seconds / 60,
                    2
                ),

            "remaining_seconds":
                round(
                    remaining_seconds,
                    2
                ),

            "average_saving_seconds_per_execution":
                round(
                    average_saving_seconds,
                    2
                )
        })

    # Sort by potential saving

    results.sort(
        key=lambda x:
            x["potential_saving_seconds"],
        reverse=True
    )

    # --------------------------------------------------------
    # PRINT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TASK-LEVEL AUTOMATION ROI")
    print("=" * 70)

    print(
        f"{'TASK':<28}"
        f"{'COUNT':>7}"
        f"{'AVG(s)':>10}"
        f"{'TOTAL(s)':>12}"
        f"{'SAVE(s)':>12}"
        f"{'SAVE(min)':>12}"
    )

    print("-" * 81)

    for result in results:

        print(
            f"{result['task']:<28}"
            f"{result['execution_count']:>7}"
            f"{result['average_execution_seconds']:>10.2f}"
            f"{result['total_observed_seconds']:>12.2f}"
            f"{result['potential_saving_seconds']:>12.2f}"
            f"{result['potential_saving_minutes']:>12.2f}"
        )

    # --------------------------------------------------------
    # BUSINESS AREA ROI
    # --------------------------------------------------------

    area_data = defaultdict(
        lambda: {
            "count": 0,
            "seconds": 0.0
        }
    )

    for segment in segments:

        area = get_area(segment)

        duration = get_duration(segment)

        area_data[area]["count"] += 1

        area_data[area]["seconds"] += duration

    print()
    print("=" * 70)
    print("BUSINESS-AREA AUTOMATION ROI")
    print("=" * 70)

    for area, data in sorted(
        area_data.items(),
        key=lambda x: x[1]["seconds"],
        reverse=True
    ):

        saving = (
            data["seconds"] *
            AUTOMATION_SAVING_RATE
        )

        print(
            f"{area:<20}"
            f"count={data['count']:>3}  "
            f"observed={data['seconds']:>9.2f}s  "
            f"potential_saving={saving:>9.2f}s"
        )

    # --------------------------------------------------------
    # OVERALL
    # --------------------------------------------------------

    total_seconds = sum(
        get_duration(x)
        for x in segments
    )

    total_saving = (
        total_seconds *
        AUTOMATION_SAVING_RATE
    )

    print()
    print("=" * 70)
    print("OVERALL")
    print("=" * 70)

    print(
        f"Segments                  : "
        f"{len(segments)}"
    )

    print(
        f"Observed execution time   : "
        f"{total_seconds:.2f}s "
        f"({total_seconds / 60:.2f} min)"
    )

    print(
        f"Assumed saving rate       : "
        f"{AUTOMATION_SAVING_RATE * 100:.0f}%"
    )

    print(
        f"Potential time saving     : "
        f"{total_saving:.2f}s "
        f"({total_saving / 60:.2f} min)"
    )

    print()
    print(
        "IMPORTANT: The 70% saving figure is a "
        "scenario assumption, not an observed measurement."
    )

    # --------------------------------------------------------
    # SAVE JSON
    # --------------------------------------------------------

    output = {

        "method":
            "V8 segment-level automation ROI",

        "input":
            str(SEGMENTS_FILE),

        "segments":
            len(segments),

        "automation_saving_rate":
            AUTOMATION_SAVING_RATE,

        "assumption":
            "70% of observed execution time "
            "could be saved under an automation scenario",

        "total_observed_seconds":
            round(
                total_seconds,
                2
            ),

        "potential_saving_seconds":
            round(
                total_saving,
                2
            ),

        "potential_saving_minutes":
            round(
                total_saving / 60,
                2
            ),

        "task_results":
            results
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print(
        f"Output written to:\n{OUTPUT_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()