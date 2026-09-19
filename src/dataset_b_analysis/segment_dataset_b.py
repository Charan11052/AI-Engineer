import json
import os
import re
from collections import Counter
from datetime import datetime


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

DATASET_B = os.path.join(
    BASE_DIR,
    "dataset_b"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "outputs"
)

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "segments.jsonl"
)


# ============================================================
# TIMESTAMP
# ============================================================

def get_timestamp(event):
    """
    Get event timestamp in seconds.

    Dataset B primarily uses timestamp_ms.
    timestamp_iso is used as a fallback.
    """

    timestamp_ms = event.get("timestamp_ms")

    if timestamp_ms is not None:
        try:
            return float(timestamp_ms) / 1000.0
        except (TypeError, ValueError):
            pass

    timestamp_iso = event.get("timestamp_iso")

    if timestamp_iso:
        try:
            return datetime.fromisoformat(
                timestamp_iso.replace(
                    "Z",
                    "+00:00"
                )
            ).timestamp()
        except Exception:
            pass

    return None


# ============================================================
# APPLICATION
# ============================================================

def get_app(event):
    """
    Extract application name from:

        context.active_app.app_name

    Dataset B stores active_app as a dictionary.
    """

    context = event.get("context") or {}

    active_app = context.get(
        "active_app"
    )

    if isinstance(active_app, dict):

        app_name = (
            active_app.get("app_name")
            or active_app.get("process_name")
        )

        if app_name:
            return str(app_name).lower().strip()

    elif isinstance(active_app, str):

        return active_app.lower().strip()

    return "unknown"


# ============================================================
# WINDOW TITLE
# ============================================================

def get_window_title(event):
    """
    Extract active window title.
    """

    context = event.get("context") or {}

    active_app = context.get(
        "active_app"
    )

    if isinstance(active_app, dict):

        title = active_app.get(
            "window_title"
        )

        if title:
            return str(title).strip()

    return ""


# ============================================================
# EXTRACTED TEXT
# ============================================================

def get_text(event):
    """
    Dataset B stores extracted_text as:

        context.extracted_text.text
    """

    context = event.get("context") or {}

    extracted = context.get(
        "extracted_text"
    )

    if isinstance(extracted, dict):

        text = extracted.get("text")

        if text:
            return str(text).strip()

    elif isinstance(extracted, str):

        return extracted.strip()

    return ""


# ============================================================
# NORMALIZE WINDOW TITLE
# ============================================================

def normalize_title(title):
    """
    Remove dynamic browser/document suffixes while
    retaining meaningful business-system/document names.
    """

    if not title:
        return ""

    title = title.lower().strip()

    # Remove invisible zero-width characters
    title = title.replace(
        "\u200b",
        ""
    )

    # Remove Edge profile suffix
    title = re.sub(
        r"\s*-\s*profile\s+\d+.*$",
        "",
        title
    )

    # Remove "and N more pages"
    title = re.sub(
        r"\s+and\s+\d+\s+more\s+pages?.*$",
        "",
        title
    )

    # Word compatibility mode
    title = title.replace(
        " - compatibility mode",
        ""
    )

    # Normalize repeated whitespace
    title = re.sub(
        r"\s+",
        " ",
        title
    )

    return title.strip()


# ============================================================
# BUSINESS AREA
# ============================================================

def classify_work_area(
    app,
    title
):
    """
    Identify the broad business/application area.

    Dataset B shows three major browser-based business
    systems plus Word/Excel/Notepad/etc.
    """

    combined = (
        f"{app} {title}"
    ).lower()

    # --------------------------------------------------------
    # Business systems
    # --------------------------------------------------------

    if "hr人事給与システム" in combined:
        return "HR"

    if "財務会計システム" in combined:
        return "FINANCE"

    if "受発注在庫管理システム" in combined:
        return "LOGISTICS"

    # --------------------------------------------------------
    # Desktop applications
    # --------------------------------------------------------

    if (
        app == "microsoft excel"
        or "excel" in combined
    ):
        return "EXCEL"

    if (
        app == "microsoft word"
        or "word" in combined
    ):
        return "WORD"

    if (
        app == "notepad"
        or "notepad" in combined
    ):
        return "NOTEPAD"

    if (
        app == "windowsterminal"
        or "windows powershell" in combined
        or "powershell" in combined
        or "terminal" in combined
    ):
        return "TERMINAL"

    if (
        app == "ms-teams"
        or "teams" in combined
    ):
        return "TEAMS"

    if (
        app == "windows explorer"
        or "explorer" in combined
    ):
        return "EXPLORER"

    return "OTHER"


# ============================================================
# MEANINGFUL EVENTS
# ============================================================

def is_meaningful_event(event):
    """
    Events that provide evidence of active work.
    """

    event_type = event.get(
        "event_type",
        ""
    )

    return event_type in {
        "app_switch",
        "browser_click",
        "browser_form_input",
        "browser_navigation",
        "mouse_click",
        "keystroke",
        "shortcut",
        "clipboard_change",
        "window_title_change",
        "text_input_complete",
        "upload_started",
        "upload_completed",
    }


# ============================================================
# LOAD EVENTS
# ============================================================

def load_events(events_file):
    """
    Load and chronologically sort one events.jsonl file.
    """

    events = []

    with open(
        events_file,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            try:
                event = json.loads(
                    line
                )
            except json.JSONDecodeError:
                continue

            timestamp = get_timestamp(
                event
            )

            if timestamp is None:
                continue

            event["_timestamp"] = timestamp

            events.append(
                event
            )

    # --------------------------------------------------------
    # Dataset B can contain small timestamp/order anomalies.
    # Chronological sorting is therefore used.
    # --------------------------------------------------------

    events.sort(
        key=lambda x: x["_timestamp"]
    )

    return events


# ============================================================
# DISCOVER ALL CHUNKS
# ============================================================

def discover_chunks():
    """
    Dataset B structure:

        dataset_b/
            ses_xxx/
                chunk_xxx/
                    events.jsonl

    Return every chunk containing events.jsonl.
    """

    chunks = []

    if not os.path.isdir(
        DATASET_B
    ):
        raise FileNotFoundError(
            f"Dataset B not found: {DATASET_B}"
        )

    for session_name in os.listdir(
        DATASET_B
    ):

        session_dir = os.path.join(
            DATASET_B,
            session_name
        )

        if not os.path.isdir(
            session_dir
        ):
            continue

        for chunk_name in os.listdir(
            session_dir
        ):

            chunk_dir = os.path.join(
                session_dir,
                chunk_name
            )

            if not os.path.isdir(
                chunk_dir
            ):
                continue

            events_file = os.path.join(
                chunk_dir,
                "events.jsonl"
            )

            if not os.path.isfile(
                events_file
            ):
                continue

            chunks.append({
                "session_folder": session_name,
                "chunk_id": chunk_name,
                "chunk_dir": chunk_dir,
                "events_file": events_file
            })

    # Stable ordering
    chunks.sort(
        key=lambda x: (
            x["session_folder"],
            x["chunk_id"]
        )
    )

    return chunks


# ============================================================
# BOUNDARY SCORING
# ============================================================

def boundary_score(
    previous_event,
    current_event,
    gap_seconds
):
    """
    Calculate evidence that the current event starts
    a new business execution.

    The score combines:
        - inactivity
        - business-system changes
        - business-area changes
        - document changes
        - application changes
        - workflow completion signals
    """

    score = 0

    reasons = []

    previous_app = get_app(
        previous_event
    )

    current_app = get_app(
        current_event
    )

    previous_title = normalize_title(
        get_window_title(
            previous_event
        )
    )

    current_title = normalize_title(
        get_window_title(
            current_event
        )
    )

    previous_area = classify_work_area(
        previous_app,
        previous_title
    )

    current_area = classify_work_area(
        current_app,
        current_title
    )

    previous_type = previous_event.get(
        "event_type",
        ""
    )

    current_type = current_event.get(
        "event_type",
        ""
    )

    # ========================================================
    # 1. INACTIVITY GAP
    # ========================================================

    if gap_seconds >= 60:

        score += 5

        reasons.append(
            f"long_gap_{gap_seconds:.1f}s"
        )

    elif gap_seconds >= 30:

        score += 3

        reasons.append(
            f"medium_gap_{gap_seconds:.1f}s"
        )

    elif gap_seconds >= 15:

        score += 1

        reasons.append(
            f"short_gap_{gap_seconds:.1f}s"
        )

    # ========================================================
    # 2. BUSINESS AREA CHANGE
    # ========================================================

    if (
        previous_area != current_area
        and previous_area != "OTHER"
        and current_area != "OTHER"
    ):

        score += 2

        reasons.append(
            f"area_change_"
            f"{previous_area}_to_{current_area}"
        )

    # ========================================================
    # 3. BUSINESS SYSTEM CHANGE
    # ========================================================

    business_areas = {
        "HR",
        "FINANCE",
        "LOGISTICS"
    }

    if (
        previous_area in business_areas
        and current_area in business_areas
        and previous_area != current_area
    ):

        score += 3

        reasons.append(
            f"business_system_change_"
            f"{previous_area}_to_{current_area}"
        )

    # ========================================================
    # 4. DOCUMENT CHANGE
    # ========================================================

    if (
        previous_title
        and current_title
        and previous_title != current_title
    ):

        document_areas = {
            "WORD",
            "EXCEL"
        }

        if (
            previous_area in document_areas
            or current_area in document_areas
        ):

            score += 2

            reasons.append(
                "document_change"
            )

    # ========================================================
    # 5. APPLICATION CHANGE AFTER ACTIVE WORK
    # ========================================================

    if previous_app != current_app:

        active_work_events = {
            "browser_form_input",
            "browser_click",
            "clipboard_change",
            "shortcut",
            "text_input_complete",
            "mouse_click"
        }

        if previous_type in active_work_events:

            score += 1

            reasons.append(
                f"app_change_after_{previous_type}"
            )

    # ========================================================
    # 6. UPLOAD COMPLETION
    # ========================================================

    if previous_type == "upload_completed":

        score += 2

        reasons.append(
            "upload_completed"
        )

    # ========================================================
    # 7. EXPLICIT SESSION START
    # ========================================================

    if current_type == "session_start":

        score += 10

        reasons.append(
            "session_start"
        )

    return score, reasons


# ============================================================
# SEGMENT ONE CHUNK
# ============================================================

def segment_chunk(
    events,
    session_id,
    chunk_id,
    session_folder
):

    if not events:
        return []

    raw_segments = []

    current_events = []

    current_boundary_score = 0

    current_boundary_reasons = []

    # --------------------------------------------------------
    # Process events
    # --------------------------------------------------------

    for event in events:

        if not current_events:

            current_events.append(
                event
            )

            continue

        previous_event = (
            current_events[-1]
        )

        gap_seconds = (
            event["_timestamp"]
            - previous_event["_timestamp"]
        )

        score, reasons = boundary_score(
            previous_event,
            event,
            gap_seconds
        )

        # ----------------------------------------------------
        # Conservative boundary rule
        # ----------------------------------------------------

        should_split = (
            score >= 5
        )

        # ----------------------------------------------------
        # Avoid creating fragments containing almost no work.
        # ----------------------------------------------------

        meaningful_events = sum(
            1
            for e in current_events
            if is_meaningful_event(e)
        )

        if (
            should_split
            and meaningful_events >= 5
        ):

            raw_segments.append({
                "events": current_events,
                "boundary_score": score,
                "boundary_reasons": reasons
            })

            current_events = [
                event
            ]

            current_boundary_score = score

            current_boundary_reasons = reasons

        else:

            current_events.append(
                event
            )

    # --------------------------------------------------------
    # Final segment
    # --------------------------------------------------------

    if current_events:

        raw_segments.append({
            "events": current_events,
            "boundary_score": current_boundary_score,
            "boundary_reasons": current_boundary_reasons
        })

    # ========================================================
    # MERGE VERY SMALL SEGMENTS
    # ========================================================

    merged_segments = []

    for segment in raw_segments:

        event_count = len(
            segment["events"]
        )

        if (
            merged_segments
            and event_count < 10
        ):

            merged_segments[-1][
                "events"
            ].extend(
                segment["events"]
            )

        else:

            merged_segments.append(
                segment
            )

    # ========================================================
    # BUILD OUTPUT RECORDS
    # ========================================================

    results = []

    for index, segment in enumerate(
        merged_segments,
        start=1
    ):

        segment_events = segment[
            "events"
        ]

        start_timestamp = (
            segment_events[0]["_timestamp"]
        )

        end_timestamp = (
            segment_events[-1]["_timestamp"]
        )

        # ----------------------------------------------------
        # Event type counts
        # ----------------------------------------------------

        event_types = Counter(
            event.get(
                "event_type",
                "unknown"
            )
            for event in segment_events
        )

        # ----------------------------------------------------
        # Applications
        # ----------------------------------------------------

        applications = Counter(
            get_app(event)
            for event in segment_events
        )

        # ----------------------------------------------------
        # Work areas
        # ----------------------------------------------------

        work_areas = Counter()

        for event in segment_events:

            app = get_app(
                event
            )

            title = normalize_title(
                get_window_title(
                    event
                )
            )

            area = classify_work_area(
                app,
                title
            )

            work_areas[area] += 1

        # ----------------------------------------------------
        # Window titles
        # ----------------------------------------------------

        window_titles = Counter()

        for event in segment_events:

            title = normalize_title(
                get_window_title(
                    event
                )
            )

            if title:
                window_titles[title] += 1

        # ----------------------------------------------------
        # Extracted text evidence
        # ----------------------------------------------------

        text_samples = []

        for event in segment_events:

            text = get_text(
                event
            )

            if text:

                # Keep only useful-sized text samples
                cleaned = re.sub(
                    r"\s+",
                    " ",
                    text
                ).strip()

                if cleaned:

                    text_samples.append(
                        cleaned[:300]
                    )

        # Remove duplicate text samples
        unique_text_samples = []

        seen_text = set()

        for text in text_samples:

            key = text.lower()

            if key not in seen_text:

                seen_text.add(key)

                unique_text_samples.append(
                    text
                )

            if len(
                unique_text_samples
            ) >= 10:
                break

        # ----------------------------------------------------
        # Browser activity
        # ----------------------------------------------------

        browser_events = sum(
            1
            for event in segment_events
            if event.get(
                "event_type"
            ) in {
                "browser_click",
                "browser_form_input",
                "browser_navigation"
            }
        )

        clipboard_events = sum(
            1
            for event in segment_events
            if event.get(
                "event_type"
            ) == "clipboard_change"
        )

        # ----------------------------------------------------
        # Dominant app / area
        # ----------------------------------------------------

        dominant_app = (
            applications.most_common(1)[0][0]
            if applications
            else "unknown"
        )

        dominant_area = (
            work_areas.most_common(1)[0][0]
            if work_areas
            else "OTHER"
        )

        # ----------------------------------------------------
        # Segment record
        # ----------------------------------------------------

        result = {
            "segment_id": (
                f"{session_id}_{chunk_id}_SEG_{index:03d}"
            ),
            
            "session_folder": session_folder,

            "session_id": session_id,

            "chunk_id": chunk_id,

            "start_timestamp": start_timestamp,

            "end_timestamp": end_timestamp,

            "duration_seconds": (
                end_timestamp
                - start_timestamp
            ),

            "event_count": len(
                segment_events
            ),

            "dominant_app": dominant_app,

            "dominant_work_area": dominant_area,

            "applications": [
                {
                    "name": app,
                    "events": count
                }
                for app, count
                in applications.most_common()
            ],

            "work_areas": [
                {
                    "area": area,
                    "events": count
                }
                for area, count
                in work_areas.most_common()
            ],

            "window_titles": [
                {
                    "title": title,
                    "events": count
                }
                for title, count
                in window_titles.most_common(10)
            ],

            "event_types": [
                {
                    "event_type": event_type,
                    "count": count
                }
                for event_type, count
                in event_types.most_common(10)
            ],

            "browser_event_count": browser_events,

            "clipboard_event_count": clipboard_events,

            "text_evidence": unique_text_samples,

            "boundary_evidence": {
                "score": segment[
                    "boundary_score"
                ],
                "reasons": segment[
                    "boundary_reasons"
                ]
            }
        }

        results.append(
            result
        )

    return results


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("DATASET B BUSINESS PROCESS SEGMENTATION")
    print("=" * 70)

    print()
    print(
        f"Dataset B: {DATASET_B}"
    )

    # --------------------------------------------------------
    # Discover chunks
    # --------------------------------------------------------

    chunks = discover_chunks()

    print()
    print(
        f"Session folders found : "
        f"{len(set(c['session_folder'] for c in chunks))}"
    )

    print(
        f"Chunks found          : "
        f"{len(chunks)}"
    )

    if not chunks:

        print()
        print(
            "ERROR: No events.jsonl files found."
        )

        print(
            "Expected structure:"
        )

        print(
            "dataset_b/"
            "ses_xxx/"
            "chunk_xxx/"
            "events.jsonl"
        )

        return

    all_segments = []

    total_events = 0

    # --------------------------------------------------------
    # Process every chunk
    # --------------------------------------------------------

    for chunk in chunks:

        chunk_id = chunk[
            "chunk_id"
        ]

        session_folder = chunk[
            "session_folder"
        ]

        events = load_events(
            chunk["events_file"]
        )

        if not events:

            print(
                f"{chunk_id:55s} "
                f"events=0 "
                f"segments=0"
            )

            continue

        total_events += len(
            events
        )

        session_id = (
            events[0].get(
                "session_id"
            )
            or session_folder
        )

        segments = segment_chunk(
            events,
            session_id,
            chunk_id,
            session_folder
        )

        all_segments.extend(
            segments
        )

        print(
            f"{chunk_id:55s} "
            f"events={len(events):4d} "
            f"segments={len(segments):3d}"
        )

    # ========================================================
    # WRITE JSONL
    # ========================================================

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for segment in all_segments:

            f.write(
                json.dumps(
                    segment,
                    ensure_ascii=False
                )
                + "\n"
            )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("SEGMENTATION SUMMARY")
    print("=" * 70)

    print(
        f"Session folders    : "
        f"{len(set(c['session_folder'] for c in chunks))}"
    )

    print(
        f"Chunks             : "
        f"{len(chunks)}"
    )

    print(
        f"Total events       : "
        f"{total_events}"
    )

    print(
        f"Segments           : "
        f"{len(all_segments)}"
    )

    # --------------------------------------------------------
    # Duration statistics
    # --------------------------------------------------------

    if all_segments:

        durations = [
            s["duration_seconds"]
            for s in all_segments
        ]

        event_counts = [
            s["event_count"]
            for s in all_segments
        ]

        print()

        print(
            f"Average duration   : "
            f"{sum(durations) / len(durations):.1f}s"
        )

        print(
            f"Minimum duration   : "
            f"{min(durations):.1f}s"
        )

        print(
            f"Maximum duration   : "
            f"{max(durations):.1f}s"
        )

        print()

        print(
            f"Average events     : "
            f"{sum(event_counts) / len(event_counts):.1f}"
        )

        print(
            f"Minimum events     : "
            f"{min(event_counts)}"
        )

        print(
            f"Maximum events     : "
            f"{max(event_counts)}"
        )

        # ====================================================
        # WORK AREAS
        # ====================================================

        print()
        print(
            "DOMINANT WORK AREAS"
        )

        areas = Counter(
            segment[
                "dominant_work_area"
            ]
            for segment in all_segments
        )

        for area, count in areas.most_common():

            print(
                f"  {area:15s} {count}"
            )

        # ====================================================
        # DOMINANT APPLICATIONS
        # ====================================================

        print()
        print(
            "DOMINANT APPLICATIONS"
        )

        apps = Counter(
            segment[
                "dominant_app"
            ]
            for segment in all_segments
        )

        for app, count in apps.most_common():

            print(
                f"  {app:30s} {count}"
            )

        # ====================================================
        # SEGMENTS PER CHUNK
        # ====================================================

        print()
        print(
            "SEGMENTS PER CHUNK"
        )

        chunk_counts = Counter(
            segment["chunk_id"]
            for segment in all_segments
        )

        for chunk in chunks:

            chunk_id = chunk[
                "chunk_id"
            ]

            print(
                f"  {chunk_id:55s} "
                f"{chunk_counts.get(chunk_id, 0)}"
            )

    # ========================================================
    # OUTPUT
    # ========================================================

    print()
    print("=" * 70)
    print("SEGMENTATION COMPLETE")
    print("=" * 70)

    print()
    print(
        f"Output file:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()