
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(r"D:\CHARAN RONGALI\AI Engineer")

DATASET_DIR = PROJECT_DIR / "data" / "dataset_a"

OUTPUT_DIR = PROJECT_DIR / "outputs" / "dataset_a"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LABELED_EVENTS_FILE = OUTPUT_DIR / "dataset_a_labeled_events.jsonl"
EXECUTION_FILE = OUTPUT_DIR / "dataset_a_execution_intervals.jsonl"
REPORT_FILE = OUTPUT_DIR / "dataset_a_alignment_report.json"


# ============================================================
# TIMESTAMP UTILITIES
# ============================================================

def parse_timestamp(value):
    """
    Convert different timestamp formats into UTC datetime.

    Supported:
      - ISO timestamp strings
      - timestamp in milliseconds
      - timestamp in seconds

    Returns:
        timezone-aware datetime in UTC, or None if invalid.
    """

    if value is None:
        return None

    # Numeric timestamp
    if isinstance(value, (int, float)):
        try:
            # milliseconds
            if value > 10_000_000_000:
                return datetime.fromtimestamp(
                    value / 1000,
                    tz=timezone.utc
                )

            # seconds
            return datetime.fromtimestamp(
                value,
                tz=timezone.utc
            )

        except (ValueError, OverflowError, OSError):
            return None

    # ISO string
    if isinstance(value, str):
        value = value.strip()

        if not value:
            return None

        try:
            # Handle Z suffix
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"

            dt = datetime.fromisoformat(value)

            # If timezone is missing, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)

        except ValueError:
            return None

    return None


def get_event_timestamp(event):
    """
    Extract timestamp from a raw event.
    """

    # Prefer timestamp_iso
    ts = parse_timestamp(
        event.get("timestamp_iso")
    )

    if ts is not None:
        return ts

    # Fall back to timestamp_ms
    return parse_timestamp(
        event.get("timestamp_ms")
    )


def get_gt_timestamp(record):
    """
    Extract timestamp from a GT record.
    """

    return parse_timestamp(
        record.get("ts_utc")
        or record.get("timestamp_iso")
        or record.get("timestamp_ms")
    )


# ============================================================
# JSONL LOADING
# ============================================================

def read_jsonl(path):
    """
    Read JSON Lines file safely.
    """

    records = []

    with path.open("r", encoding="utf-8") as f:

        for line_number, line in enumerate(f, start=1):

            line = line.strip()

            if not line:
                continue

            try:
                records.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as e:

                print(
                    f"WARNING: Could not parse {path} "
                    f"line {line_number}: {e}"
                )

    return records


# ============================================================
# SESSION DISCOVERY
# ============================================================

def find_sessions():
    """
    Find session directories.

    A session is identified by the presence of:
        gt.jsonl
    or
        gt_manifest.json
    """

    sessions = {}

    # Sessions containing gt.jsonl
    for gt_file in DATASET_DIR.rglob("gt.jsonl"):

        session_dir = gt_file.parent

        sessions[str(session_dir)] = session_dir

    # Sessions containing gt_manifest.json
    for manifest_file in DATASET_DIR.rglob("gt_manifest.json"):

        session_dir = manifest_file.parent

        sessions[str(session_dir)] = session_dir

    return sorted(
        sessions.values(),
        key=lambda p: str(p)
    )


# ============================================================
# EVENT FILE DISCOVERY
# ============================================================

def find_event_files(session_dir):
    """
    Find all events.jsonl files inside a session.

    Recursive because event files may be inside chunk folders.
    """

    return sorted(
        session_dir.rglob("events.jsonl"),
        key=lambda p: str(p)
    )


# ============================================================
# PROCESS EXECUTION EXTRACTION
# ============================================================

def extract_manifest_executions(manifest_path, session_id):
    """
    Extract process executions directly from the actual
    gt_manifest.json schema.

    Actual structure:

        manifest
          └── processes[]
                ├── code
                ├── family_name
                ├── domain
                └── executions[]
                      ├── code
                      ├── variant
                      ├── case_id
                      ├── start_ts
                      ├── end_ts
                      ├── apps
                      ├── continues_from_prev
                      ├── continues_to_next
                      ├── split_id
                      ├── phase
                      ├── exec_id
                      └── seq

    IMPORTANT:
        end_ts may legitimately be None.

    We therefore keep open-ended executions instead of
    discarding them.
    """

    if not manifest_path.exists():
        return []

    try:

        with manifest_path.open(
            "r",
            encoding="utf-8"
        ) as f:

            manifest = json.load(f)

    except Exception as e:

        print(
            f"WARNING: Could not read {manifest_path}: {e}"
        )

        return []

    if not isinstance(manifest, dict):
        print(
            f"WARNING: Unexpected manifest structure: "
            f"{manifest_path}"
        )
        return []

    process_groups = manifest.get("processes")

    if not isinstance(process_groups, list):
        print(
            f"WARNING: No valid 'processes' list in "
            f"{manifest_path}"
        )
        return []

    executions = []

    execution_counter = 0

    # --------------------------------------------------------
    # Actual manifest structure:
    #
    # processes[]
    #     -> executions[]
    # --------------------------------------------------------

    for process_group in process_groups:

        if not isinstance(process_group, dict):
            continue

        group_code = process_group.get("code")

        group_family_name = process_group.get(
            "family_name"
        )

        group_domain = process_group.get(
            "domain"
        )

        manifest_executions = process_group.get(
            "executions"
        )

        if not isinstance(manifest_executions, list):
            continue

        for item in manifest_executions:

            if not isinstance(item, dict):
                continue

            # ------------------------------------------------
            # Process code
            #
            # Execution-level code is preferred because it is
            # the identifier of the actual execution.
            # Process-group code is the fallback.
            # ------------------------------------------------

            process_code = (
                item.get("code")
                if item.get("code") is not None
                else group_code
            )

            # ------------------------------------------------
            # Variant
            #
            # IMPORTANT:
            # Do NOT use:
            #
            #     item.get("variant") or "unknown"
            #
            # because None is meaningful in the manifest.
            # ------------------------------------------------

            if "variant" in item:
                process_variant = item.get("variant")

            elif "process_variant" in item:
                process_variant = item.get(
                    "process_variant"
                )

            else:
                process_variant = None

            # ------------------------------------------------
            # Timestamps
            # ------------------------------------------------

            start_value = item.get(
                "start_ts"
            )

            end_value = item.get(
                "end_ts"
            )

            start_dt = parse_timestamp(
                start_value
            )

            end_dt = parse_timestamp(
                end_value
            )

            # A valid execution must have a start timestamp.
            if start_dt is None:

                print(
                    "WARNING: Execution without valid "
                    f"start_ts in {manifest_path}: "
                    f"{item}"
                )

                continue

            # ------------------------------------------------
            # Case ID
            # ------------------------------------------------

            case_id = item.get(
                "case_id"
            )

            # ------------------------------------------------
            # Preserve execution metadata from manifest
            # ------------------------------------------------

            execution_counter += 1

            execution_id = item.get(
                "exec_id"
            )

            if execution_id is None:

                execution_id = (
                    f"{session_id}_exec_"
                    f"{execution_counter:04d}"
                )

            execution = {
                "session_id": session_id,

                "execution_id": execution_id,

                "case_id": case_id,

                "process_code": process_code,

                "process_variant": process_variant,

                "process_family_name": (
                    group_family_name
                ),

                "domain": group_domain,

                "start_ts": start_dt.isoformat(),

                # IMPORTANT:
                # None is preserved here.
                "end_ts": (
                    end_dt.isoformat()
                    if end_dt is not None
                    else None
                ),

                # Useful manifest metadata
                "apps": item.get("apps"),

                "continues_from_prev": item.get(
                    "continues_from_prev"
                ),

                "continues_to_next": item.get(
                    "continues_to_next"
                ),

                "split_id": item.get(
                    "split_id"
                ),

                "phase": item.get(
                    "phase"
                ),

                "seq": item.get(
                    "seq"
                ),

                # Internal datetime values
                "_start_dt": start_dt,

                "_end_dt": end_dt,
            }

            executions.append(
                execution
            )

    # --------------------------------------------------------
    # Sort chronologically.
    # --------------------------------------------------------

        # --------------------------------------------------------
    # Sort chronologically.
    # --------------------------------------------------------

    executions.sort(
        key=lambda x: (
            x["_start_dt"],
            str(x["execution_id"])
        )
    )

    # --------------------------------------------------------
    # Infer missing end timestamps.
    #
    # IMPORTANT:
    # - Never overwrite a real manifest end_ts.
    # - Only infer an end when the next execution exists.
    # - The inferred boundary is the next execution's start.
    # - Keep the source distinction explicit.
    # --------------------------------------------------------

    for i, execution in enumerate(executions):

        if execution["_end_dt"] is not None:
            execution["end_ts_source"] = "manifest"
            execution["inferred_end_ts"] = None
            continue

        if i + 1 < len(executions):

            next_execution = executions[i + 1]
            inferred_end = next_execution["_start_dt"]

            # Defensive check: an inferred end must be
            # strictly after the execution start.
            if inferred_end > execution["_start_dt"]:

                execution["inferred_end_ts"] = (
                    inferred_end.isoformat()
                )

                execution["end_ts_source"] = (
                    "inferred_next_start"
                )

            else:
                execution["inferred_end_ts"] = None
                execution["end_ts_source"] = (
                    "missing_invalid_inference"
                )

        else:
            # No following execution exists, so there is
            # insufficient evidence to infer an end.
            execution["inferred_end_ts"] = None
            execution["end_ts_source"] = (
                "missing_no_next_execution"
            )

    return executions


# ============================================================
# FALLBACK: EXTRACT FROM GT.JSONL
# ============================================================

def get_gt_event_type(record):
    """
    Extract the GT event type.

    The actual GT uses the key:
        event

    Older/general formats are also supported as fallback.
    """

    return (
        record.get("event")
        or record.get("event_type")
        or record.get("type")
        or record.get("action")
    )


def extract_gt_processes(gt_path, session_id):
    """
    Fallback parser for gt.jsonl.

    This is NOT the preferred source for execution intervals.

    It is used only when a usable gt_manifest.json is not
    available.
    """

    if not gt_path.exists():
        return []

    records = read_jsonl(
        gt_path
    )

    starts = []

    for record in records:

        event_type = get_gt_event_type(
            record
        )

        if event_type != "process_started":
            continue

        timestamp = get_gt_timestamp(
            record
        )

        if timestamp is None:
            continue

        process_code = (
            record.get("process_code")
            or record.get("process")
            or record.get("current_process")
        )

        # Preserve None rather than inventing "unknown".
        if "process_variant" in record:
            process_variant = record.get(
                "process_variant"
            )

        elif "variant" in record:
            process_variant = record.get(
                "variant"
            )

        else:
            process_variant = None

        starts.append({
            "timestamp": timestamp,
            "process_code": process_code,
            "process_variant": process_variant,
        })

    starts.sort(
        key=lambda x: x["timestamp"]
    )

    executions = []

    for i, start in enumerate(starts):

        if i + 1 < len(starts):

            end = starts[i + 1]["timestamp"]

        else:

            end = None

        executions.append({
            "session_id": session_id,

            "execution_id": (
                f"{session_id}_fallback_"
                f"{i + 1:04d}"
            ),

            "case_id": None,

            "process_code": (
                start["process_code"]
            ),

            "process_variant": (
                start["process_variant"]
            ),

            "start_ts": (
                start["timestamp"].isoformat()
            ),

            "end_ts": (
                end.isoformat()
                if end
                else None
            ),

            "_start_dt": start["timestamp"],

            "_end_dt": end,
        })

    return executions


# ============================================================
# EVENT LABELING
# ============================================================

def label_events(events, executions):
    """
    Assign each event to a process execution.

    Events outside an execution are labeled NO_PROCESS.

    An execution with end_ts=None is treated as open-ended.
    """

    # Sort events chronologically
    events.sort(
        key=lambda x: (
            x["_timestamp"],
            str(x.get("_event_index", ""))
        )
    )

    # Executions should already be chronological.
    executions = sorted(
        executions,
        key=lambda x: (
            x["_start_dt"],
            str(x["execution_id"])
        )
    )

    labeled = []

    execution_index = 0

    for event in events:

        event_ts = event["_timestamp"]

        # ----------------------------------------------------
        # Move past executions that have definitely ended
        # before this event.
        # ----------------------------------------------------

        while (
            execution_index < len(executions)
            and executions[
                execution_index
            ]["_end_dt"] is not None
            and event_ts > executions[
                execution_index
            ]["_end_dt"]
        ):

            execution_index += 1

        matched_execution = None

        # ----------------------------------------------------
        # Check current execution.
        # ----------------------------------------------------

        if execution_index < len(executions):

            execution = executions[
                execution_index
            ]

            start_dt = execution[
                "_start_dt"
            ]

            end_dt = execution[
                "_end_dt"
            ]

            if event_ts >= start_dt:

                # Open-ended execution
                if end_dt is None:

                    matched_execution = execution

                # Normal closed execution
                elif event_ts <= end_dt:

                    matched_execution = execution

        # ----------------------------------------------------
        # Build labeled event.
        # ----------------------------------------------------

        labeled_event = {
            "session_id": (
                event["_session_id"]
            ),

            "timestamp": (
                event["_timestamp"].isoformat()
            ),

            "event_type": event.get(
                "event_type"
            ),

            "layer": event.get(
                "layer"
            ),

            "app": event.get(
                "_app"
            ),

            "window_title": event.get(
                "_window_title"
            ),

            "process_code": (
                matched_execution[
                    "process_code"
                ]
                if matched_execution
                else "NO_PROCESS"
            ),

            "process_variant": (
                matched_execution[
                    "process_variant"
                ]
                if matched_execution
                else None
            ),

            "execution_id": (
                matched_execution[
                    "execution_id"
                ]
                if matched_execution
                else None
            ),

            "case_id": (
                matched_execution[
                    "case_id"
                ]
                if matched_execution
                else None
            ),

            "in_ground_truth": (
                matched_execution is not None
            ),

            # Preserve useful raw information
            "payload": event.get(
                "payload"
            ),

            "context": event.get(
                "context"
            ),
        }

        labeled.append(
            labeled_event
        )

    return labeled


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "BUILDING DATASET A GROUND-TRUTH ALIGNMENT"
    )
    print("=" * 70)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    sessions = find_sessions()

    print(
        f"\nSessions found: {len(sessions)}"
    )

    all_labeled_events = []

    all_executions = []

    report = {
        "dataset": str(
            DATASET_DIR
        ),

        "sessions": 0,

        "sessions_processed": 0,

        "sessions_without_manifest": 0,

        "event_files": 0,

        "raw_events": 0,

        "labeled_events": 0,

        "events_inside_process": 0,

        "events_outside_process": 0,

        "executions": 0,

        "process_distribution": {},

        "variant_distribution": {},

        "alignment_coverage": 0.0,

        "errors": []
    }

    report["sessions"] = len(
        sessions
    )

    # --------------------------------------------------------
    # Process every session
    # --------------------------------------------------------

    for session_number, session_dir in enumerate(
        sessions,
        start=1
    ):

        session_id = session_dir.name

        print(
            f"\n[{session_number}/{len(sessions)}] "
            f"Processing session: {session_id}"
        )

        try:

            # ------------------------------------------------
            # Find event files
            # ------------------------------------------------

            event_files = find_event_files(
                session_dir
            )

            report[
                "event_files"
            ] += len(event_files)

            events = []

            event_index = 0

            for event_file in event_files:

                records = read_jsonl(
                    event_file
                )

                for event in records:

                    timestamp = get_event_timestamp(
                        event
                    )

                    if timestamp is None:
                        continue

                    # Defensive extraction of app
                    context = event.get(
                        "context"
                    ) or {}

                    if not isinstance(
                        context,
                        dict
                    ):
                        context = {}

                    active_app = context.get(
                        "active_app"
                    ) or {}

                    if isinstance(
                        active_app,
                        dict
                    ):

                        app_name = (
                            active_app.get(
                                "name"
                            )
                            or active_app.get(
                                "app_name"
                            )
                            or active_app.get(
                                "title"
                            )
                        )

                    else:

                        app_name = None

                    window_title = (
                        context.get(
                            "window_title"
                        )
                        or context.get(
                            "active_window_title"
                        )
                    )

                    # Internal metadata
                    event[
                        "_timestamp"
                    ] = timestamp

                    event[
                        "_session_id"
                    ] = session_id

                    event[
                        "_app"
                    ] = app_name

                    event[
                        "_window_title"
                    ] = window_title

                    event[
                        "_event_index"
                    ] = event_index

                    event_index += 1

                    events.append(
                        event
                    )

            print(
                f"  Event files : {len(event_files)}"
            )

            print(
                f"  Raw events  : {len(events)}"
            )

            report[
                "raw_events"
            ] += len(events)

            # ------------------------------------------------
            # Ground truth
            # ------------------------------------------------

            manifest_path = (
                session_dir
                / "gt_manifest.json"
            )

            gt_path = (
                session_dir
                / "gt.jsonl"
            )

            executions = (
                extract_manifest_executions(
                    manifest_path,
                    session_id
                )
            )

            if not executions:

                report[
                    "sessions_without_manifest"
                ] += 1

                print(
                    "  WARNING: No usable "
                    "gt_manifest executions."
                )

                # Do not silently trust fallback data
                # unless necessary.
                executions = (
                    extract_gt_processes(
                        gt_path,
                        session_id
                    )
                )

                if executions:

                    print(
                        f"  Fallback GT executions: "
                        f"{len(executions)}"
                    )

            else:

                print(
                    f"  GT executions: "
                    f"{len(executions)}"
                )

            # ------------------------------------------------
            # Label events
            # ------------------------------------------------

            labeled = label_events(
                events,
                executions
            )

            inside = sum(
                1
                for event in labeled
                if event[
                    "in_ground_truth"
                ]
            )

            outside = (
                len(labeled)
                - inside
            )

            print(
                f"  Inside process : {inside}"
            )

            print(
                f"  Outside process: {outside}"
            )

            all_labeled_events.extend(
                labeled
            )

            all_executions.extend(
                executions
            )

            report[
                "executions"
            ] += len(executions)

            report[
                "labeled_events"
            ] += len(labeled)

            report[
                "events_inside_process"
            ] += inside

            report[
                "events_outside_process"
            ] += outside

            report[
                "sessions_processed"
            ] += 1

        except Exception as e:

            error_message = (
                f"{session_id}: "
                f"{type(e).__name__}: "
                f"{e}"
            )

            print(
                f"  ERROR: {error_message}"
            )

            report[
                "errors"
            ].append(
                error_message
            )

    # ========================================================
    # WRITE LABELED EVENTS
    # ========================================================

    print(
        "\nWriting labeled events..."
    )

    with LABELED_EVENTS_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        for event in all_labeled_events:

            f.write(
                json.dumps(
                    event,
                    ensure_ascii=False
                )
                + "\n"
            )

    # ========================================================
    # WRITE EXECUTION INTERVALS
    # ========================================================

    print(
        "Writing execution intervals..."
    )

    with EXECUTION_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        for execution in all_executions:

            clean_execution = {
                key: value
                for key, value in execution.items()
                if not key.startswith("_")
            }

            f.write(
                json.dumps(
                    clean_execution,
                    ensure_ascii=False
                )
                + "\n"
            )

    # ========================================================
    # DISTRIBUTIONS
    # ========================================================

    process_counter = Counter()

    variant_counter = Counter()

    for execution in all_executions:

        process_counter[
            execution.get(
                "process_code"
            )
        ] += 1

        variant_counter[
            execution.get(
                "process_variant"
            )
        ] += 1

    report[
        "process_distribution"
    ] = dict(
        process_counter.most_common()
    )

    report[
        "variant_distribution"
    ] = dict(
        variant_counter.most_common()
    )

    # ========================================================
    # COVERAGE
    # ========================================================

    if report[
        "labeled_events"
    ] > 0:

        report[
            "alignment_coverage"
        ] = round(
            report[
                "events_inside_process"
            ]
            /
            report[
                "labeled_events"
            ],
            4
        )

    # ========================================================
    # WRITE REPORT
    # ========================================================

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

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print(
        "\n" + "=" * 70
    )

    print(
        "GROUND-TRUTH ALIGNMENT COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"Sessions processed : "
        f"{report['sessions_processed']}"
    )

    print(
        f"Raw events         : "
        f"{report['raw_events']:,}"
    )

    print(
        f"Executions         : "
        f"{report['executions']:,}"
    )

    print(
        f"Events labeled     : "
        f"{report['labeled_events']:,}"
    )

    print(
        f"Inside processes   : "
        f"{report['events_inside_process']:,}"
    )

    print(
        f"Outside processes  : "
        f"{report['events_outside_process']:,}"
    )

    print(
        f"Alignment coverage : "
        f"{report['alignment_coverage']:.2%}"
    )

    print(
        "\nProcess distribution:"
    )

    for process, count in (
        process_counter.most_common()
    ):

        print(
            f"  {process}: {count}"
        )

    print(
        "\nVariant distribution:"
    )

    for variant, count in (
        variant_counter.most_common()
    ):

        print(
            f"  {variant}: {count}"
        )

    print(
        "\nOutput files:"
    )

    print(
        f"  {LABELED_EVENTS_FILE}"
    )

    print(
        f"  {EXECUTION_FILE}"
    )

    print(
        f"  {REPORT_FILE}"
    )

    if report["errors"]:

        print(
            f"\nWARNING: "
            f"{len(report['errors'])} "
            f"sessions had errors."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()