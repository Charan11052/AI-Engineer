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

OUTPUT_FILE = OUTPUT_DIR / "dataset_b_segments_v3.jsonl"


# ============================================================
# CONFIGURATION
# ============================================================

MIN_SEGMENT_EVENTS = 15
MIN_SEGMENT_SECONDS = 8

# A concrete task signal must normally persist for this many
# meaningful events before it can create a new segment.
TASK_PERSISTENCE_EVENTS = 6

# Long inactivity is strong evidence of a new episode.
LONG_GAP_SECONDS = 45

# Long mixed segments get special treatment.
LONG_SEGMENT_SECONDS = 150


# ============================================================
# BASIC HELPERS
# ============================================================

def parse_timestamp(event):
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
            return int(
                datetime.fromisoformat(text).timestamp() * 1000
            )
        except Exception:
            pass

    return None


def get_app(event):
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
    context = event.get("context") or {}

    active_app = context.get("active_app") or {}

    if isinstance(active_app, dict):
        value = active_app.get("window_title")
        if value:
            return str(value).strip()

    value = context.get("window_title")

    return str(value).strip() if value else ""


def get_extracted_text(event):
    context = event.get("context") or {}
    extracted = context.get("extracted_text")

    if isinstance(extracted, dict):
        return str(
            extracted.get("text") or ""
        ).strip()

    if extracted:
        return str(extracted).strip()

    return ""


def get_event_type(event):
    return str(
        event.get("event_type") or ""
    ).lower()


def normalize_text(text):
    text = str(text or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def meaningful_event(event):
    ignored = {
        "session_start",
        "session_end",
        "extension_connected",
        "extension_disconnected",
    }

    return get_event_type(event) not in ignored


# ============================================================
# BUSINESS AREA
# ============================================================

def classify_area(app, title, text):

    combined = normalize_text(
        f"{title} {text}"
    )

    # Strong business-system identifiers first.
    if (
        "hr人事給与システム" in combined
        or "人事給与システム" in combined
    ):
        return "HR"

    if (
        "財務会計システム" in combined
        or "財務会計システム" in combined
    ):
        return "FINANCE"

    if (
        "受発注在庫管理システム" in combined
        or "受発注在庫" in combined
    ):
        return "LOGISTICS"

    # Document/application evidence.
    if "excel" in app or "excel" in combined:
        return "EXCEL"

    if "word" in app or "word" in combined:
        return "WORD"

    if "notepad" in app:
        return "NOTEPAD"

    if (
        "terminal" in app
        or "powershell" in combined
    ):
        return "TERMINAL"

    if "teams" in app:
        return "TEAMS"

    if "explorer" in app:
        return "EXPLORER"

    return "OTHER"


# ============================================================
# STRONG TASK SIGNATURES
# ============================================================

# IMPORTANT:
# These are deliberately concrete.
# Generic dashboard words such as "在庫", "給与", "経費"
# are NOT sufficient by themselves.

TASK_PATTERNS = {

    "HR_PAYROLL_CHANGE": [
        "給与変更登録",
        "給与変更処理",
        "salary change",
        "payroll change",
    ],

    "HR_ONBOARDING": [
        "入社照合完了",
        "入社手続き処理完了",
        "入社手続き完了",
        "入社照合",
        "nyusha_checklist_shinsotsu_batch",
        "onboarding completed",
        "onboarding",
    ],

    "FINANCE_EXPENSE": [
        "経費承認処理完了",
        "経費精算処理完了",
        "請求書照合完了",
        "expense_calc",
        "settai_keihi_kitei",
        "expense approval",
    ],

    "FINANCE_BUDGET": [
        "予算差異分析",
        "budget_analysis",
        "budget variance",
    ],

    "FINANCE_PAYMENT": [
        "支払処理完了",
        "支払処理",
        "payment processing",
        "payment completed",
    ],

    "LOGISTICS_INVENTORY": [
        "在庫調整登録",
        "在庫調整処理完了",
        "在庫調整完了",
        "inventory adjustment",
    ],

    "LOGISTICS_CONTRACT": [
        "契約管理処理",
        "契約処理記録",
        "契約処理完了",
        "新規契約手続き",
        "契約解除手続き",
        "keiyaku_kaijo_tetsuzuki",
        "shinkui_keiyaku_tetsuzuki",
        "contract processing",
    ],

    "LOGISTICS_SUPPLIER": [
        "取引先登録処理",
        "取引先登録完了",
        "shinkuitorihikisaki_touroku_tetsuzuki",
        "supplier registration",
    ],

    "LOGISTICS_ORDER": [
        "発注管理処理",
        "発注書確認・登録完了",
        "受注処理完了",
        "order processing",
    ],
}


def detect_task_signatures(title, text):

    combined = normalize_text(
        f"{title} {text}"
    )

    matches = []

    for task_name, patterns in TASK_PATTERNS.items():

        for pattern in patterns:

            if normalize_text(pattern) in combined:
                matches.append(task_name)
                break

    return matches


# ============================================================
# TASK COMPLETION
# ============================================================

COMPLETION_MARKERS = [
    "確認完了",
    "処理完了",
    "登録完了",
    "照合完了",
    "承認完了",
    "発注書確認・登録完了",
    "completed",
    "complete",
    "submitted",
    "success",
]


def has_completion_marker(title, text):

    combined = normalize_text(
        f"{title} {text}"
    )

    return any(
        normalize_text(marker) in combined
        for marker in COMPLETION_MARKERS
    )


# ============================================================
# DOCUMENT IDENTIFICATION
# ============================================================

DOCUMENT_PATTERNS = [
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
    "kazoku_teate_kitei",
]


def detect_document(title):

    normalized = normalize_text(title)

    for pattern in DOCUMENT_PATTERNS:

        if normalize_text(pattern) in normalized:
            return pattern

    return ""


# ============================================================
# EVENT FEATURES
# ============================================================

def build_feature(event):

    app = get_app(event)
    title = get_window_title(event)
    text = get_extracted_text(event)

    return {
        "timestamp_ms": parse_timestamp(event),
        "event_id": event.get("event_id"),
        "event_type": get_event_type(event),
        "app": app or "unknown",
        "title": title,
        "text": text,

        "area": classify_area(
            app,
            title,
            text
        ),

        "tasks": detect_task_signatures(
            title,
            text
        ),

        "document": detect_document(title),

        "completion": has_completion_marker(
            title,
            text
        ),
    }


# ============================================================
# STRONG TASK EVIDENCE
# ============================================================

def task_strength(feature):

    """
    Score the quality of task evidence.

    Explicit transaction phrases are strongest.
    Generic application/dashboard evidence is intentionally weak.
    """

    score = 0

    if feature["tasks"]:
        score += 5

    if feature["completion"]:
        score += 3

    if feature["document"]:
        score += 1

    return score


def task_signature(feature):

    if feature["tasks"]:
        return tuple(
            sorted(feature["tasks"])
        )

    return ()


# ============================================================
# STABLE TASK DETECTION
# ============================================================

def stable_task_start(features, index):

    if index >= len(features):
        return False

    candidate = features[index]

    candidate_tasks = set(
        candidate["tasks"]
    )

    # No concrete task evidence.
    if not candidate_tasks:
        return False

    stable = 0

    for j in range(
        index,
        min(
            len(features),
            index + TASK_PERSISTENCE_EVENTS
        )
    ):

        current_tasks = set(
            features[j]["tasks"]
        )

        if candidate_tasks.intersection(
            current_tasks
        ):
            stable += 1

    return stable >= TASK_PERSISTENCE_EVENTS


# ============================================================
# BOUNDARY DETECTION
# ============================================================

def boundary_score(previous, current, gap_seconds):

    score = 0
    reasons = []

    prev_tasks = set(
        previous["tasks"]
    )

    curr_tasks = set(
        current["tasks"]
    )

    # --------------------------------------------------------
    # Explicit task change
    # --------------------------------------------------------

    if (
        prev_tasks
        and curr_tasks
        and prev_tasks != curr_tasks
    ):

        score += 6
        reasons.append(
            "explicit_task_change"
        )

    # New task appearing after no task.
    elif (
        curr_tasks
        and not prev_tasks
    ):

        score += 4
        reasons.append(
            "new_explicit_task"
        )

    # --------------------------------------------------------
    # Document change
    # --------------------------------------------------------

    if (
        previous["document"]
        and current["document"]
        and previous["document"]
        != current["document"]
    ):

        score += 2
        reasons.append(
            "document_change"
        )

    # --------------------------------------------------------
    # Area change
    # --------------------------------------------------------

    if (
        previous["area"]
        != current["area"]
        and previous["area"] != "OTHER"
        and current["area"] != "OTHER"
    ):

        score += 1
        reasons.append(
            "business_area_change"
        )

    # --------------------------------------------------------
    # Completion followed by new evidence
    # --------------------------------------------------------

    if previous["completion"] and curr_tasks:

        score += 4
        reasons.append(
            "completion_then_new_task"
        )

    # --------------------------------------------------------
    # Long gap
    # --------------------------------------------------------

    if gap_seconds >= LONG_GAP_SECONDS:

        score += 6
        reasons.append(
            "long_inactivity_gap"
        )

    return score, reasons


# ============================================================
# SHOULD SPLIT
# ============================================================

def should_split(
    features,
    index,
    current_segment
):

    previous = features[index - 1]
    current = features[index]

    prev_ts = previous["timestamp_ms"]
    curr_ts = current["timestamp_ms"]

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

    score, reasons = boundary_score(
        previous,
        current,
        gap_seconds
    )

    # Strong inactivity boundary.
    if gap_seconds >= LONG_GAP_SECONDS:
        return True, reasons

    # A new concrete task must persist.
    if (
        score >= 6
        and stable_task_start(
            features,
            index
        )
    ):
        return True, reasons

    return False, []


# ============================================================
# SEGMENT SUMMARY
# ============================================================

def summarize_segment(
    features,
    session_id,
    chunk_id,
    number,
    boundary_evidence
):

    timestamps = [
        f["timestamp_ms"]
        for f in features
        if f["timestamp_ms"] is not None
    ]

    start_ms = (
        min(timestamps)
        if timestamps
        else None
    )

    end_ms = (
        max(timestamps)
        if timestamps
        else None
    )

    duration = (
        (end_ms - start_ms) / 1000
        if (
            start_ms is not None
            and end_ms is not None
        )
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

    tasks = Counter()

    for feature in features:

        for task in feature["tasks"]:
            tasks[task] += 1

    documents = Counter(
        f["document"]
        for f in features
        if f["document"]
    )

    titles = Counter(
        f["title"]
        for f in features
        if f["title"]
    )

    completions = sum(
        1
        for f in features
        if f["completion"]
    )

    text_evidence = []

    for feature in features:

        text = feature["text"]

        if not text:
            continue

        text = re.sub(
            r"\s+",
            " ",
            text
        ).strip()

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

    # --------------------------------------------------------
    # Evidence-based confidence
    # --------------------------------------------------------

    confidence_score = 0

    if dominant_task:
        confidence_score += 4

    if completions:
        confidence_score += 2

    if documents:
        confidence_score += 1

    if len(features) >= MIN_SEGMENT_EVENTS:
        confidence_score += 1

    if duration >= MIN_SEGMENT_SECONDS:
        confidence_score += 1

    if len(areas) == 1:
        confidence_score += 1

    if confidence_score >= 7:
        confidence = "high"
    elif confidence_score >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "segment_id": (
            f"{session_id}_"
            f"{chunk_id}_"
            f"SEG_{number:03d}"
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
            duration,
            2
        ),

        "event_count": len(features),

        "dominant_area": dominant_area,
        "dominant_task": dominant_task,

        "confidence": confidence,
        "confidence_score": confidence_score,

        "completion_evidence_count": completions,

        "apps": dict(apps),
        "areas": dict(areas),
        "event_types": dict(event_types),

        "task_signatures": dict(tasks),
        "documents": dict(documents),

        "window_titles": dict(
            titles.most_common(15)
        ),

        "text_evidence": text_evidence,

        "boundary_evidence": boundary_evidence,

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
# LOAD DATASET B
# ============================================================

def discover_chunks():

    chunks = []

    for session_dir in sorted(
        DATASET_B.glob("ses_*")
    ):

        if not session_dir.is_dir():
            continue

        session_id = session_dir.name

        for chunk_dir in sorted(
            session_dir.glob("chunk_*")
        ):

            if not chunk_dir.is_dir():
                continue

            events_file = (
                chunk_dir / "events.jsonl"
            )

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

            event["_timestamp_ms"] = (
                parse_timestamp(event)
            )

            events.append(event)

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

def segment_chunk(
    events,
    session_id,
    chunk_id
):

    features = [
        build_feature(event)
        for event in events
        if meaningful_event(event)
    ]

    if not features:
        return []

    raw_segments = []

    current = [
        features[0]
    ]

    pending_reasons = []

    for index in range(
        1,
        len(features)
    ):

        split, reasons = should_split(
            features,
            index,
            current
        )

        if split:

            duration = 0

            if (
                current[0]["timestamp_ms"]
                is not None
                and current[-1]["timestamp_ms"]
                is not None
            ):

                duration = (
                    current[-1]["timestamp_ms"]
                    - current[0]["timestamp_ms"]
                ) / 1000

            # Only close a segment if it is reasonably sized.
            if (
                len(current)
                >= MIN_SEGMENT_EVENTS
                or duration
                >= MIN_SEGMENT_SECONDS
            ):

                raw_segments.append(
                    (
                        current,
                        reasons
                    )
                )

                current = []

        current.append(
            features[index]
        )

    if current:

        raw_segments.append(
            (
                current,
                pending_reasons
            )
        )

    # --------------------------------------------------------
    # Merge fragments
    # --------------------------------------------------------

    merged = []

    for part, reasons in raw_segments:

        if not merged:

            merged.append(
                [part, reasons]
            )

            continue

        timestamps = [
            f["timestamp_ms"]
            for f in part
            if f["timestamp_ms"] is not None
        ]

        duration = (
            (
                max(timestamps)
                - min(timestamps)
            ) / 1000
            if timestamps
            else 0
        )

        tiny = (
            len(part) < MIN_SEGMENT_EVENTS
            and duration < MIN_SEGMENT_SECONDS
        )

        explicit_task = any(
            f["tasks"]
            for f in part
        )

        completion = any(
            f["completion"]
            for f in part
        )

        # Tiny fragments are merged unless they contain
        # explicit transaction evidence.
        if (
            tiny
            and not explicit_task
            and not completion
        ):

            merged[-1][0].extend(
                part
            )

            if reasons:
                merged[-1][1].extend(
                    reasons
                )

        else:

            merged.append(
                [part, reasons]
            )

    # --------------------------------------------------------
    # Build output
    # --------------------------------------------------------

    output = []

    for number, (
        part,
        reasons
    ) in enumerate(
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
    print("DATASET B SEGMENTATION V3")
    print("=" * 70)

    print(
        f"Session folders/chunks found: "
        f"{len(chunks)}"
    )

    total_events = 0
    total_segments = 0

    all_segments = []

    for number, chunk in enumerate(
        chunks,
        start=1
    ):

        session_id = chunk["session_id"]
        chunk_id = chunk["chunk_id"]

        events = load_chunk(
            chunk["path"]
        )

        total_events += len(events)

        segments = segment_chunk(
            events,
            session_id,
            chunk_id
        )

        total_segments += len(
            segments
        )

        all_segments.extend(
            segments
        )

        print(
            f"[{number:02d}/{len(chunks):02d}] "
            f"{session_id} / {chunk_id}: "
            f"{len(events)} events -> "
            f"{len(segments)} segments"
        )

    # --------------------------------------------------------
    # Write output
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

    tasks = Counter(
        s["dominant_task"] or "NONE"
        for s in all_segments
    )

    confidence = Counter(
        s["confidence"]
        for s in all_segments
    )

    short_count = sum(
        1
        for d in durations
        if d < 10
    )

    long_count = sum(
        1
        for d in durations
        if d > 150
    )

    print()
    print("=" * 70)
    print("V3 SUMMARY")
    print("=" * 70)

    print(
        f"Chunks processed : {len(chunks)}"
    )

    print(
        f"Total events     : {total_events}"
    )

    print(
        f"Total segments   : {total_segments}"
    )

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

    print(
        f"Segments <10s    : {short_count}"
    )

    print(
        f"Segments >150s   : {long_count}"
    )

    print()
    print("DOMINANT AREAS")

    for area, count in areas.most_common():

        print(
            f"  {area:15s} {count:4d}"
        )

    print()
    print("DOMINANT TASKS")

    for task, count in tasks.most_common():

        print(
            f"  {task:35s} {count:4d}"
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
    print("Output:")
    print(OUTPUT_FILE)

    print("=" * 70)


if __name__ == "__main__":
    main()