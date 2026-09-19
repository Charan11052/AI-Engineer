import json
import re
from pathlib import Path
from collections import Counter
from datetime import datetime


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_B = BASE_DIR / "dataset_b"
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_FILE = OUTPUT_DIR / "dataset_b_segments_v2.jsonl"


# ============================================================
# CONFIGURATION
# ============================================================

# A candidate new task must persist for at least this many
# meaningful events before we treat it as a real boundary.
MIN_STABLE_EVENTS = 8

# Very tiny segments are usually fragments caused by app/system
# transitions rather than complete business tasks.
MIN_SEGMENT_EVENTS = 15
MIN_SEGMENT_SECONDS = 8

# If there is a long inactivity gap, it is stronger evidence
# for a boundary.
LONG_GAP_SECONDS = 45

# Extremely long segments are inspected for internal task changes.
LONG_SEGMENT_SECONDS = 150


# ============================================================
# BASIC HELPERS
# ============================================================

def parse_timestamp(event):
    """Return timestamp in milliseconds."""
    value = event.get("timestamp_ms")

    if value is not None:
        try:
            return int(value)
        except (ValueError, TypeError):
            pass

    iso = event.get("timestamp_iso")

    if iso:
        try:
            text = iso.replace("Z", "+00:00")
            return int(datetime.fromisoformat(text).timestamp() * 1000)
        except Exception:
            pass

    return None


def get_app(event):
    """Extract normalized application name."""
    context = event.get("context") or {}
    active_app = context.get("active_app") or {}

    if isinstance(active_app, dict):
        value = (
            active_app.get("app_name")
            or active_app.get("process_name")
            or ""
        )
    else:
        value = str(active_app)

    return str(value).strip().lower()


def get_window_title(event):
    """Extract active window title."""
    context = event.get("context") or {}
    value = context.get("window_title")

    if value:
        return str(value).strip()

    active_app = context.get("active_app") or {}

    if isinstance(active_app, dict):
        value = active_app.get("window_title")

    return str(value).strip() if value else ""


def get_extracted_text(event):
    """Extract text captured by the event."""
    context = event.get("context") or {}
    extracted = context.get("extracted_text")

    if isinstance(extracted, dict):
        return str(extracted.get("text") or "").strip()

    if extracted:
        return str(extracted).strip()

    return ""


def get_event_type(event):
    return str(event.get("event_type") or "").lower()


def normalize_text(text):
    """
    Normalize text for matching while preserving Japanese/Unicode.
    """
    text = str(text or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def meaningful_event(event):
    """
    Events useful for detecting work activity.
    Screenshots are included because they may contain extracted text,
    but we don't OCR anything here.
    """
    event_type = get_event_type(event)

    ignored = {
        "session_start",
        "session_end",
        "extension_connected",
        "extension_disconnected",
    }

    return event_type not in ignored


# ============================================================
# BUSINESS AREA CLASSIFICATION
# ============================================================

def classify_area(app, title, text):
    """
    Determine the broad business/work area.

    Window titles and text are more important than application alone.
    """

    combined = normalize_text(
        f"{title} {text}"
    )

    # HR / personnel
    hr_patterns = [
        "hr人事給与システム",
        "人事給与",
        "入社",
        "給与",
        "給与変更",
        "入社照合",
        "入社チェックリスト",
        "nyusha_checklist",
        "shinsotsu",
        "employee",
        "personnel",
    ]

    # Finance
    finance_patterns = [
        "財務会計システム",
        "財務会計",
        "経費",
        "経費承認",
        "支払処理",
        "精算",
        "expense_calc",
        "budget_analysis",
        "settai_keihi",
        "payment",
        "invoice",
        "expense",
    ]

    # Logistics
    logistics_patterns = [
        "受発注在庫管理システム",
        "受発注",
        "在庫",
        "在庫調整",
        "返品",
        "契約",
        "契約管理",
        "契約手続き",
        "keiyaku_kaijo_tetsuzuki",
        "shinkui_keiyaku_tetsuzuki",
        "shinkuitorihikisaki_touroku_tetsuzuki",
        "getsujitsu_teigaku_torihikisaki_ichiran",
        "inventory",
        "order",
        "contract",
        "logistics",
    ]

    if any(pattern in combined for pattern in hr_patterns):
        return "HR"

    if any(pattern in combined for pattern in finance_patterns):
        return "FINANCE"

    if any(pattern in combined for pattern in logistics_patterns):
        return "LOGISTICS"

    # Application/document evidence
    if "excel" in app or "excel" in combined:
        return "EXCEL"

    if "word" in app or "word" in combined:
        return "WORD"

    if "notepad" in app:
        return "NOTEPAD"

    if "terminal" in app or "powershell" in combined:
        return "TERMINAL"

    if "teams" in app:
        return "TEAMS"

    if "explorer" in app:
        return "EXPLORER"

    return "OTHER"


# ============================================================
# TASK SIGNATURES
# ============================================================

TASK_SIGNATURES = {
    "HR_PAYROLL_CHANGE": [
        "給与変更",
        "給与変更登録",
        "salary change",
        "payroll",
    ],

    "HR_ONBOARDING": [
        "入社手続き",
        "入社照合",
        "入社チェックリスト",
        "nyusha_checklist",
        "shinsotsu",
        "onboarding",
    ],

    "FINANCE_EXPENSE": [
        "経費承認",
        "expense_calc",
        "expense",
        "精算",
        "settai_keihi",
    ],

    "FINANCE_BUDGET": [
        "budget_analysis",
        "budget",
        "予算",
    ],

    "FINANCE_PAYMENT": [
        "支払処理",
        "payment",
        "支払い",
        "invoice",
    ],

    "LOGISTICS_INVENTORY": [
        "在庫調整",
        "在庫",
        "inventory",
        "受発注在庫管理システム",
    ],

    "LOGISTICS_CONTRACT": [
        "契約管理",
        "契約手続き",
        "新規契約手続き",
        "契約解除",
        "keiyaku_kaijo_tetsuzuki",
        "shinkui_keiyaku_tetsuzuki",
        "contract",
    ],

    "LOGISTICS_SUPPLIER": [
        "shinkuitorihikisaki_touroku_tetsuzuki",
        "torihikisaki",
        "取引先",
        "supplier",
    ],

    "LOGISTICS_ORDER": [
        "受発注",
        "order",
    ],
}


def detect_task_signatures(title, text):
    """
    Return task signatures supported by title/text evidence.
    """
    combined = normalize_text(
        f"{title} {text}"
    )

    matches = []

    for task_name, patterns in TASK_SIGNATURES.items():
        for pattern in patterns:
            if normalize_text(pattern) in combined:
                matches.append(task_name)
                break

    return matches


# ============================================================
# DOCUMENT SIGNATURE
# ============================================================

def detect_document(title):
    """
    Identify useful document/window patterns.

    This is intentionally lightweight; it does not attempt to
    understand every Word/Excel file.
    """
    normalized = normalize_text(title)

    patterns = [
        "expense_calc",
        "budget_analysis",
        "keiyaku_kaijo_tetsuzuki",
        "nyusha_checklist_shinsotsu_batch",
        "gyomu_itaku_kyuuyo_kitei",
        "settai_keihi_kitei",
        "shinkui_keiyaku_tetsuzuki",
        "shinkuitorihikisaki_touroku_tetsuzuki",
        "getsujitsu_teigaku_torihikisaki_ichiran",
        "精算確認メモ",
        "在庫調整メモ",
        "給与",
        "入社",
        "契約",
        "在庫",
    ]

    for pattern in patterns:
        if normalize_text(pattern) in normalized:
            return pattern

    return ""


# ============================================================
# EVENT FEATURES
# ============================================================

def build_event_features(event):
    app = get_app(event)
    title = get_window_title(event)
    text = get_extracted_text(event)
    event_type = get_event_type(event)

    area = classify_area(app, title, text)
    tasks = detect_task_signatures(title, text)
    document = detect_document(title)

    return {
        "timestamp_ms": parse_timestamp(event),
        "event_id": event.get("event_id"),
        "event_type": event_type,
        "app": app or "unknown",
        "title": title,
        "text": text,
        "area": area,
        "tasks": tasks,
        "document": document,
    }


# ============================================================
# BOUNDARY EVIDENCE
# ============================================================

def semantic_signature(feature):
    """
    High-level identity of an event.

    Task signature has priority over application.
    """
    if feature["tasks"]:
        return (
            feature["area"],
            tuple(sorted(feature["tasks"])),
            feature["document"],
        )

    if feature["document"]:
        return (
            feature["area"],
            (),
            feature["document"],
        )

    return (
        feature["area"],
        (),
        "",
    )


def calculate_boundary_evidence(previous, current, gap_seconds):
    """
    Calculate evidence that the current event begins a new task.

    IMPORTANT:
    A simple HR -> Finance transition is NOT sufficient by itself.
    """

    score = 0
    reasons = []

    prev_sig = semantic_signature(previous)
    curr_sig = semantic_signature(current)

    prev_tasks = set(previous["tasks"])
    curr_tasks = set(current["tasks"])

    # --------------------------------------------------------
    # Strongest evidence: explicit task change
    # --------------------------------------------------------

    if curr_tasks and prev_tasks and curr_tasks != prev_tasks:
        score += 5
        reasons.append("task_signature_change")

    # A new explicit task when the previous event had no task
    if curr_tasks and not prev_tasks:
        score += 3
        reasons.append("new_task_signature")

    # --------------------------------------------------------
    # Document change
    # --------------------------------------------------------

    if (
        current["document"]
        and previous["document"]
        and current["document"] != previous["document"]
    ):
        score += 3
        reasons.append("document_change")

    # --------------------------------------------------------
    # Business area change
    # --------------------------------------------------------

    if (
        previous["area"] != current["area"]
        and previous["area"] != "OTHER"
        and current["area"] != "OTHER"
    ):
        score += 2
        reasons.append(
            f"area_change_{previous['area']}_to_{current['area']}"
        )

    # --------------------------------------------------------
    # Large gap
    # --------------------------------------------------------

    if gap_seconds >= LONG_GAP_SECONDS:
        score += 5
        reasons.append("long_inactivity_gap")

    elif gap_seconds >= 20:
        score += 2
        reasons.append("moderate_inactivity_gap")

    # --------------------------------------------------------
    # Strong completion/start language
    # --------------------------------------------------------

    current_text = normalize_text(
        f"{current['title']} {current['text']}"
    )

    completion_markers = [
        "確認完了",
        "処理完了",
        "登録完了",
        "完了",
        "completed",
        "complete",
        "submitted",
        "success",
    ]

    if any(marker.lower() in current_text for marker in completion_markers):
        score += 1
        reasons.append("completion_marker")

    return score, reasons


# ============================================================
# STABILITY CHECK
# ============================================================

def find_stable_new_task(features, start_index):
    """
    Check whether a new task/semantic signature persists.

    This prevents a single screenshot or one system transition
    from creating a tiny 3-second segment.
    """

    if start_index >= len(features):
        return False

    candidate = features[start_index]

    # We need meaningful task evidence.
    if not candidate["tasks"] and not candidate["document"]:
        return False

    candidate_sig = semantic_signature(candidate)

    stable_count = 0

    for i in range(
        start_index,
        min(len(features), start_index + MIN_STABLE_EVENTS)
    ):
        current_sig = semantic_signature(features[i])

        if current_sig == candidate_sig:
            stable_count += 1

    return stable_count >= MIN_STABLE_EVENTS


# ============================================================
# SEGMENT CREATION
# ============================================================

def summarize_segment(
    features,
    session_id,
    chunk_id,
    segment_number,
    boundary_reasons=None,
):
    boundary_reasons = boundary_reasons or []

    timestamps = [
        f["timestamp_ms"]
        for f in features
        if f["timestamp_ms"] is not None
    ]

    start_ms = min(timestamps) if timestamps else None
    end_ms = max(timestamps) if timestamps else None

    duration_seconds = (
        (end_ms - start_ms) / 1000
        if start_ms is not None and end_ms is not None
        else 0
    )

    apps = Counter(
        f["app"]
        for f in features
        if f["app"]
    )

    areas = Counter(
        f["area"]
        for f in features
        if f["area"]
    )

    event_types = Counter(
        f["event_type"]
        for f in features
    )

    titles = Counter(
        f["title"]
        for f in features
        if f["title"]
    )

    tasks = Counter()

    for f in features:
        for task in f["tasks"]:
            tasks[task] += 1

    documents = Counter(
        f["document"]
        for f in features
        if f["document"]
    )

    text_evidence = []

    for f in features:
        text = f["text"]

        if text:
            text = re.sub(r"\s+", " ", text)

            if text not in text_evidence:
                text_evidence.append(text)

        if len(text_evidence) >= 12:
            break

    dominant_area = (
        areas.most_common(1)[0][0]
        if areas
        else "OTHER"
    )

    dominant_task = (
        tasks.most_common(1)[0][0]
        if tasks
        else None
    )

    # Confidence is based on evidence quality rather than
    # pretending that the segmentation is ground truth.
    confidence_score = 0

    if dominant_task:
        confidence_score += 3

    if len(tasks) >= 2:
        confidence_score += 1

    if documents:
        confidence_score += 1

    if len(areas) == 1:
        confidence_score += 1

    if duration_seconds >= MIN_SEGMENT_SECONDS:
        confidence_score += 1

    if len(features) >= MIN_SEGMENT_EVENTS:
        confidence_score += 1

    if confidence_score >= 6:
        confidence = "high"
    elif confidence_score >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "segment_id": (
            f"{session_id}_{chunk_id}_SEG_{segment_number:03d}"
        ),

        "session_id": session_id,
        "chunk_id": chunk_id,

        "start_ts": (
            datetime.fromtimestamp(
                start_ms / 1000
            ).isoformat()
            if start_ms is not None
            else None
        ),

        "end_ts": (
            datetime.fromtimestamp(
                end_ms / 1000
            ).isoformat()
            if end_ms is not None
            else None
        ),

        "start_timestamp_ms": start_ms,
        "end_timestamp_ms": end_ms,

        "duration_seconds": round(
            duration_seconds,
            2
        ),

        "event_count": len(features),

        "dominant_area": dominant_area,
        "dominant_task": dominant_task,

        "confidence": confidence,
        "confidence_score": confidence_score,

        "apps": dict(apps),
        "areas": dict(areas),
        "event_types": dict(event_types),

        "task_signatures": dict(tasks),
        "documents": dict(documents),

        "window_titles": dict(titles.most_common(15)),

        "text_evidence": text_evidence,

        "boundary_evidence": boundary_reasons,

        "start_event_id": (
            features[0]["event_id"]
            if features
            else None
        ),

        "end_event_id": (
            features[-1]["event_id"]
            if features
            else None
        ),
    }


# ============================================================
# LOAD CHUNKS
# ============================================================

def discover_chunks():
    """
    Dataset B has nested structure:

    dataset_b/
        ses_x/
            chunk_x/
                events.jsonl

    Chunk names can repeat across different sessions, so both
    session and chunk identity must be retained.
    """

    chunks = []

    for session_dir in sorted(DATASET_B.glob("ses_*")):

        if not session_dir.is_dir():
            continue

        session_id = session_dir.name

        for chunk_dir in sorted(session_dir.glob("chunk_*")):

            if not chunk_dir.is_dir():
                continue

            events_file = chunk_dir / "events.jsonl"

            if events_file.exists():
                chunks.append(
                    {
                        "session_id": session_id,
                        "chunk_id": chunk_dir.name,
                        "path": events_file,
                    }
                )

    return chunks


def load_chunk(path):
    events = []

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event["_timestamp_ms"] = parse_timestamp(event)

            events.append(event)

    # Timestamp order is more reliable for segmentation than
    # assuming file order is perfect.
    events.sort(
        key=lambda e: (
            e["_timestamp_ms"]
            if e["_timestamp_ms"] is not None
            else float("inf")
        )
    )

    return events


# ============================================================
# SEGMENT ONE CHUNK
# ============================================================

def segment_chunk(events, session_id, chunk_id):
    """
    Two-stage segmentation:

    1. Detect candidate boundaries using semantic evidence.
    2. Require the new task signature to persist.

    This is intentionally conservative.
    """

    if not events:
        return []

    features = [
        build_event_features(event)
        for event in events
        if meaningful_event(event)
    ]

    if not features:
        return []

    segments = []

    current = [features[0]]
    pending_boundary = None

    i = 1

    while i < len(features):

        previous = features[i - 1]
        current_feature = features[i]

        prev_ts = previous["timestamp_ms"]
        curr_ts = current_feature["timestamp_ms"]

        if (
            prev_ts is not None
            and curr_ts is not None
        ):
            gap_seconds = max(
                0,
                (curr_ts - prev_ts) / 1000
            )
        else:
            gap_seconds = 0

        score, reasons = calculate_boundary_evidence(
            previous,
            current_feature,
            gap_seconds
        )

        # ----------------------------------------------------
        # Strong semantic boundary
        # ----------------------------------------------------

        should_split = False

        # Long gap is strong enough on its own.
        if gap_seconds >= LONG_GAP_SECONDS:
            should_split = True

        # Explicit task change requires persistence.
        elif score >= 5:

            if find_stable_new_task(
                features,
                i
            ):
                should_split = True

        # ----------------------------------------------------
        # If a boundary is real, finalize current segment.
        # ----------------------------------------------------

        if should_split:

            # Don't create tiny fragments.
            current_duration = 0

            if (
                current[0]["timestamp_ms"] is not None
                and current[-1]["timestamp_ms"] is not None
            ):
                current_duration = (
                    current[-1]["timestamp_ms"]
                    - current[0]["timestamp_ms"]
                ) / 1000

            if (
                len(current) >= MIN_SEGMENT_EVENTS
                or current_duration >= MIN_SEGMENT_SECONDS
            ):

                segments.append(
                    (
                        current,
                        reasons
                    )
                )

                current = []

            else:
                # Tiny fragment: keep it with the next task.
                pass

        current.append(current_feature)

        i += 1

    # Final segment
    if current:
        segments.append(
            (
                current,
                []
            )
        )

    # --------------------------------------------------------
    # Merge tiny segments
    # --------------------------------------------------------

    merged = []

    for features_part, reasons in segments:

        if not merged:
            merged.append(
                [features_part, reasons]
            )
            continue

        duration = 0

        if (
            features_part[0]["timestamp_ms"] is not None
            and features_part[-1]["timestamp_ms"] is not None
        ):
            duration = (
                features_part[-1]["timestamp_ms"]
                - features_part[0]["timestamp_ms"]
            ) / 1000

        is_tiny = (
            len(features_part) < MIN_SEGMENT_EVENTS
            and duration < MIN_SEGMENT_SECONDS
        )

        # If tiny and no strong task evidence, merge backward.
        has_task = any(
            f["tasks"]
            for f in features_part
        )

        if is_tiny and not has_task:

            merged[-1][0].extend(features_part)

            if reasons:
                merged[-1][1].extend(reasons)

        else:
            merged.append(
                [features_part, reasons]
            )

    # --------------------------------------------------------
    # Produce final records
    # --------------------------------------------------------

    output = []

    for number, (part, reasons) in enumerate(
        merged,
        start=1
    ):

        output.append(
            summarize_segment(
                part,
                session_id,
                chunk_id,
                number,
                reasons
            )
        )

    return output


# ============================================================
# MAIN
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    chunks = discover_chunks()

    print("=" * 70)
    print("DATASET B SEGMENTATION V2")
    print("=" * 70)

    print(f"Session folders/chunks found: {len(chunks)}")

    total_events = 0
    total_segments = 0

    all_segments = []

    for index, chunk in enumerate(
        chunks,
        start=1
    ):

        session_id = chunk["session_id"]
        chunk_id = chunk["chunk_id"]
        path = chunk["path"]

        events = load_chunk(path)

        total_events += len(events)

        segments = segment_chunk(
            events,
            session_id,
            chunk_id
        )

        total_segments += len(segments)

        all_segments.extend(segments)

        print(
            f"[{index:02d}/{len(chunks):02d}] "
            f"{session_id} / {chunk_id}: "
            f"{len(events)} events -> "
            f"{len(segments)} segments"
        )

    # --------------------------------------------------------
    # Write JSONL
    # --------------------------------------------------------

    with OUTPUT_FILE.open(
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

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    durations = [
        s["duration_seconds"]
        for s in all_segments
    ]

    event_counts = [
        s["event_count"]
        for s in all_segments
    ]

    areas = Counter(
        s["dominant_area"]
        for s in all_segments
    )

    confidence = Counter(
        s["confidence"]
        for s in all_segments
    )

    tasks = Counter(
        s["dominant_task"]
        for s in all_segments
        if s["dominant_task"]
    )

    print()
    print("=" * 70)
    print("V2 SUMMARY")
    print("=" * 70)

    print(f"Chunks processed : {len(chunks)}")
    print(f"Total events     : {total_events}")
    print(f"Total segments   : {total_segments}")

    if durations:
        print(
            f"Avg duration     : "
            f"{sum(durations) / len(durations):.1f}s"
        )

        print(
            f"Min duration     : "
            f"{min(durations):.1f}s"
        )

        print(
            f"Max duration     : "
            f"{max(durations):.1f}s"
        )

    if event_counts:
        print(
            f"Avg events/seg   : "
            f"{sum(event_counts) / len(event_counts):.1f}"
        )

    print()
    print("DOMINANT AREAS")

    for area, count in areas.most_common():
        print(
            f"  {area:12s} {count:4d}"
        )

    print()
    print("CONFIDENCE")

    for level in [
        "high",
        "medium",
        "low"
    ]:
        print(
            f"  {level:8s} "
            f"{confidence.get(level, 0):4d}"
        )

    print()
    print("TASK SIGNATURES")

    for task, count in tasks.most_common():
        print(
            f"  {task:35s} {count:4d}"
        )

    print()
    print(f"Output written to:")
    print(OUTPUT_FILE)

    print("=" * 70)


if __name__ == "__main__":
    main()