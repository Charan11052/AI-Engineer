import json
from pathlib import Path
from collections import Counter


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_A = PROJECT_DIR / "data" / "dataset_a"


# ============================================================
# JSONL READER
# ============================================================

def read_jsonl(path):
    """
    Read a JSONL file safely.
    Returns a list of JSON objects.
    """

    records = []

    with open(path, "r", encoding="utf-8") as f:

        for line_number, line in enumerate(f, start=1):

            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))

            except json.JSONDecodeError as e:

                print(
                    f"WARNING: Invalid JSON in:\n"
                    f"  File: {path}\n"
                    f"  Line: {line_number}\n"
                    f"  Error: {e}"
                )

    return records


# ============================================================
# SAFE APPLICATION EXTRACTION
# ============================================================

def get_app_name(event):

    context = event.get("context") or {}

    if not isinstance(context, dict):
        return None

    active_app = context.get("active_app") or {}

    if not isinstance(active_app, dict):
        return None

    return active_app.get("app_name")


# ============================================================
# SAFE TIMESTAMP EXTRACTION
# ============================================================

def get_timestamp(event):

    return (
        event.get("timestamp_iso")
        or event.get("timestamp_ms")
        or ""
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("DATASET A - COMPLETE RECURSIVE INSPECTION")
    print("=" * 80)

    if not DATASET_A.exists():

        print("\nERROR:")
        print(f"Dataset directory does not exist:")
        print(DATASET_A.resolve())
        return

    # --------------------------------------------------------
    # FIND SESSIONS
    # --------------------------------------------------------

    sessions = sorted(
        p for p in DATASET_A.iterdir()
        if p.is_dir() and p.name.startswith("ses_")
    )

    print(f"\nDataset path : {DATASET_A.resolve()}")
    print(f"Sessions found: {len(sessions)}")

    if len(sessions) != 63:

        print(
            f"WARNING: Expected 63 sessions, "
            f"but found {len(sessions)}"
        )

    # --------------------------------------------------------
    # GLOBAL STATISTICS
    # --------------------------------------------------------

    total_events = 0
    total_chunks = 0
    total_executions = 0

    event_types = Counter()
    applications = Counter()
    processes = Counter()

    layer_counts = Counter()

    sessions_with_gt = 0
    sessions_without_gt = 0

    sessions_with_events = 0
    sessions_without_events = 0

    total_event_files = 0

    # Useful diagnostic counters
    null_context = 0
    null_active_app = 0
    events_with_extracted_text = 0

    # --------------------------------------------------------
    # SESSION LOOP
    # --------------------------------------------------------

    for session_index, session_dir in enumerate(
        sessions,
        start=1
    ):

        # ----------------------------------------------------
        # RECURSIVELY FIND EVENTS.JSONL
        # ----------------------------------------------------

        event_files = sorted(
            session_dir.rglob("events.jsonl")
        )

        # ----------------------------------------------------
        # RECURSIVELY FIND GROUND TRUTH
        # ----------------------------------------------------

        gt_files = sorted(
            session_dir.rglob("gt.jsonl")
        )

        # ----------------------------------------------------
        # SESSION STATISTICS
        # ----------------------------------------------------

        session_event_count = 0
        session_process_count = 0

        # ----------------------------------------------------
        # PROCESS ALL EVENT FILES
        # ----------------------------------------------------

        for events_file in event_files:

            total_event_files += 1
            total_chunks += 1

            events = read_jsonl(events_file)

            session_event_count += len(events)

            # -----------------------------------------------
            # EVENT LOOP
            # -----------------------------------------------

            for event in events:

                total_events += 1

                # Event type
                event_type = event.get(
                    "event_type",
                    "UNKNOWN"
                )

                event_types[event_type] += 1

                # Layer
                layer = event.get(
                    "layer",
                    "UNKNOWN"
                )

                layer_counts[layer] += 1

                # Application
                app_name = get_app_name(event)

                if app_name:

                    applications[app_name] += 1

                else:

                    null_active_app += 1

                # Context diagnostics
                if event.get("context") is None:

                    null_context += 1

                # Extracted screen text
                context = event.get("context") or {}

                if (
                    isinstance(context, dict)
                    and context.get("extracted_text")
                ):

                    events_with_extracted_text += 1

        # ----------------------------------------------------
        # GROUND TRUTH
        # ----------------------------------------------------

        if gt_files:

            sessions_with_gt += 1

            # Usually there should be one gt.jsonl
            # but we handle all recursively found files.

            for gt_file in gt_files:

                gt_records = read_jsonl(gt_file)

                for record in gt_records:

                    event_type = record.get("event")

                    if event_type == "process_started":

                        total_executions += 1
                        session_process_count += 1

                        process_code = record.get(
                            "process_code"
                        )

                        if process_code:

                            processes[process_code] += 1

        else:

            sessions_without_gt += 1

        # ----------------------------------------------------
        # SESSION STATUS
        # ----------------------------------------------------

        if event_files:

            sessions_with_events += 1

        else:

            sessions_without_events += 1

        # ----------------------------------------------------
        # PRINT SESSION
        # ----------------------------------------------------

        print(
            f"[{session_index:02d}/"
            f"{len(sessions):02d}] "
            f"{session_dir.name}"
        )

        print(
            f"       events.jsonl files : "
            f"{len(event_files)}"
        )

        print(
            f"       events             : "
            f"{session_event_count}"
        )

        print(
            f"       GT executions      : "
            f"{session_process_count}"
        )

        # Print actual event locations
        for events_file in event_files:

            relative_path = events_file.relative_to(
                session_dir
            )

            print(
                f"       └─ {relative_path}"
            )

    # ========================================================
    # GLOBAL SUMMARY
    # ========================================================

    print("\n")
    print("=" * 80)
    print("GLOBAL SUMMARY")
    print("=" * 80)

    print(
        f"Sessions found              : "
        f"{len(sessions)}"
    )

    print(
        f"Sessions with events        : "
        f"{sessions_with_events}"
    )

    print(
        f"Sessions WITHOUT events     : "
        f"{sessions_without_events}"
    )

    print(
        f"Sessions with GT            : "
        f"{sessions_with_gt}"
    )

    print(
        f"Sessions WITHOUT GT         : "
        f"{sessions_without_gt}"
    )

    print(
        f"events.jsonl files found    : "
        f"{total_event_files}"
    )

    print(
        f"Total chunks/files           : "
        f"{total_chunks}"
    )

    print(
        f"Total events                 : "
        f"{total_events:,}"
    )

    print(
        f"Process executions (GT)      : "
        f"{total_executions:,}"
    )

    print(
        f"Unique process types         : "
        f"{len(processes)}"
    )

    # ========================================================
    # EVENT TYPES
    # ========================================================

    print("\n")
    print("=" * 80)
    print("EVENT TYPE DISTRIBUTION")
    print("=" * 80)

    for name, count in event_types.most_common():

        percentage = (
            count / total_events * 100
            if total_events
            else 0
        )

        print(
            f"{name:35} "
            f"{count:10,} "
            f"{percentage:7.2f}%"
        )

    # ========================================================
    # LAYERS
    # ========================================================

    print("\n")
    print("=" * 80)
    print("EVENT LAYERS")
    print("=" * 80)

    for name, count in layer_counts.most_common():

        percentage = (
            count / total_events * 100
            if total_events
            else 0
        )

        print(
            f"{name:20} "
            f"{count:10,} "
            f"{percentage:7.2f}%"
        )

    # ========================================================
    # APPLICATIONS
    # ========================================================

    print("\n")
    print("=" * 80)
    print("TOP APPLICATIONS")
    print("=" * 80)

    for name, count in applications.most_common(30):

        percentage = (
            count / total_events * 100
            if total_events
            else 0
        )

        print(
            f"{str(name):35} "
            f"{count:10,} "
            f"{percentage:7.2f}%"
        )

    # ========================================================
    # GROUND TRUTH PROCESSES
    # ========================================================

    print("\n")
    print("=" * 80)
    print("GROUND-TRUTH PROCESS DISTRIBUTION")
    print("=" * 80)

    for name, count in processes.most_common():

        percentage = (
            count / total_executions * 100
            if total_executions
            else 0
        )

        print(
            f"Process {str(name):20} "
            f"{count:10,} "
            f"{percentage:7.2f}%"
        )

    # ========================================================
    # DATA QUALITY
    # ========================================================

    print("\n")
    print("=" * 80)
    print("DATA QUALITY / DIAGNOSTICS")
    print("=" * 80)

    print(
        f"Events with null context     : "
        f"{null_context:,}"
    )

    print(
        f"Events with null active_app  : "
        f"{null_active_app:,}"
    )

    print(
        f"Events with extracted text   : "
        f"{events_with_extracted_text:,}"
    )

    print("\nInspection completed.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()