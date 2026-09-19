
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(r"D:\CHARAN RONGALI\AI Engineer")

DATASET_DIR = PROJECT_DIR / "data" / "dataset_a"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "dataset_a"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXECUTION_FILE = OUTPUT_DIR / "dataset_a_execution_intervals.jsonl"
REPORT_FILE = OUTPUT_DIR / "dataset_a_gt_validation_report.json"

# Timestamp tolerance used when comparing our extraction
# against the manifest.
TIMESTAMP_TOLERANCE_SECONDS = 2.0


# ============================================================
# TIMESTAMP UTILITIES
# ============================================================

def parse_timestamp(value):
    """
    Convert ISO timestamps / milliseconds / seconds
    into UTC datetime.
    """

    if value is None:
        return None

    if isinstance(value, (int, float)):

        if value > 10_000_000_000:
            return datetime.fromtimestamp(
                value / 1000,
                tz=timezone.utc
            )

        return datetime.fromtimestamp(
            value,
            tz=timezone.utc
        )

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return None

        try:

            value = value.replace("Z", "+00:00")

            dt = datetime.fromisoformat(value)

            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=timezone.utc
                )

            return dt.astimezone(timezone.utc)

        except ValueError:
            return None

    return None


# ============================================================
# JSONL READER
# ============================================================

def read_jsonl(path):

    records = []

    if not path.exists():
        return records

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

            except json.JSONDecodeError:

                print(
                    f"WARNING: Invalid JSON in "
                    f"{path}:{line_number}"
                )

    return records


# ============================================================
# GT EVENT TYPE
# ============================================================

def get_gt_event_type(record):

    return (
        record.get("event")
        or record.get("event_type")
        or record.get("type")
        or record.get("action")
    )


# ============================================================
# SESSION DISCOVERY
# ============================================================

def find_sessions():

    sessions = {}

    for gt_file in DATASET_DIR.rglob("gt.jsonl"):

        session_dir = gt_file.parent

        sessions[str(session_dir)] = session_dir

    return sorted(
        sessions.values(),
        key=lambda p: p.name
    )


# ============================================================
# LOAD MANIFEST EXECUTIONS
# ============================================================

def load_manifest_executions(session_dir):
    """
    Load authoritative execution-level ground truth
    from gt_manifest.json.

    Manifest structure:

        processes[]
            -> executions[]
    """

    manifest_path = (
        session_dir / "gt_manifest.json"
    )

    if not manifest_path.exists():
        return [], {
            "error": "manifest_not_found"
        }

    try:

        with manifest_path.open(
            "r",
            encoding="utf-8"
        ) as f:

            manifest = json.load(f)

    except (json.JSONDecodeError, OSError) as e:

        return [], {
            "error": f"manifest_read_error: {e}"
        }

    executions = []

    for process_group in manifest.get(
        "processes",
        []
    ):

        process_code = process_group.get(
            "code"
        )

        family_name = process_group.get(
            "family_name"
        )

        domain = process_group.get(
            "domain"
        )

        for execution in process_group.get(
            "executions",
            []
        ):

            record = dict(execution)

            # Normalize process information.
            record["process_code"] = (
                record.get("code")
                or process_code
            )

            record["family_name"] = family_name
            record["domain"] = domain

            record["_start_dt"] = parse_timestamp(
                record.get("start_ts")
            )

            record["_end_dt"] = parse_timestamp(
                record.get("end_ts")
            )

            executions.append(record)

    executions.sort(
        key=lambda x: (
            x["_start_dt"]
            if x["_start_dt"]
            else datetime.max.replace(
                tzinfo=timezone.utc
            )
        )
    )

    return executions, {
        "error": None,
        "schema_version": manifest.get(
            "schema_version"
        ),
        "run_id": manifest.get(
            "run_id"
        ),
        "theme": manifest.get(
            "theme"
        )
    }


# ============================================================
# LOAD OUR EXTRACTED EXECUTIONS
# ============================================================

def load_our_executions():

    executions_by_session = defaultdict(list)

    if not EXECUTION_FILE.exists():

        print(
            f"ERROR: Could not find:\n"
            f"{EXECUTION_FILE}"
        )

        return executions_by_session

    records = read_jsonl(
        EXECUTION_FILE
    )

    for record in records:

        session_id = record.get(
            "session_id"
        )

        if session_id is None:
            continue

        record["_start_dt"] = parse_timestamp(
            record.get("start_ts")
        )

        record["_end_dt"] = parse_timestamp(
            record.get("end_ts")
        )

        executions_by_session[
            session_id
        ].append(record)

    for session_id in executions_by_session:

        executions_by_session[
            session_id
        ].sort(
            key=lambda x: (
                x["_start_dt"]
                if x["_start_dt"]
                else datetime.max.replace(
                    tzinfo=timezone.utc
                )
            )
        )

    return executions_by_session


# ============================================================
# ANALYZE RAW GT EVENTS
# ============================================================

def analyze_gt_file(gt_path):
    """
    Analyze gt.jsonl separately.

    IMPORTANT:
    process_started count is NOT treated as the
    authoritative execution count.
    """

    records = read_jsonl(
        gt_path
    )

    event_counter = Counter()
    process_started_counter = Counter()

    process_started_records = []

    timestamps_missing = 0

    for record in records:

        event_type = get_gt_event_type(
            record
        )

        event_counter[event_type] += 1

        if event_type == "process_started":

            process_code = (
                record.get("process_code")
                or record.get("current_process")
            )

            variant = (
                record.get("process_variant")
                or record.get("variant")
            )

            timestamp = parse_timestamp(
                record.get("ts_utc")
                or record.get("timestamp_iso")
                or record.get("timestamp_ms")
            )

            if timestamp is None:
                timestamps_missing += 1

            process_started_counter[
                process_code
            ] += 1

            process_started_records.append({
                "timestamp": timestamp,
                "process_code": process_code,
                "process_variant": variant,
                "case_id": record.get(
                    "case_id"
                ),
                "record": record
            })

    process_started_records.sort(
        key=lambda x: (
            x["timestamp"]
            if x["timestamp"]
            else datetime.max.replace(
                tzinfo=timezone.utc
            )
        )
    )

    return {
        "total_records": len(records),
        "event_counts": dict(
            event_counter
        ),
        "process_started_count": len(
            process_started_records
        ),
        "process_distribution": dict(
            process_started_counter
        ),
        "timestamps_missing": timestamps_missing,
        "process_started_records":
            process_started_records
    }


# ============================================================
# EXECUTION MATCHING
# ============================================================

def match_manifest_to_extracted(
    manifest_executions,
    extracted_executions
):
    """
    Match authoritative manifest executions
    against our extracted executions.

    Primary identity:
        process_code + case_id

    Secondary validation:
        start timestamp proximity

    This avoids incorrectly treating every
    process_started event as a separate execution.
    """

    matched = []
    missing_gt = []
    extra_extracted = []

    used_extracted = set()

    # --------------------------------------------------------
    # Match every manifest execution
    # --------------------------------------------------------

    for gt_index, gt in enumerate(
        manifest_executions
    ):

        gt_code = gt.get(
            "process_code"
        )

        gt_case = gt.get(
            "case_id"
        )

        gt_start = gt.get(
            "_start_dt"
        )

        candidates = []

        for our_index, our in enumerate(
            extracted_executions
        ):

            if our_index in used_extracted:
                continue

            our_code = our.get(
                "process_code"
            )

            our_case = our.get(
                "case_id"
            )

            # Strong identity match.
            if (
                gt_code is not None
                and our_code != gt_code
            ):
                continue

            if (
                gt_case is not None
                and our_case is not None
                and our_case != gt_case
            ):
                continue

            our_start = our.get(
                "_start_dt"
            )

            if gt_start is not None and our_start is not None:

                start_difference = abs(
                    (
                        our_start - gt_start
                    ).total_seconds()
                )

            else:

                start_difference = float("inf")

            candidates.append(
                (
                    start_difference,
                    our_index,
                    our
                )
            )

        if not candidates:

            missing_gt.append({
                "reason": "no_matching_extraction",
                "process_code": gt_code,
                "case_id": gt_case,
                "exec_id": gt.get("exec_id"),
                "start_ts": gt.get("start_ts")
            })

            continue

        candidates.sort(
            key=lambda x: x[0]
        )

        difference, our_index, our = (
            candidates[0]
        )

        used_extracted.add(
            our_index
        )

        matched.append({
            "manifest": gt,
            "extracted": our,
            "start_difference_seconds":
                None
                if difference == float("inf")
                else difference
        })

    # --------------------------------------------------------
    # Anything extracted but not matched = extra
    # --------------------------------------------------------

    for index, execution in enumerate(
        extracted_executions
    ):

        if index not in used_extracted:

            extra_extracted.append(
                execution
            )

    return (
        matched,
        missing_gt,
        extra_extracted
    )


# ============================================================
# VALIDATE MATCHED EXECUTIONS
# ============================================================

def validate_matches(matches):

    problems = []

    start_differences = []
    end_differences = []

    for item in matches:

        gt = item["manifest"]
        our = item["extracted"]

        gt_start = gt.get(
            "_start_dt"
        )

        our_start = our.get(
            "_start_dt"
        )

        gt_end = gt.get(
            "_end_dt"
        )

        our_end = our.get(
            "_end_dt"
        )

        exec_id = (
            gt.get("exec_id")
            or gt.get("case_id")
        )

        process_code = gt.get(
            "process_code"
        )

        # ----------------------------------------------------
        # Start timestamp
        # ----------------------------------------------------

        if (
            gt_start is not None
            and our_start is not None
        ):

            difference = abs(
                (
                    our_start - gt_start
                ).total_seconds()
            )

            start_differences.append(
                difference
            )

            if difference > TIMESTAMP_TOLERANCE_SECONDS:

                problems.append({
                    "type":
                        "start_timestamp_mismatch",
                    "exec_id":
                        exec_id,
                    "process_code":
                        process_code,
                    "difference_seconds":
                        difference,
                    "gt_start":
                        gt.get("start_ts"),
                    "our_start":
                        our.get("start_ts")
                })

        # ----------------------------------------------------
        # End timestamp
        # ----------------------------------------------------

        if (
            gt_end is not None
            and our_end is not None
        ):

            difference = abs(
                (
                    our_end - gt_end
                ).total_seconds()
            )

            end_differences.append(
                difference
            )

            if difference > TIMESTAMP_TOLERANCE_SECONDS:

                problems.append({
                    "type":
                        "end_timestamp_mismatch",
                    "exec_id":
                        exec_id,
                    "process_code":
                        process_code,
                    "difference_seconds":
                        difference,
                    "gt_end":
                        gt.get("end_ts"),
                    "our_end":
                        our.get("end_ts")
                })

        elif gt_end is None:

            # GT legitimately has an open-ended execution.
            if our_end is not None:

                problems.append({
                    "type":
                        "unexpected_extracted_end",
                    "exec_id":
                        exec_id,
                    "process_code":
                        process_code,
                    "gt_end":
                        None,
                    "our_end":
                        our.get("end_ts")
                })

        elif our_end is None:

            problems.append({
                "type":
                    "missing_extracted_end",
                "exec_id":
                    exec_id,
                "process_code":
                    process_code,
                "gt_end":
                    gt.get("end_ts"),
                "our_end":
                    None
            })

        # ----------------------------------------------------
        # Process code
        # ----------------------------------------------------

        if (
            gt.get("process_code")
            != our.get("process_code")
        ):

            problems.append({
                "type":
                    "process_code_mismatch",
                "exec_id":
                    exec_id,
                "gt":
                    gt.get("process_code"),
                "our":
                    our.get("process_code")
            })

        # ----------------------------------------------------
        # Case ID
        # ----------------------------------------------------

        if (
            gt.get("case_id") is not None
            and our.get("case_id") is not None
            and gt.get("case_id")
            != our.get("case_id")
        ):

            problems.append({
                "type":
                    "case_id_mismatch",
                "exec_id":
                    exec_id,
                "gt":
                    gt.get("case_id"),
                "our":
                    our.get("case_id")
            })

    return {
        "problems": problems,
        "start_timestamp_count":
            len(start_differences),
        "end_timestamp_count":
            len(end_differences),
        "max_start_difference_seconds":
            max(start_differences)
            if start_differences
            else None,
        "max_end_difference_seconds":
            max(end_differences)
            if end_differences
            else None,
        "mean_start_difference_seconds":
            sum(start_differences)
            / len(start_differences)
            if start_differences
            else None,
        "mean_end_difference_seconds":
            sum(end_differences)
            / len(end_differences)
            if end_differences
            else None
    }


# ============================================================
# CHECK EXTRACTED INTERVALS
# ============================================================

def check_execution_intervals(
    executions
):

    problems = []

    previous_end = None

    for execution in executions:

        start = execution.get(
            "_start_dt"
        )

        end = execution.get(
            "_end_dt"
        )

        process = execution.get(
            "process_code"
        )

        execution_id = (
            execution.get("execution_id")
            or execution.get("exec_id")
            or execution.get("case_id")
        )

        # Missing start
        if start is None:

            problems.append({
                "type":
                    "missing_start",
                "execution_id":
                    execution_id,
                "process":
                    process
            })

            continue

        # Missing end is allowed because
        # the manifest itself contains open-ended
        # executions.
        #
        # Therefore we do NOT automatically mark
        # missing end as an error.

        # Negative duration
        if (
            end is not None
            and end < start
        ):

            problems.append({
                "type":
                    "negative_duration",
                "execution_id":
                    execution_id,
                "process":
                    process,
                "start":
                    start.isoformat(),
                "end":
                    end.isoformat()
            })

        # Overlap
        if (
            previous_end is not None
            and start < previous_end
        ):

            problems.append({
                "type":
                    "overlapping_execution",
                "execution_id":
                    execution_id,
                "process":
                    process,
                "start":
                    start.isoformat(),
                "previous_end":
                    previous_end.isoformat()
            })

        if end is not None:
            previous_end = end

    return problems


# ============================================================
# PROCESS / VARIANT DISTRIBUTIONS
# ============================================================

def build_distributions(
    manifest_executions,
    extracted_executions
):

    manifest_process = Counter()
    extracted_process = Counter()

    manifest_variant = Counter()
    extracted_variant = Counter()

    for execution in manifest_executions:

        process = execution.get(
            "process_code"
        )

        variant = execution.get(
            "variant"
        )

        manifest_process[
            process
        ] += 1

        manifest_variant[
            variant
        ] += 1

    for execution in extracted_executions:

        process = execution.get(
            "process_code"
        )

        variant = (
            execution.get("process_variant")
            or execution.get("variant")
        )

        extracted_process[
            process
        ] += 1

        extracted_variant[
            variant
        ] += 1

    return (
        manifest_process,
        extracted_process,
        manifest_variant,
        extracted_variant
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("VALIDATING DATASET A GROUND TRUTH")
    print("=" * 70)

    sessions = find_sessions()

    print(
        f"\nSessions found: {len(sessions)}"
    )

    our_executions = (
        load_our_executions()
    )

    total_manifest_executions = 0
    total_extracted_executions = 0

    total_matched = 0
    total_missing = 0
    total_extra = 0

    all_matching_problems = []
    all_interval_problems = []

    manifest_process = Counter()
    extracted_process = Counter()

    manifest_variant = Counter()
    extracted_variant = Counter()

    session_results = []

    # ========================================================
    # PROCESS EACH SESSION
    # ========================================================

    for number, session_dir in enumerate(
        sessions,
        start=1
    ):

        session_id = session_dir.name

        print(
            f"\n[{number}/{len(sessions)}] "
            f"{session_id}"
        )

        # ----------------------------------------------------
        # Load manifest
        # ----------------------------------------------------

        manifest_executions, manifest_info = (
            load_manifest_executions(
                session_dir
            )
        )

        # ----------------------------------------------------
        # Analyze raw GT
        # ----------------------------------------------------

        gt_path = (
            session_dir / "gt.jsonl"
        )

        gt_analysis = analyze_gt_file(
            gt_path
        )

        # ----------------------------------------------------
        # Our executions
        # ----------------------------------------------------

        extracted = our_executions.get(
            session_id,
            []
        )

        # ----------------------------------------------------
        # Counters
        # ----------------------------------------------------

        total_manifest_executions += (
            len(manifest_executions)
        )

        total_extracted_executions += (
            len(extracted)
        )

        for execution in manifest_executions:

            manifest_process[
                execution.get(
                    "process_code"
                )
            ] += 1

            manifest_variant[
                execution.get(
                    "variant"
                )
            ] += 1

        for execution in extracted:

            extracted_process[
                execution.get(
                    "process_code"
                )
            ] += 1

            extracted_variant[
                execution.get(
                    "process_variant"
                )
                or execution.get(
                    "variant"
                )
            ] += 1

        # ----------------------------------------------------
        # Interval validation
        # ----------------------------------------------------

        interval_problems = (
            check_execution_intervals(
                extracted
            )
        )

        for problem in interval_problems:

            all_interval_problems.append({
                "session_id":
                    session_id,
                **problem
            })

        # ----------------------------------------------------
        # Match manifest -> extracted
        # ----------------------------------------------------

        matched, missing, extra = (
            match_manifest_to_extracted(
                manifest_executions,
                extracted
            )
        )

        total_matched += len(
            matched
        )

        total_missing += len(
            missing
        )

        total_extra += len(
            extra
        )

        # ----------------------------------------------------
        # Validate matched timestamps etc.
        # ----------------------------------------------------

        match_validation = (
            validate_matches(
                matched
            )
        )

        for problem in (
            match_validation["problems"]
        ):

            all_matching_problems.append({
                "session_id":
                    session_id,
                **problem
            })

        # ----------------------------------------------------
        # Session result
        # ----------------------------------------------------

        session_results.append({

            "session_id":
                session_id,

            "raw_gt_process_started":
                gt_analysis[
                    "process_started_count"
                ],

            "manifest_executions":
                len(
                    manifest_executions
                ),

            "extracted_executions":
                len(
                    extracted
                ),

            "matched_executions":
                len(
                    matched
                ),

            "missing_manifest_executions":
                len(
                    missing
                ),

            "extra_extracted_executions":
                len(
                    extra
                ),

            "interval_problems":
                len(
                    interval_problems
                ),

            "matching_problems":
                len(
                    match_validation[
                        "problems"
                    ]
                ),

            "max_start_difference_seconds":
                match_validation[
                    "max_start_difference_seconds"
                ],

            "max_end_difference_seconds":
                match_validation[
                    "max_end_difference_seconds"
                ],

            "manifest_metadata":
                manifest_info
        })

        # ----------------------------------------------------
        # Print session summary
        # ----------------------------------------------------

        print(
            f"  Raw process_started : "
            f"{gt_analysis['process_started_count']}"
        )

        print(
            f"  Manifest executions : "
            f"{len(manifest_executions)}"
        )

        print(
            f"  Our executions      : "
            f"{len(extracted)}"
        )

        print(
            f"  Matched             : "
            f"{len(matched)}"
        )

        print(
            f"  Missing GT          : "
            f"{len(missing)}"
        )

        print(
            f"  Extra extracted     : "
            f"{len(extra)}"
        )

        print(
            f"  Validation problems : "
            f"{len(match_validation['problems'])}"
        )

    # ========================================================
    # FINAL METRICS
    # ========================================================

    if total_manifest_executions:

        execution_match_rate = (
            total_matched
            / total_manifest_executions
        )

    else:

        execution_match_rate = 0

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n")
    print("=" * 70)
    print("GROUND TRUTH VALIDATION SUMMARY")
    print("=" * 70)

    print(
        f"\nSessions                  : "
        f"{len(sessions)}"
    )

    print(
        f"Manifest executions      : "
        f"{total_manifest_executions}"
    )

    print(
        f"Our extracted executions : "
        f"{total_extracted_executions}"
    )

    print(
        f"Matched executions       : "
        f"{total_matched}"
    )

    print(
        f"Missing GT executions    : "
        f"{total_missing}"
    )

    print(
        f"Extra extracted          : "
        f"{total_extra}"
    )

    print(
        f"Execution match rate     : "
        f"{execution_match_rate:.2%}"
    )

    print(
        f"Interval problems        : "
        f"{len(all_interval_problems)}"
    )

    print(
        f"Matching problems        : "
        f"{len(all_matching_problems)}"
    )

    # ========================================================
    # PROCESS COMPARISON
    # ========================================================

    print("\n")
    print("=" * 70)
    print("PROCESS COUNT COMPARISON")
    print("=" * 70)

    all_processes = sorted(
        set(manifest_process)
        | set(extracted_process),
        key=lambda x: str(x)
    )

    print(
        f"\n{'Process':<10}"
        f"{'GT':>10}"
        f"{'Extracted':>12}"
        f"{'Difference':>12}"
    )

    print("-" * 46)

    process_difference = {}

    for process in all_processes:

        gt_count = manifest_process[
            process
        ]

        our_count = extracted_process[
            process
        ]

        diff = (
            gt_count
            - our_count
        )

        process_difference[
            str(process)
        ] = diff

        print(
            f"{str(process):<10}"
            f"{gt_count:>10}"
            f"{our_count:>12}"
            f"{diff:>12}"
        )

    # ========================================================
    # VARIANT COMPARISON
    # ========================================================

    print("\n")
    print("=" * 70)
    print("VARIANT COUNT COMPARISON")
    print("=" * 70)

    all_variants = sorted(
        set(manifest_variant)
        | set(extracted_variant),
        key=lambda x: str(x)
    )

    print(
        f"\n{'Variant':<20}"
        f"{'GT':>10}"
        f"{'Extracted':>12}"
        f"{'Difference':>12}"
    )

    print("-" * 54)

    variant_difference = {}

    for variant in all_variants:

        gt_count = manifest_variant[
            variant
        ]

        our_count = extracted_variant[
            variant
        ]

        diff = (
            gt_count
            - our_count
        )

        variant_difference[
            str(variant)
        ] = diff

        print(
            f"{str(variant):<20}"
            f"{gt_count:>10}"
            f"{our_count:>12}"
            f"{diff:>12}"
        )

    # ========================================================
    # FIRST PROBLEMS
    # ========================================================

    if all_matching_problems:

        print("\n")
        print("=" * 70)
        print("FIRST 20 MATCHING PROBLEMS")
        print("=" * 70)

        for problem in (
            all_matching_problems[:20]
        ):

            print(
                json.dumps(
                    problem,
                    ensure_ascii=False,
                    indent=2
                )
            )

    if all_interval_problems:

        print("\n")
        print("=" * 70)
        print("FIRST 20 INTERVAL PROBLEMS")
        print("=" * 70)

        for problem in (
            all_interval_problems[:20]
        ):

            print(
                json.dumps(
                    problem,
                    ensure_ascii=False,
                    indent=2
                )
            )

    # ========================================================
    # SAVE REPORT
    # ========================================================

    report = {

        "dataset":
            str(DATASET_DIR),

        "sessions":
            len(sessions),

        "manifest_executions":
            total_manifest_executions,

        "our_executions":
            total_extracted_executions,

        "matched_executions":
            total_matched,

        "missing_manifest_executions":
            total_missing,

        "extra_extracted_executions":
            total_extra,

        "execution_match_rate":
            round(
                execution_match_rate,
                6
            ),

        "interval_problems":
            len(
                all_interval_problems
            ),

        "matching_problems":
            len(
                all_matching_problems
            ),

        "manifest_process_distribution":
            dict(
                manifest_process
            ),

        "extracted_process_distribution":
            dict(
                extracted_process
            ),

        "process_difference":
            process_difference,

        "manifest_variant_distribution":
            {
                str(k): v
                for k, v
                in manifest_variant.items()
            },

        "extracted_variant_distribution":
            {
                str(k): v
                for k, v
                in extracted_variant.items()
            },

        "variant_difference":
            variant_difference,

        "session_results":
            session_results,

        "matching_problems_detail":
            all_matching_problems,

        "interval_problems_detail":
            all_interval_problems
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with REPORT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False
        )

    print("\n")
    print("=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)

    print(
        f"\nDetailed report saved to:"
    )

    print(
        f"  {REPORT_FILE}"
    )


if __name__ == "__main__":
    main()