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

OUTPUT_FILE = OUTPUT_DIR / "dataset_b_segments_v8.jsonl"


# ============================================================
# V8 CONFIGURATION
# ============================================================

# Maximum amount of time we look backwards from a completion
# event to recover the beginning of the execution.
START_LOOKBACK_SECONDS = 60

# Strong inactivity gaps.
STRONG_GAP_SECONDS = 5
VERY_STRONG_GAP_SECONDS = 8

# Maximum allowed segment duration.
MAX_SEGMENT_SECONDS = 120

# Require multiple activity events after a candidate start.
MIN_ACTIVITY_AFTER = 4

# Dense activity window.
DENSE_ACTIVITY_WINDOW_SECONDS = 8

# Minimum activity events inside dense window.
MIN_DENSE_ACTIVITY = 3


# ============================================================
# STRICT BUSINESS COMPLETION PATTERNS
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

    "LOGISTICS_SUPPLIER": [],
}


# ============================================================
# SUPPORTING TASK EVIDENCE
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
# EVENT TYPES
# ============================================================

ACTIVITY_EVENT_TYPES = {
    "keystroke",
    "mouse_click",
    "mouse_scroll",
    "browser_click",
    "browser_navigation",
    "browser_form_input",
    "app_switch",
    "shortcut",
    "clipboard_change",
    "upload_completed",
}


# ============================================================
# TIMESTAMP
# ============================================================

def parse_timestamp(event):
    """
    Return timestamp in milliseconds.

    timestamp_ms is preferred.
    timestamp_iso is used as fallback.
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
    """

    pieces = []

    context = event.get(
        "context",
        {}
    )

    # --------------------------------------------------------
    # Extracted text
    # --------------------------------------------------------

    extracted = context.get(
        "extracted_text"
    )

    if isinstance(extracted, dict):

        text = extracted.get(
            "text"
        )

        if text:
            pieces.append(
                str(text)
            )

    elif isinstance(extracted, str):

        pieces.append(
            extracted
        )

    # --------------------------------------------------------
    # Active application
    # --------------------------------------------------------

    active_app = context.get(
        "active_app"
    )

    if isinstance(active_app, dict):

        title = active_app.get(
            "window_title"
        )

        if title:
            pieces.append(
                str(title)
            )

        app_name = active_app.get(
            "app_name"
        )

        if app_name:
            pieces.append(
                str(app_name)
            )

    # --------------------------------------------------------
    # Payload
    # --------------------------------------------------------

    payload = event.get(
        "payload",
        {}
    )

    if isinstance(payload, dict):

        for key in [
            "new_app",
            "previous_app",
            "window_title",
            "text",
        ]:

            value = payload.get(
                key
            )

            if value:
                pieces.append(
                    str(value)
                )

    return " ".join(
        pieces
    )


# ============================================================
# ACTIVE APPLICATION
# ============================================================

def get_active_app(event):
    """
    Return normalized active application name.
    """

    context = event.get(
        "context",
        {}
    )

    active_app = context.get(
        "active_app"
    )

    if isinstance(active_app, dict):

        app = (
            active_app.get(
                "app_name"
            )
            or active_app.get(
                "process_name"
            )
        )

        if app:
            return str(app)

    return "unknown"


# ============================================================
# APP IDENTITY
# ============================================================

def get_app_identity(event):
    """
    Return normalized application identity.
    """

    context = event.get(
        "context",
        {}
    )

    active_app = context.get(
        "active_app"
    )

    if isinstance(active_app, dict):

        app = (
            active_app.get(
                "app_name"
            )
            or active_app.get(
                "process_name"
            )
            or ""
        )

        return str(
            app
        ).strip().lower()

    return ""


# ============================================================
# WINDOW TITLE
# ============================================================

def get_window_title(event):
    """
    Return normalized active window title.
    """

    context = event.get(
        "context",
        {}
    )

    active_app = context.get(
        "active_app"
    )

    if isinstance(active_app, dict):

        title = active_app.get(
            "window_title"
        )

        if title:
            return str(
                title
            ).strip().lower()

    return ""


# ============================================================
# EVENT TYPE
# ============================================================

def get_event_type(event):
    return event.get(
        "event_type",
        "unknown"
    )


# ============================================================
# ACTIVITY DETECTION
# ============================================================

def is_activity_event(event):
    """
    Determine whether an event represents meaningful
    user interaction or workflow movement.
    """

    return (
        get_event_type(event)
        in ACTIVITY_EVENT_TYPES
    )


# ============================================================
# DASHBOARD DETECTION
# ============================================================

def is_dashboard_text(text):
    """
    Detect generic dashboard/status-page text.
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
    Detect genuine supplier registration completion.
    """

    text = get_event_text(
        event
    )

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

    has_identifier = bool(
        re.search(
            r"(?:ID|コード|番号)\s*[:：]",
            text,
            flags=re.IGNORECASE
        )
    )

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
    """

    text = get_event_text(
        event
    )

    if not text:
        return None

    matches = []

    # --------------------------------------------------------
    # Strict completion patterns
    # --------------------------------------------------------

    for task_name, patterns in (
        COMPLETION_PATTERNS.items()
    ):

        if task_name == "LOGISTICS_SUPPLIER":

            if is_strong_supplier_completion(
                event
            ):

                matches.append(
                    task_name
                )

            continue

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
    # Ignore generic dashboards.
    # --------------------------------------------------------

    if (
        is_dashboard_text(text)
        and len(matches) == 0
    ):

        return None

    # --------------------------------------------------------
    # Exactly one task must match.
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

    Supporting evidence does not directly create a segment.
    """

    text = get_event_text(
        event
    )

    if not text:
        return []

    if is_dashboard_text(text):
        return []

    matches = []

    for task_name, patterns in (
        TASK_PATTERNS.items()
    ):

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
    """

    parts = list(
        path.parts
    )

    session = None

    for part in reversed(
        parts
    ):

        if part.startswith(
            "ses_"
        ):

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

    Chunk boundaries are preserved but are not automatically
    treated as business-process boundaries.
    """

    chunks = []

    for path in DATASET_B.rglob(
        "events.jsonl"
    ):

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

                    event = json.loads(
                        line
                    )

                except json.JSONDecodeError:

                    continue

                ts = parse_timestamp(
                    event
                )

                if ts is None:
                    continue

                event["_ts"] = ts

                events.append(
                    event
                )

        if not events:
            continue

        events.sort(
            key=lambda x: x["_ts"]
        )

        session, chunk_name = (
            get_session_and_chunk(
                path
            )
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
# ACTIVITY AFTER CANDIDATE
# ============================================================

def count_activity_after(
    events,
    start_index,
    completion_index
):
    """
    Count activity within the dense activity window
    following a candidate.
    """

    start_ts = events[
        start_index
    ]["_ts"]

    limit_ts = (
        start_ts
        + DENSE_ACTIVITY_WINDOW_SECONDS * 1000
    )

    count = 0

    for j in range(
        start_index + 1,
        completion_index + 1
    ):

        if events[j]["_ts"] > limit_ts:
            break

        if is_activity_event(
            events[j]
        ):

            count += 1

    return count


# ============================================================
# CONTINUED ACTIVITY
# ============================================================

def has_continued_activity(
    events,
    start_index,
    completion_index
):
    """
    Require multiple activity events after a proposed start.
    """

    count = 0

    for j in range(
        start_index + 1,
        completion_index + 1
    ):

        if is_activity_event(
            events[j]
        ):

            count += 1

            if count >= MIN_ACTIVITY_AFTER:
                return True

    return False


# ============================================================
# CANDIDATE START SCORE
# ============================================================

def candidate_start_score(
    events,
    index,
    completion_index,
    task_name
):
    """
    Score a possible beginning of the workflow.

    The score uses:

        - inactivity gap
        - browser navigation
        - form input
        - clicks
        - application changes
        - window changes
        - task evidence
        - competing task evidence
        - continued activity
    """

    event = events[
        index
    ]

    score = 0.0

    reasons = []

    event_type = get_event_type(
        event
    )

    # --------------------------------------------------------
    # Gap before candidate
    # --------------------------------------------------------

    if index > 0:

        gap = (
            event["_ts"]
            - events[index - 1]["_ts"]
        ) / 1000.0

        if gap >= VERY_STRONG_GAP_SECONDS:

            score += 6
            reasons.append(
                "idle_gap_>=8s"
            )

        elif gap >= STRONG_GAP_SECONDS:

            score += 4
            reasons.append(
                "idle_gap_>=5s"
            )

        elif gap >= 3:

            score += 2
            reasons.append(
                "idle_gap_>=3s"
            )

    # --------------------------------------------------------
    # Browser navigation
    # --------------------------------------------------------

    if event_type == "browser_navigation":

        score += 5

        reasons.append(
            "browser_navigation"
        )

    # --------------------------------------------------------
    # Form interaction
    # --------------------------------------------------------

    elif event_type == "browser_form_input":

        score += 4

        reasons.append(
            "browser_form_input"
        )

    # --------------------------------------------------------
    # Click
    # --------------------------------------------------------

    elif event_type in {
        "mouse_click",
        "browser_click",
    }:

        score += 2

        reasons.append(
            "click"
        )

    # --------------------------------------------------------
    # Application change
    # --------------------------------------------------------

    if index > 0:

        previous_app = get_app_identity(
            events[index - 1]
        )

        current_app = get_app_identity(
            event
        )

        if (
            current_app
            and previous_app
            and current_app != previous_app
        ):

            score += 3

            reasons.append(
                "app_change"
            )

    # --------------------------------------------------------
    # Window change
    # --------------------------------------------------------

    if index > 0:

        previous_title = get_window_title(
            events[index - 1]
        )

        current_title = get_window_title(
            event
        )

        if (
            current_title
            and previous_title
            and current_title != previous_title
        ):

            score += 2

            reasons.append(
                "window_change"
            )

    # --------------------------------------------------------
    # Task evidence
    # --------------------------------------------------------

    supporting = detect_supporting_tasks(
        event
    )

    if task_name in supporting:

        score += 3

        reasons.append(
            "task_evidence"
        )

    # --------------------------------------------------------
    # Competing task evidence
    # --------------------------------------------------------

    competing = [
        task
        for task in supporting
        if task != task_name
    ]

    if competing:

        score -= 4

        reasons.append(
            "competing_task_evidence"
        )

    # --------------------------------------------------------
    # Continued activity
    # --------------------------------------------------------

    activity_count = count_activity_after(
        events,
        index,
        completion_index
    )

    if activity_count >= 8:

        score += 5

        reasons.append(
            "dense_activity"
        )

    elif activity_count >= 5:

        score += 3

        reasons.append(
            "continued_activity"
        )

    elif activity_count >= MIN_DENSE_ACTIVITY:

        score += 1

        reasons.append(
            "some_activity"
        )

    else:

        score -= 5

        reasons.append(
            "isolated_candidate"
        )

    return (
        score,
        reasons,
        activity_count
    )


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
    Recover a credible beginning of the business interaction.

    V8 differs from V7:

        V7:
            latest strong candidate

        V8:
            earliest credible candidate inside the
            continuous activity block.

    The completion anchor itself remains unchanged.
    """

    completion_ts = events[
        completion_index
    ]["_ts"]

    earliest_allowed_ts = (
        completion_ts
        - START_LOOKBACK_SECONDS * 1000
    )

    candidates = []

    # --------------------------------------------------------
    # Scan FORWARD.
    #
    # We deliberately scan from the beginning of the
    # lookback window toward the completion.
    #
    # This prevents the latest event from automatically
    # becoming the start.
    # --------------------------------------------------------

    for i in range(
        minimum_index,
        completion_index
    ):

        event_ts = events[
            i
        ]["_ts"]

        if event_ts < earliest_allowed_ts:
            continue

        if not is_activity_event(
            events[i]
        ):
            continue

        score, reasons, activity_count = (
            candidate_start_score(
                events,
                i,
                completion_index,
                task_name
            )
        )

        # ----------------------------------------------------
        # Require real activity after candidate.
        # ----------------------------------------------------

        if activity_count < MIN_ACTIVITY_AFTER:
            continue

        # ----------------------------------------------------
        # Require reasonable candidate evidence.
        # ----------------------------------------------------

        if score < 3:
            continue

        candidates.append(
            {
                "index": i,
                "score": score,
                "reasons": reasons,
                "activity_count": activity_count,
            }
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    if not candidates:

        for i in range(
            minimum_index,
            completion_index
        ):

            if events[i]["_ts"] < earliest_allowed_ts:
                continue

            if is_activity_event(
                events[i]
            ):

                return (
                    i,
                    "fallback_activity",
                    ["fallback_activity"],
                    "low"
                )

        return (
            completion_index,
            "completion_fallback",
            ["completion_fallback"],
            "low"
        )

    # --------------------------------------------------------
    # IMPORTANT V8 DECISION
    #
    # Select the EARLIEST credible candidate.
    #
    # Do NOT select:
    #
    #     max(candidates, key=score)
    #
    # because that again tends to move the start toward the
    # completion event.
    # --------------------------------------------------------

    selected = candidates[0]

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    if (
        selected["score"] >= 8
        and selected["activity_count"] >= 5
    ):

        confidence = "high"

    else:

        confidence = "medium"

    return (
        selected["index"],
        "activity_block_boundary",
        selected["reasons"],
        confidence
    )


# ============================================================
# FIND SEGMENT END
# ============================================================

def find_end(
    events,
    completion_index
):
    """
    Include a small amount of context after completion
    without consuming the next execution.
    """

    completion_ts = events[
        completion_index
    ]["_ts"]

    end_index = completion_index

    for i in range(
        completion_index + 1,
        len(events)
    ):

        current_ts = events[
            i
        ]["_ts"]

        if (
            current_ts
            - completion_ts
            > 2000
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
    segment_number,
    start_detection_method,
    start_reasons,
    start_confidence
):
    """
    Build final segment representation.
    """

    segment_events = events[
        start_index:
        end_index + 1
    ]

    start_ts = segment_events[
        0
    ]["_ts"]

    end_ts = segment_events[
        -1
    ]["_ts"]

    # --------------------------------------------------------
    # Maximum duration safety check
    # --------------------------------------------------------

    duration_seconds = (
        end_ts - start_ts
    ) / 1000.0

    # --------------------------------------------------------
    # Applications
    # --------------------------------------------------------

    apps = []

    # --------------------------------------------------------
    # Supporting tasks
    # --------------------------------------------------------

    supporting_tasks = set()

    # --------------------------------------------------------
    # Event counts
    # --------------------------------------------------------

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

        for task in detect_supporting_tasks(
            event
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

    # --------------------------------------------------------
    # Business area
    # --------------------------------------------------------

    area = TASK_TO_AREA.get(
        task_name,
        "Other"
    )

    # --------------------------------------------------------
    # Completion evidence
    # --------------------------------------------------------

    completion_text = get_event_text(
        events[
            completion_index
        ]
    )

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

        # ----------------------------------------------------
        # V8 start-detection metadata
        # ----------------------------------------------------

        "start_detection_method": (
            start_detection_method
        ),

        "start_reasons": (
            start_reasons
        ),

        "start_confidence": (
            start_confidence
        ),
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

        (
            start_index,
            start_detection_method,
            start_reasons,
            start_confidence
        ) = find_start(
            events,
            i,
            task_name,
            minimum_index=used_until + 1
        )

        # ----------------------------------------------------
        # Recover ending context.
        # ----------------------------------------------------

        end_index = find_end(
            events,
            i
        )

        # ----------------------------------------------------
        # Prevent overlap.
        # ----------------------------------------------------

        if start_index <= used_until:
            continue

        # ----------------------------------------------------
        # Maximum segment duration.
        #
        # If the proposed start is extremely far from the
        # completion, move it forward to the first activity
        # inside the allowed duration.
        # ----------------------------------------------------

        proposed_duration = (
            events[end_index]["_ts"]
            - events[start_index]["_ts"]
        ) / 1000.0

        if proposed_duration > MAX_SEGMENT_SECONDS:

            minimum_start_ts = (
                events[end_index]["_ts"]
                - MAX_SEGMENT_SECONDS * 1000
            )

            adjusted_start = None

            for j in range(
                start_index,
                i + 1
            ):

                if (
                    events[j]["_ts"]
                    >= minimum_start_ts
                    and is_activity_event(
                        events[j]
                    )
                ):

                    adjusted_start = j
                    break

            if adjusted_start is not None:

                start_index = adjusted_start

                start_detection_method = (
                    start_detection_method
                    + "_max_duration_adjusted"
                )

                start_reasons = (
                    start_reasons
                    + ["max_duration_adjustment"]
                )

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
            start_detection_method=(
                start_detection_method
            ),
            start_reasons=start_reasons,
            start_confidence=start_confidence,
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

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    chunks = load_chunks()

    print("=" * 70)
    print(
        "DATASET B V8 — RAW TASK-START SEGMENTATION"
    )
    print("=" * 70)

    print(
        f"Chunks loaded: {len(chunks)}"
    )

    all_segments = []

    for chunk in chunks:

        all_segments.extend(
            segment_chunk(
                chunk
            )
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
    # Empty result
    # --------------------------------------------------------

    if not all_segments:

        print(
            "WARNING: No segments were detected."
        )

        return

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    durations = [
        s["duration_seconds"]
        for s in all_segments
    ]

    event_counts = [
        s["event_count"]
        for s in all_segments
    ]

    area_counts = {}

    task_counts = {}

    method_counts = {}

    confidence_counts = {}

    for segment in all_segments:

        area = segment[
            "business_area"
        ]

        area_counts[
            area
        ] = (
            area_counts.get(
                area,
                0
            ) + 1
        )

        task = segment[
            "task"
        ]

        task_counts[
            task
        ] = (
            task_counts.get(
                task,
                0
            ) + 1
        )

        method = segment[
            "start_detection_method"
        ]

        method_counts[
            method
        ] = (
            method_counts.get(
                method,
                0
            ) + 1
        )

        confidence = segment[
            "start_confidence"
        ]

        confidence_counts[
            confidence
        ] = (
            confidence_counts.get(
                confidence,
                0
            ) + 1
        )

    # --------------------------------------------------------
    # Duration buckets
    # --------------------------------------------------------

    buckets = {
        "<1s": 0,
        "1-2s": 0,
        "2-5s": 0,
        "5-10s": 0,
        "10-30s": 0,
        "30-60s": 0,
        "60-120s": 0,
        ">120s": 0,
    }

    for duration in durations:

        if duration < 1:
            buckets["<1s"] += 1

        elif duration < 2:
            buckets["1-2s"] += 1

        elif duration < 5:
            buckets["2-5s"] += 1

        elif duration < 10:
            buckets["5-10s"] += 1

        elif duration < 30:
            buckets["10-30s"] += 1

        elif duration < 60:
            buckets["30-60s"] += 1

        elif duration <= 120:
            buckets["60-120s"] += 1

        else:
            buckets[">120s"] += 1

    # --------------------------------------------------------
    # Output summary
    # --------------------------------------------------------

    print()
    print(
        f"Segments: {len(all_segments)}"
    )

    print(
        "Duration (s) — "
        f"avg: {sum(durations) / len(durations):.2f}, "
        f"min: {min(durations):.2f}, "
        f"max: {max(durations):.2f}"
    )

    print(
        "Avg events/segment: "
        f"{sum(event_counts) / len(event_counts):.1f}"
    )

    print()
    print("=" * 70)
    print("BUSINESS AREAS")
    print("=" * 70)

    for area, count in sorted(
        area_counts.items(),
        key=lambda x: -x[1]
    ):

        print(
            f"  {area}: {count}"
        )

    print()
    print("=" * 70)
    print("TASKS")
    print("=" * 70)

    for task, count in sorted(
        task_counts.items(),
        key=lambda x: -x[1]
    ):

        print(
            f"  {task}: {count}"
        )

    print()
    print("=" * 70)
    print("DURATION BUCKETS")
    print("=" * 70)

    for bucket, count in buckets.items():

        print(
            f"  {bucket:<10}: {count}"
        )

    print()
    print("=" * 70)
    print("START DETECTION METHODS")
    print("=" * 70)

    for method, count in sorted(
        method_counts.items(),
        key=lambda x: -x[1]
    ):

        print(
            f"  {method}: {count}"
        )

    print()
    print("=" * 70)
    print("START CONFIDENCE")
    print("=" * 70)

    for confidence, count in sorted(
        confidence_counts.items(),
        key=lambda x: -x[1]
    ):

        print(
            f"  {confidence}: {count}"
        )

    print()
    print(
        f"Output written to: {OUTPUT_FILE}"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()