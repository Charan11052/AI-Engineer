import json
import re
from pathlib import Path
from datetime import datetime


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATASET_B = ROOT / "data" / "dataset_b"
OUTPUT_DIR = ROOT / "outputs" / "dataset_b"

OUTPUT_FILE = OUTPUT_DIR / "dataset_b_segments_v6.jsonl"


# ============================================================
# CONFIGURATION
# ============================================================

# Maximum amount of time we look backwards from a completion
# event to recover the beginning of the execution.
MAX_LOOKBACK_SECONDS = 45

# Long inactivity gap can indicate a process boundary.
GAP_SECONDS = 8

# Small amount of context after completion.
POST_COMPLETION_SECONDS = 2


# ============================================================
# STRICT BUSINESS COMPLETION PATTERNS
# ============================================================

# These are intended to identify ACTUAL operational outcomes.
#
# Generic words such as:
#   完了
#   登録
#   承認
#
# are not sufficient on their own.
#
# Dashboards and Word procedure documents frequently contain
# these words without representing an actual execution.
# ============================================================

COMPLETION_PATTERNS = {

    # -------------------------
    # HR
    # -------------------------

    "HR_ONBOARDING": [
        r"入社照合完了",
        r"入社確認完了",
    ],

    "HR_PAYROLL": [
        r"給与変更登録.*確認完了",
        r"給与変更登録完了",
    ],

    "HR_ATTENDANCE": [
        r"勤怠申請確認.*(?:完了|承認)",
    ],


    # -------------------------
    # FINANCE
    # -------------------------

    "FINANCE_EXPENSE": [
        r"経費精算処理.*完了",
        r"経費精算確認.*完了",
        r"経費申請.*(?:承認|完了)",
        r"精算確認.*完了",
    ],

    "FINANCE_INVOICE": [
        r"請求書照合完了",
        r"請求書確認.*完了",
    ],

    "FINANCE_PAYMENT": [
        r"支払処理.*完了",
        r"支払確認.*完了",
        r"支払申請.*(?:承認|完了)",
    ],

    "FINANCE_BUDGET": [
        r"予算差異分析完了",
        r"予算分析.*完了",
        r"予算確認.*完了",
    ],


    # -------------------------
    # LOGISTICS
    # -------------------------

    "LOGISTICS_INVENTORY": [
        r"在庫調整登録(?:。|：)",
        r"在庫調整.*完了",
        r"在庫確認.*完了",
    ],

    "LOGISTICS_CONTRACT": [
        r"契約管理処理.*完了",
        r"契約管理処理.*登録完了",
    ],

    "LOGISTICS_ORDER": [
        r"発注書確認・登録完了",
        r"発注管理処理.*完了",
        r"発注処理.*完了",
    ],

    # Supplier registration is handled separately.
    "LOGISTICS_SUPPLIER": [],
}


# ============================================================
# SUPPORTING TASK EVIDENCE
# ============================================================

# These patterns help understand what a segment is about.
#
# They DO NOT create a segment boundary by themselves.
# ============================================================

TASK_PATTERNS = {

    # -------------------------
    # HR
    # -------------------------

    "HR_ONBOARDING": [
        r"入社",
        r"新入社員",
        r"オンボーディング",
        r"人事",
    ],

    "HR_PAYROLL": [
        r"給与",
        r"給与変更",
        r"給与計算",
    ],

    "HR_ATTENDANCE": [
        r"勤怠",
        r"勤務時間",
        r"出勤",
    ],


    # -------------------------
    # FINANCE
    # -------------------------

    "FINANCE_EXPENSE": [
        r"経費",
        r"精算",
        r"expense",
        r"settai",
    ],

    "FINANCE_INVOICE": [
        r"請求書",
        r"invoice",
    ],

    "FINANCE_PAYMENT": [
        r"支払",
        r"payment",
    ],

    "FINANCE_BUDGET": [
        r"予算",
        r"budget",
    ],


    # -------------------------
    # LOGISTICS
    # -------------------------

    "LOGISTICS_INVENTORY": [
        r"在庫",
        r"inventory",
        r"在庫調整",
    ],

    "LOGISTICS_CONTRACT": [
        r"契約",
        r"contract",
    ],

    "LOGISTICS_ORDER": [
        r"発注",
        r"注文",
        r"order",
    ],

    "LOGISTICS_SUPPLIER": [
        r"取引先",
        r"仕入先",
        r"サプライヤ",
        r"supplier",
    ],
}


# ============================================================
# BUSINESS AREA MAPPING
# ============================================================

TASK_TO_AREA = {

    "HR_ONBOARDING": "HR",
    "HR_PAYROLL": "HR",
    "HR_ATTENDANCE": "HR",

    "FINANCE_EXPENSE": "Finance",
    "FINANCE_INVOICE": "Finance",
    "FINANCE_PAYMENT": "Finance",
    "FINANCE_BUDGET": "Finance",

    "LOGISTICS_INVENTORY": "Logistics",
    "LOGISTICS_CONTRACT": "Logistics",
    "LOGISTICS_ORDER": "Logistics",
    "LOGISTICS_SUPPLIER": "Logistics",
}


# ============================================================
# TIMESTAMP
# ============================================================

def parse_timestamp(event):
    """
    Return timestamp in milliseconds.

    Dataset B provides timestamp_ms directly, so that is
    preferred. timestamp_iso is used as a fallback.
    """

    value = event.get("timestamp_ms")

    if value is not None:
        try:
            return int(value)
        except (TypeError, ValueError):
            pass

    timestamp_iso = event.get("timestamp_iso")

    if timestamp_iso:
        try:
            dt = datetime.fromisoformat(
                timestamp_iso.replace("Z", "+00:00")
            )

            return int(dt.timestamp() * 1000)

        except Exception:
            pass

    return None


# ============================================================
# EVENT TEXT
# ============================================================

def get_event_text(event):
    """
    Extract useful textual evidence from an event.

    Priority is given to structured extracted text and
    window-title information.
    """

    pieces = []

    context = event.get("context", {})

    # --------------------------------------------------------
    # Extracted OCR / structured text
    # --------------------------------------------------------

    extracted = context.get("extracted_text")

    if isinstance(extracted, dict):

        text = extracted.get("text")

        if text:
            pieces.append(str(text))

    elif isinstance(extracted, str):

        pieces.append(extracted)

    # --------------------------------------------------------
    # Active application
    # --------------------------------------------------------

    active_app = context.get("active_app")

    if isinstance(active_app, dict):

        title = active_app.get("window_title")

        if title:
            pieces.append(str(title))

        app_name = active_app.get("app_name")

        if app_name:
            pieces.append(str(app_name))

    # --------------------------------------------------------
    # Payload
    # --------------------------------------------------------

    payload = event.get("payload", {})

    if isinstance(payload, dict):

        for key in [
            "new_app",
            "previous_app",
            "window_title",
            "text",
        ]:

            value = payload.get(key)

            if value:
                pieces.append(str(value))

    return " ".join(pieces)


# ============================================================
# ACTIVE APPLICATION
# ============================================================

def get_active_app(event):
    """
    Return normalized active application name.
    """

    context = event.get("context", {})

    active_app = context.get("active_app")

    if isinstance(active_app, dict):

        app = (
            active_app.get("app_name")
            or active_app.get("process_name")
        )

        if app:
            return str(app)

    return "unknown"


# ============================================================
# DASHBOARD DETECTION
# ============================================================

def is_dashboard_text(text):
    """
    Detect generic dashboard/status-page text.

    Dashboards can contain many different business terms
    simultaneously.

    IMPORTANT:
    Dashboard detection is NOT allowed to override a
    strong, unique completion pattern.
    """

    if not text:
        return False

    lower = text.lower()

    dashboard_terms = [

        "dashboard",
        "ダッシュボード",

        "処理状況",
        "処理一覧",

        "ステータス",
        "status",

        "pending",
        "completed",

        "件",
        "件数",
    ]

    matches = sum(
        term in lower
        for term in dashboard_terms
    )

    return matches >= 2


# ============================================================
# STRONG SUPPLIER COMPLETION
# ============================================================

def is_strong_supplier_completion(event):
    """
    Detect a genuine supplier-registration completion.

    We require:

    1. Supplier/entity terminology
    2. A concrete ID/code/number
    3. Registration/completion evidence

    This prevents policy documents from becoming
    LOGISTICS_SUPPLIER executions.
    """

    text = get_event_text(event)

    if not text:
        return False

    supplier_terms = [
        "取引先",
        "仕入先",
        "サプライヤ",
    ]

    has_supplier = any(
        term in text
        for term in supplier_terms
    )

    # Concrete identifier.
    has_identifier = bool(
        re.search(
            r"(?:ID|コード|番号)\s*[:：]",
            text,
            flags=re.IGNORECASE
        )
    )

    # Actual registration/completion wording.
    has_registration = bool(
        re.search(
            r"(?:登録完了|登録済み|登録しました)",
            text
        )
    )

    return (
        has_supplier
        and has_identifier
        and has_registration
    )


# ============================================================
# COMPLETION DETECTION
# ============================================================

def detect_completion(event):
    """
    Detect a high-confidence operational completion.

    IMPORTANT V6 CHANGE:

    Strong completion evidence is checked BEFORE dashboard
    rejection.

    Therefore a genuine operational completion such as:

        請求書照合完了
        発注書確認・登録完了
        入社照合完了
        予算差異分析完了

    can still be recognized even if the same OCR text also
    contains generic dashboard/status information.

    Returns:
        task name
        or None
    """

    text = get_event_text(event)

    if not text:
        return None

    matches = []

    # --------------------------------------------------------
    # Check all strict completion patterns first.
    # --------------------------------------------------------

    for task_name, patterns in COMPLETION_PATTERNS.items():

        # ----------------------------------------------------
        # Supplier is handled with stricter evidence.
        # ----------------------------------------------------

        if task_name == "LOGISTICS_SUPPLIER":

            if is_strong_supplier_completion(event):

                matches.append(
                    task_name
                )

            continue

        # ----------------------------------------------------
        # Normal task patterns
        # ----------------------------------------------------

        for pattern in patterns:

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            ):

                matches.append(
                    task_name
                )

                break

    # --------------------------------------------------------
    # Dashboard handling happens AFTER strict completion
    # detection.
    #
    # A dashboard without a strong completion is ignored.
    # A dashboard containing exactly one strong completion
    # is allowed to remain an anchor.
    # --------------------------------------------------------

    if is_dashboard_text(text) and len(matches) == 0:
        return None

    # --------------------------------------------------------
    # Only accept an anchor if exactly one task matches.
    # --------------------------------------------------------

    if len(matches) == 1:

        return matches[0]

    return None


# ============================================================
# SUPPORTING TASK DETECTION
# ============================================================

def detect_supporting_tasks(event):
    """
    Detect task-related evidence.

    Supporting evidence does NOT directly create a segment.
    """

    text = get_event_text(event)

    if not text:
        return []

    # Ignore generic dashboards.
    if is_dashboard_text(text):
        return []

    matches = []

    for task_name, patterns in TASK_PATTERNS.items():

        for pattern in patterns:

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            ):

                matches.append(
                    task_name
                )

                break

    return matches


# ============================================================
# SESSION / CHUNK IDENTIFICATION
# ============================================================

def get_session_and_chunk(path):
    """
    Dataset B structure:

        dataset_b/
            ses_x/
                chunk_x/
                    events.jsonl

    Chunk names can repeat across sessions.

    Therefore both session and chunk are included in IDs.
    """

    parts = list(path.parts)

    session = None

    # Search backwards for ses_*.
    for part in reversed(parts):

        if part.startswith("ses_"):

            session = part

            break

    if session is None:

        session = "unknown_session"

    chunk_name = path.parent.name

    return (
        session,
        chunk_name
    )


# ============================================================
# LOAD DATASET B
# ============================================================

def load_chunks():
    """
    Load all Dataset B event chunks.

    Recording chunk boundaries are preserved but are NOT
    automatically treated as business-process boundaries.
    """

    chunks = []

    for path in DATASET_B.rglob("events.jsonl"):

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

                ts = parse_timestamp(event)

                if ts is None:
                    continue

                event["_ts"] = ts

                events.append(event)

        if not events:
            continue

        events.sort(
            key=lambda x: x["_ts"]
        )

        session, chunk_name = (
            get_session_and_chunk(path)
        )

        chunks.append(
            {
                "path": path,
                "session": session,
                "chunk": chunk_name,
                "events": events,
            }
        )

    chunks.sort(
        key=lambda x: (
            x["events"][0]["_ts"],
            x["session"],
            x["chunk"],
        )
    )

    return chunks


# ============================================================
# FIND SEGMENT START
# ============================================================

def find_start(
    events,
    completion_index,
    task_name,
    minimum_index=0
):
    """
    Walk backwards from the completion anchor to recover
    the beginning of the execution.

    minimum_index prevents the new execution from reaching
    backwards into an already-used segment.

    Stop when:
    1. Maximum lookback is reached
    2. Long inactivity gap occurs
    3. Another strong completion is encountered
    4. A different confirmed task appears
    5. The previous segment boundary is reached
    """

    completion_ts = (
        events[completion_index]["_ts"]
    )

    start_index = completion_index

    for i in range(
        completion_index - 1,
        minimum_index - 1,
        -1
    ):

        current = events[i]

        current_ts = current["_ts"]

        # ----------------------------------------------------
        # Maximum lookback
        # ----------------------------------------------------

        if (
            completion_ts - current_ts
            > MAX_LOOKBACK_SECONDS * 1000
        ):
            break

        # ----------------------------------------------------
        # Long inactivity gap
        # ----------------------------------------------------

        next_ts = events[i + 1]["_ts"]

        if (
            next_ts - current_ts
            > GAP_SECONDS * 1000
        ):
            break

        # ----------------------------------------------------
        # Another strong completion
        # ----------------------------------------------------

        previous_completion = detect_completion(
            current
        )

        if previous_completion is not None:
            break

        # ----------------------------------------------------
        # Different task evidence
        # ----------------------------------------------------

        supporting = detect_supporting_tasks(
            current
        )

        different_tasks = [
            task
            for task in supporting
            if task != task_name
        ]

        if different_tasks:
            break

        start_index = i

    return start_index
# ============================================================
# FIND SEGMENT END
# ============================================================

def find_end(
    events,
    completion_index
):
    """
    Include a small amount of context after the completion
    event without consuming the next execution.
    """

    completion_ts = (
        events[
            completion_index
        ]["_ts"]
    )

    end_index = completion_index

    for i in range(
        completion_index + 1,
        len(events)
    ):

        current_ts = (
            events[i]["_ts"]
        )

        if (
            current_ts
            - completion_ts
            > POST_COMPLETION_SECONDS * 1000
        ):

            break

        end_index = i

    return end_index


# ============================================================
# BUILD SEGMENT
# ============================================================

def build_segment(
    events,
    start_index,
    end_index,
    completion_index,
    task_name,
    session,
    chunk_name,
    segment_number
):
    """
    Build the final segment representation.
    """

    segment_events = events[
        start_index:
        end_index + 1
    ]

    start_ts = (
        segment_events[0]["_ts"]
    )

    end_ts = (
        segment_events[-1]["_ts"]
    )

    apps = []

    supporting_tasks = set()

    event_type_counts = {}

    for event in segment_events:

        # ----------------------------------------------------
        # Applications
        # ----------------------------------------------------

        app = get_active_app(
            event
        )

        if app not in apps:

            apps.append(
                app
            )

        # ----------------------------------------------------
        # Supporting tasks
        # ----------------------------------------------------

        for task in (
            detect_supporting_tasks(
                event
            )
        ):

            supporting_tasks.add(
                task
            )

        # ----------------------------------------------------
        # Event types
        # ----------------------------------------------------

        event_type = event.get(
            "event_type",
            "unknown"
        )

        event_type_counts[
            event_type
        ] = (
            event_type_counts.get(
                event_type,
                0
            ) + 1
        )

    area = TASK_TO_AREA.get(
        task_name,
        "Other"
    )

    completion_text = (
        get_event_text(
            events[
                completion_index
            ]
        )
    )

    duration_seconds = (
        end_ts - start_ts
    ) / 1000.0

    return {

        "segment_id": (
            f"{session}__"
            f"{chunk_name}__"
            f"segment_{segment_number:04d}"
        ),

        "session": session,

        "chunk": chunk_name,

        "task": task_name,

        "business_area": area,

        "start_timestamp_ms": start_ts,

        "end_timestamp_ms": end_ts,

        "duration_seconds": round(
            duration_seconds,
            3
        ),

        "event_count": len(
            segment_events
        ),

        "applications": apps,

        "supporting_tasks": sorted(
            supporting_tasks
        ),

        "completion_evidence": (
            completion_text
        ),

        "completion_event_index": (
            completion_index
        ),

        "start_event_index": (
            start_index
        ),

        "end_event_index": (
            end_index
        ),

        "event_type_counts": (
            event_type_counts
        ),

        "confidence": "high",
    }


# ============================================================
# SEGMENT ONE CHUNK
# ============================================================

def segment_chunk(chunk):

    events = chunk[
        "events"
    ]

    session = chunk[
        "session"
    ]

    chunk_name = chunk[
        "chunk"
    ]

    segments = []

    # Last event already assigned to a segment.
    used_until = -1

    segment_number = 1

    for i, event in enumerate(
        events
    ):

        task_name = detect_completion(
            event
        )

        if task_name is None:
            continue

        # ----------------------------------------------------
        # Prevent event reuse.
        # ----------------------------------------------------

        if i <= used_until:
            continue

        # ----------------------------------------------------
        # Recover beginning.
        # ----------------------------------------------------

        start_index = find_start(
            events,
            i,
            task_name,
            minimum_index=used_until + 1
        )
        # ----------------------------------------------------
        # Recover small ending context.
        # ----------------------------------------------------

        end_index = find_end(
            events,
            i
        )

        # ----------------------------------------------------
        # Avoid overlapping segments.
        # ----------------------------------------------------

        if start_index <= used_until:
            continue

        # ----------------------------------------------------
        # Build segment.
        # ----------------------------------------------------

        segment = build_segment(
            events=events,
            start_index=start_index,
            end_index=end_index,
            completion_index=i,
            task_name=task_name,
            session=session,
            chunk_name=chunk_name,
            segment_number=segment_number,
        )

        segments.append(
            segment
        )

        used_until = end_index

        segment_number += 1

    return segments


# ============================================================
# MAIN
# ============================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chunks = load_chunks()

    print("=" * 70)
    print("DATASET B SEGMENTATION")
    print("=" * 70)
    print(f"Chunks loaded: {len(chunks)}")

    all_segments = []
    for chunk in chunks:
        all_segments.extend(segment_chunk(chunk))

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for segment in all_segments:
            f.write(json.dumps(segment, ensure_ascii=False) + "\n")

    if not all_segments:
        print("WARNING: No segments were detected.")
        return

    durations = [s["duration_seconds"] for s in all_segments]
    event_counts = [s["event_count"] for s in all_segments]
    area_counts, task_counts = {}, {}
    for s in all_segments:
        area_counts[s["business_area"]] = area_counts.get(s["business_area"], 0) + 1
        task_counts[s["task"]] = task_counts.get(s["task"], 0) + 1

    short = sum(1 for d in durations if d < 10)
    medium = sum(1 for d in durations if 10 <= d <= 120)
    long_ = sum(1 for d in durations if d > 120)

    print(f"\nSegments: {len(all_segments)}")
    print(f"Duration (s) — avg: {sum(durations) / len(durations):.2f}, "
          f"min: {min(durations):.2f}, max: {max(durations):.2f}")
    print(f"Avg events/segment: {sum(event_counts) / len(event_counts):.1f}")

    print("\nBusiness areas:")
    for area, count in sorted(area_counts.items(), key=lambda x: -x[1]):
        print(f"  {area}: {count}")

    print("\nTasks:")
    for task, count in sorted(task_counts.items(), key=lambda x: -x[1]):
        print(f"  {task}: {count}")

    print("\nDuration buckets:")
    print(f"  <10s:    {short}")
    print(f"  10-120s: {medium}")
    print(f"  >120s:   {long_}")

    print(f"\nOutput written to: {OUTPUT_FILE}")
    print("=" * 70)

    # KNOWN LIMITATION (see /reports/final_report.md and PIPELINE.md):
    # this segmenter anchors each unit of work on a hardcoded Japanese
    # "completion phrase" match and takes a fixed lookback window
    # (<=45s before / 2s after the match). It marks the END of a task,
    # not its true START, so segment durations understate real task
    # length and only a small fraction of total session time gets a
    # label. Fixing this requires reprocessing the raw event stream
    # with real task-start detection (e.g. first navigation into the
    # relevant screen/case), not a formatting change.

if __name__ == "__main__":
    main()