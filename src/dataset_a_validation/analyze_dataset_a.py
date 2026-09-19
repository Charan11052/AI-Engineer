
import json
import statistics
import csv
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(r"D:\CHARAN RONGALI\AI Engineer")

OUTPUT_DIR = PROJECT_DIR / "outputs" / "dataset_a"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXECUTION_FILE = (
    OUTPUT_DIR / "dataset_a_execution_intervals.jsonl"
)

LABELED_EVENTS_FILE = (
    OUTPUT_DIR / "dataset_a_labeled_events.jsonl"
)

PROCESS_CSV = (
    OUTPUT_DIR / "dataset_a_process_summary.csv"
)

PROCESS_JSON = (
    OUTPUT_DIR / "dataset_a_process_summary.json"
)

APP_CSV = (
    OUTPUT_DIR / "dataset_a_app_summary.csv"
)

OPERATOR_CSV = (
    OUTPUT_DIR / "dataset_a_operator_summary.csv"
)


# ============================================================
# JSONL READER
# ============================================================

def read_jsonl(path):

    records = []

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line_number, line in enumerate(
            f,
            start=1
        ):

            line = line.strip()

            if not line:
                continue

            try:

                records.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as e:

                print(
                    f"WARNING: Could not parse "
                    f"{path} line {line_number}: {e}"
                )

    return records


# ============================================================
# PERCENTILE
# ============================================================

def percentile(values, p):

    if not values:
        return None

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    position = (
        (len(values) - 1)
        * p
        / 100
    )

    lower = int(position)

    upper = min(
        lower + 1,
        len(values) - 1
    )

    fraction = (
        position - lower
    )

    return (
        values[lower]
        +
        fraction
        *
        (
            values[upper]
            -
            values[lower]
        )
    )


# ============================================================
# DATETIME PARSER
# ============================================================

def parse_datetime(value):

    if value is None:
        return None

    try:

        return datetime.fromisoformat(
            value
        )

    except (ValueError, TypeError):

        return None


# ============================================================
# CSV WRITER
# ============================================================

def write_csv(
    path,
    rows,
    fieldnames
):

    with path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(rows)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("DATASET A PROCESS ANALYSIS")
    print("=" * 70)

    # ========================================================
    # LOAD EXECUTIONS
    # ========================================================

    print("\nLoading executions...")

    executions = read_jsonl(
        EXECUTION_FILE
    )

    print(
        f"Executions loaded: "
        f"{len(executions):,}"
    )

    if not executions:

        print(
            "ERROR: No executions found."
        )

        return

    # ========================================================
    # LOAD EVENTS
    # ========================================================

    print(
        "Loading labeled events..."
    )

    events = read_jsonl(
        LABELED_EVENTS_FILE
    )

    print(
        f"Events loaded: "
        f"{len(events):,}"
    )

    # ========================================================
    # DATA STRUCTURES
    # ========================================================

    process_durations = defaultdict(
        list
    )

    process_variants = defaultdict(
        Counter
    )

    process_sessions = defaultdict(
        set
    )

    process_cases = defaultdict(
        set
    )

    process_apps = defaultdict(
        Counter
    )

    process_event_counts = Counter()

    process_execution_count = Counter()

    # ========================================================
    # EXECUTION-LEVEL ANALYSIS
    # ========================================================

    print(
        "\nCalculating execution statistics..."
    )

    for execution in executions:

        process = execution.get(
            "process_code"
        )

        if process is None:
            process = "UNKNOWN"

        variant = execution.get(
            "process_variant"
        )

        session = execution.get(
            "session_id"
        )

        case_id = execution.get(
            "case_id"
        )

        start = execution.get(
            "start_ts"
        )

        end = execution.get(
            "end_ts"
        )

        # ----------------------------------------------------
        # Execution count
        # ----------------------------------------------------

        process_execution_count[
            process
        ] += 1

        # ----------------------------------------------------
        # Variant
        # ----------------------------------------------------

        # Preserve None explicitly.
        variant_key = (
            "None"
            if variant is None
            else str(variant)
        )

        process_variants[
            process
        ][variant_key] += 1

        # ----------------------------------------------------
        # Sessions/operators
        # ----------------------------------------------------

        if session is not None:

            process_sessions[
                process
            ].add(
                session
            )

        # ----------------------------------------------------
        # Cases
        # ----------------------------------------------------

        if case_id is not None:

            process_cases[
                process
            ].add(
                case_id
            )

        # ----------------------------------------------------
        # Duration
        # ----------------------------------------------------

        start_dt = parse_datetime(
            start
        )

        end_dt = parse_datetime(
            end
        )

        if (
            start_dt is not None
            and end_dt is not None
        ):

            duration = (
                end_dt - start_dt
            ).total_seconds()

            if duration >= 0:

                process_durations[
                    process
                ].append(
                    duration
                )

        # ----------------------------------------------------
        # Applications
        # ----------------------------------------------------

        apps = execution.get(
            "apps"
        )

        if isinstance(
            apps,
            list
        ):

            for app in apps:

                if app is not None:

                    process_apps[
                        process
                    ][str(app)] += 1

    # ========================================================
    # EVENT-LEVEL ANALYSIS
    # ========================================================

    print(
        "Calculating event statistics..."
    )

    execution_event_counts = Counter()

    for event in events:

        execution_id = event.get(
            "execution_id"
        )

        process = event.get(
            "process_code"
        )

        # Count events by execution
        if execution_id is not None:

            execution_event_counts[
                execution_id
            ] += 1

        # Count events by process
        if (
            process is not None
            and process != "NO_PROCESS"
        ):

            process_event_counts[
                process
            ] += 1

    # ========================================================
    # PROCESS SUMMARY
    # ========================================================

    rows = []

    for process in sorted(
        process_execution_count.keys()
    ):

        durations = process_durations.get(
            process,
            []
        )

        count = process_execution_count[
            process
        ]

        # ----------------------------------------------------
        # Duration statistics
        # ----------------------------------------------------

        total_seconds = sum(
            durations
        )

        mean_seconds = (
            statistics.mean(
                durations
            )
            if durations
            else None
        )

        median_seconds = (
            statistics.median(
                durations
            )
            if durations
            else None
        )

        min_seconds = (
            min(durations)
            if durations
            else None
        )

        max_seconds = (
            max(durations)
            if durations
            else None
        )

        p75_seconds = percentile(
            durations,
            75
        )

        p90_seconds = percentile(
            durations,
            90
        )

        p95_seconds = percentile(
            durations,
            95
        )

        # ----------------------------------------------------
        # Event statistics
        # ----------------------------------------------------

        event_count = process_event_counts.get(
            process,
            0
        )

        events_per_execution = (
            event_count / count
            if count > 0
            else 0
        )

        # ----------------------------------------------------
        # Variant statistics
        # ----------------------------------------------------

        variants = process_variants.get(
            process,
            Counter()
        )

        variant_string = "; ".join(
            f"{key}={value}"
            for key, value in sorted(
                variants.items()
            )
        )

        # ----------------------------------------------------
        # Application statistics
        # ----------------------------------------------------

        apps = process_apps.get(
            process,
            Counter()
        )

        app_string = "; ".join(
            f"{app}={count}"
            for app, count in apps.most_common()
        )

        # ----------------------------------------------------
        # Sessions/operators
        # ----------------------------------------------------

        session_count = len(
            process_sessions.get(
                process,
                set()
            )
        )

        case_count = len(
            process_cases.get(
                process,
                set()
            )
        )

        # ----------------------------------------------------
        # Time
        # ----------------------------------------------------

        total_hours = (
            total_seconds / 3600
        )

        mean_minutes = (
            mean_seconds / 60
            if mean_seconds is not None
            else None
        )

        # ----------------------------------------------------
        # Summary row
        # ----------------------------------------------------

        rows.append({

            "process_code": process,

            "executions": count,

            "sessions": session_count,

            "unique_cases": case_count,

            "total_seconds": round(
                total_seconds,
                2
            ),

            "total_hours": round(
                total_hours,
                3
            ),

            "mean_seconds": (
                round(
                    mean_seconds,
                    2
                )
                if mean_seconds is not None
                else None
            ),

            "mean_minutes": (
                round(
                    mean_minutes,
                    2
                )
                if mean_minutes is not None
                else None
            ),

            "median_seconds": (
                round(
                    median_seconds,
                    2
                )
                if median_seconds is not None
                else None
            ),

            "p75_seconds": (
                round(
                    p75_seconds,
                    2
                )
                if p75_seconds is not None
                else None
            ),

            "p90_seconds": (
                round(
                    p90_seconds,
                    2
                )
                if p90_seconds is not None
                else None
            ),

            "p95_seconds": (
                round(
                    p95_seconds,
                    2
                )
                if p95_seconds is not None
                else None
            ),

            "min_seconds": (
                round(
                    min_seconds,
                    2
                )
                if min_seconds is not None
                else None
            ),

            "max_seconds": (
                round(
                    max_seconds,
                    2
                )
                if max_seconds is not None
                else None
            ),

            "event_count": event_count,

            "events_per_execution": round(
                events_per_execution,
                2
            ),

            "variants": variant_string,

            "applications": app_string
        })

    # ========================================================
    # SORT BY TOTAL TIME
    # ========================================================

    rows.sort(
        key=lambda row: (
            row["total_seconds"]
            if row["total_seconds"] is not None
            else 0
        ),
        reverse=True
    )

    # ========================================================
    # WRITE PROCESS CSV
    # ========================================================

    process_fields = [
        "process_code",
        "executions",
        "sessions",
        "unique_cases",
        "total_seconds",
        "total_hours",
        "mean_seconds",
        "mean_minutes",
        "median_seconds",
        "p75_seconds",
        "p90_seconds",
        "p95_seconds",
        "min_seconds",
        "max_seconds",
        "event_count",
        "events_per_execution",
        "variants",
        "applications"
    ]

    write_csv(
        PROCESS_CSV,
        rows,
        process_fields
    )

    # ========================================================
    # WRITE PROCESS JSON
    # ========================================================

    with PROCESS_JSON.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            rows,
            f,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # APPLICATION SUMMARY
    # ========================================================

    app_rows = []

    for process in sorted(
        process_apps.keys()
    ):

        apps = process_apps[
            process
        ]

        total_executions = (
            process_execution_count[
                process
            ]
        )

        for app, count in apps.most_common():

            share = (
                count
                /
                total_executions
                if total_executions
                else 0
            )

            app_rows.append({

                "process_code": process,

                "application": app,

                "execution_app_count": count,

                "process_executions": (
                    total_executions
                ),

                "share_of_executions": round(
                    share,
                    4
                )
            })

    app_fields = [
        "process_code",
        "application",
        "execution_app_count",
        "process_executions",
        "share_of_executions"
    ]

    write_csv(
        APP_CSV,
        app_rows,
        app_fields
    )

    # ========================================================
    # OPERATOR / SESSION SUMMARY
    # ========================================================

    operator_process_counts = defaultdict(
        Counter
    )

    for execution in executions:

        process = execution.get(
            "process_code"
        )

        session = execution.get(
            "session_id"
        )

        if process is not None and session is not None:

            operator_process_counts[
                session
            ][process] += 1

    operator_rows = []

    for session in sorted(
        operator_process_counts.keys()
    ):

        processes = (
            operator_process_counts[
                session
            ]
        )

        for process, count in (
            processes.most_common()
        ):

            operator_rows.append({

                "session_id": session,

                "process_code": process,

                "executions": count
            })

    operator_fields = [
        "session_id",
        "process_code",
        "executions"
    ]

    write_csv(
        OPERATOR_CSV,
        operator_rows,
        operator_fields
    )

    # ========================================================
    # PRINT MAIN RESULTS
    # ========================================================

    print(
        "\n" + "=" * 70
    )

    print(
        "PROCESS SUMMARY"
    )

    print(
        "=" * 70
    )

    print(
        f"{'Process':<10}"
        f"{'Exec':>8}"
        f"{'Hours':>12}"
        f"{'Mean(min)':>12}"
        f"{'Median(s)':>12}"
        f"{'P90(s)':>12}"
        f"{'Events':>12}"
    )

    print(
        "-" * 78
    )

    for row in rows:

        mean_minutes = row[
            "mean_minutes"
        ]

        median_seconds = row[
            "median_seconds"
        ]

        p90_seconds = row[
            "p90_seconds"
        ]

        print(
            f"{row['process_code']:<10}"
            f"{row['executions']:>8}"
            f"{row['total_hours']:>12.3f}"
            f"{mean_minutes:>12.2f}"
            f"{median_seconds:>12.2f}"
            f"{p90_seconds:>12.2f}"
            f"{row['event_count']:>12}"
        )

    # ========================================================
    # TOP PROCESSES
    # ========================================================

    print(
        "\n" + "=" * 70
    )

    print(
        "TOP PROCESSES BY TOTAL TIME"
    )

    print(
        "=" * 70
    )

    for rank, row in enumerate(
        rows[:10],
        start=1
    ):

        print(
            f"{rank:>2}. "
            f"Process {row['process_code']} — "
            f"{row['total_hours']:.3f} hours — "
            f"{row['executions']} executions — "
            f"median "
            f"{row['median_seconds']:.2f}s"
        )

    # ========================================================
    # OUTPUT FILES
    # ========================================================

    print(
        "\n" + "=" * 70
    )

    print(
        "OUTPUT FILES"
    )

    print(
        "=" * 70
    )

    print(
        f"Process CSV    : {PROCESS_CSV}"
    )

    print(
        f"Process JSON   : {PROCESS_JSON}"
    )

    print(
        f"Application CSV: {APP_CSV}"
    )

    print(
        f"Operator CSV   : {OPERATOR_CSV}"
    )

    print(
        "\nDataset A analysis complete."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
