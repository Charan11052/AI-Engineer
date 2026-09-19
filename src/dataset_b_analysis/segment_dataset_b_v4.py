import json
import re
from pathlib import Path
from collections import Counter


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
DATASET_B = ROOT / "dataset_b"
OUTPUT = ROOT / "outputs" / "dataset_b_segments_v4.jsonl"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# BUSINESS TASK DEFINITIONS
#
# IMPORTANT:
# These are deliberately based on strong completion/action
# phrases, NOT generic dashboard words.
# ============================================================

TASK_PATTERNS = {
    "HR_ONBOARDING": [
        r"入社照合完了",
        r"照合項目すべて確認済み",
        r"入社チェック.*完了",
        r"入社手続き.*完了",
    ],

    "HR_PAYROLL_CHANGE": [
        r"給与変更登録",
        r"給与変更.*確認完了",
        r"給与変更.*完了",
    ],

    "HR_ATTENDANCE": [
        r"勤怠申請確認",
        r"有給.*問題なし承認",
        r"休暇.*問題なし承認",
        r"勤怠.*承認",
    ],

    "HR_BENEFITS": [
        r"福利厚生申請処理完了",
        r"育児休業申請",
        r"家族手当.*変更",
        r"福利厚生.*完了",
    ],

    "FINANCE_EXPENSE": [
        r"経費精算確認済み",
        r"経費承認（管理職）",
        r"経費精算.*確認",
    ],

    "FINANCE_PAYMENT": [
        r"支払処理確認",
        r"支払実行確認",
        r"振込実行.*完了",
        r"支払.*完了",
    ],

    "FINANCE_INVOICE": [
        r"請求書照合完了",
        r"請求書.*差異なし承認",
        r"請求書.*承認",
    ],

    "FINANCE_BUDGET": [
        r"予算差異分析",
        r"予算分析.*完了",
        r"予算.*確認完了",
    ],

    "LOGISTICS_INVENTORY": [
        r"在庫調整登録",
        r"在庫調整.*完了",
        r"在庫.*登録完了",
    ],

    "LOGISTICS_ORDER": [
        r"発注管理処理",
        r"発注書確認・登録完了",
        r"発注書.*登録完了",
    ],

    "LOGISTICS_CONTRACT": [
        r"契約処理記録",
        r"契約.*登録完了",
        r"契約.*処理完了",
        r"新規契約.*完了",
        r"契約締結.*完了",
    ],

    "LOGISTICS_SUPPLIER": [
        r"新規取引先登録",
        r"取引先登録.*完了",
        r"新規取引先.*登録完了",
    ],
}


# ============================================================
# TASK -> AREA
# ============================================================

TASK_AREA = {
    "HR_ONBOARDING": "HR",
    "HR_PAYROLL_CHANGE": "HR",
    "HR_ATTENDANCE": "HR",
    "HR_BENEFITS": "HR",

    "FINANCE_EXPENSE": "FINANCE",
    "FINANCE_PAYMENT": "FINANCE",
    "FINANCE_INVOICE": "FINANCE",
    "FINANCE_BUDGET": "FINANCE",

    "LOGISTICS_INVENTORY": "LOGISTICS",
    "LOGISTICS_ORDER": "LOGISTICS",
    "LOGISTICS_CONTRACT": "LOGISTICS",
    "LOGISTICS_SUPPLIER": "LOGISTICS",
}


# ============================================================
# DOCUMENT -> TASK SUPPORT
# Documents are supporting evidence only.
# They should NOT independently create a boundary.
# ============================================================

DOCUMENT_TASK = {
    "nyusha_checklist_shinsotsu_batch": "HR_ONBOARDING",
    "gyomu_itaku_ukeire_tetsuzuki": "HR_ONBOARDING",

    "expense_calc": "FINANCE_EXPENSE",
    "settai_keihi_kitei": "FINANCE_EXPENSE",
    "gyomu_itaku_keihi_kitei": "FINANCE_EXPENSE",

    "getsujitsu_teigaku_torihikisaki_ichiran": "FINANCE_INVOICE",

    "budget_analysis": "FINANCE_BUDGET",

    "gyomu_itaku_kyuuyo_kitei": "FINANCE_PAYMENT",

    "keiyaku_kaijo_tetsuzuki": "LOGISTICS_CONTRACT",
    "shinkui_keiyaku_tetsuzuki": "LOGISTICS_CONTRACT",

    "shinkuitorihikisaki_touroku_tetsuzuki": "LOGISTICS_SUPPLIER",

    "在庫調整メモ": "LOGISTICS_INVENTORY",
    "精算確認メモ": "FINANCE_EXPENSE",
}


# ============================================================
# HELPERS
# ============================================================

def parse_ts(event):
    return int(event.get("timestamp_ms", 0))


def get_text(event):
    """
    Extract OCR / extracted text from the event.
    """

    context = event.get("context") or {}

    extracted = context.get("extracted_text")

    if isinstance(extracted, dict):
        text = extracted.get("text")
        if text:
            return str(text)

    elif isinstance(extracted, str):
        return extracted

    # Some events can contain useful payload text
    payload = event.get("payload") or {}

    if isinstance(payload, dict):
        for key in ("text", "value", "content"):
            value = payload.get(key)
            if isinstance(value, str):
                return value

    return ""


def get_app(event):
    context = event.get("context") or {}
    active_app = context.get("active_app")

    if isinstance(active_app, dict):
        return (
            active_app.get("app_name")
            or active_app.get("process_name")
            or "UNKNOWN"
        )

    if isinstance(active_app, str):
        return active_app

    return "UNKNOWN"


def get_title(event):
    context = event.get("context") or {}
    active_app = context.get("active_app")

    if isinstance(active_app, dict):
        return active_app.get("window_title") or ""

    return ""


def normalize_text(text):
    if not text:
        return ""

    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# TASK DETECTION
# ============================================================

def detect_tasks(text):
    """
    Return strong task matches found in text.

    Multiple tasks can occur in one event because screenshots
    sometimes capture dashboards containing several sections.
    """

    text = normalize_text(text)

    if not text:
        return []

    matches = []

    for task, patterns in TASK_PATTERNS.items():

        for pattern in patterns:

            if re.search(pattern, text):

                matches.append(task)
                break

    return matches


# ============================================================
# DOCUMENT DETECTION
# ============================================================

def detect_documents(title, text):
    """
    Detect known process documents.
    """

    combined = f"{title} {text}".lower()

    docs = []

    for doc in DOCUMENT_TASK:

        if doc.lower() in combined:
            docs.append(doc)

    return docs


# ============================================================
# EVENT ENRICHMENT
# ============================================================

def enrich_event(event):

    text = get_text(event)
    title = get_title(event)
    app = get_app(event)

    tasks = detect_tasks(text)
    documents = detect_documents(title, text)

    return {
        "event": event,
        "ts": parse_ts(event),
        "text": text,
        "title": title,
        "app": app,
        "tasks": tasks,
        "documents": documents,
    }


# ============================================================
# STRONG COMPLETION DETECTION
# ============================================================

def is_completion_event(info):

    text = info["text"]

    if not text:
        return False

    completion_words = [
        "完了",
        "確認済み",
        "確認完了",
        "登録完了",
        "処理完了",
        "照合完了",
        "承認",
    ]

    return any(word in text for word in completion_words)


# ============================================================
# TASK SCORE
# ============================================================

def task_scores(events):

    scores = Counter()

    for e in events:

        # Explicit task evidence is strongest
        for task in e["tasks"]:
            scores[task] += 10

        # Documents are supporting evidence
        for doc in e["documents"]:

            task = DOCUMENT_TASK.get(doc)

            if task:
                scores[task] += 2

    return scores


# ============================================================
# CHOOSE DOMINANT TASK
# ============================================================

def choose_task(events):

    scores = task_scores(events)

    if not scores:
        return None, 0, scores

    task, score = scores.most_common(1)[0]

    return task, score, scores


# ============================================================
# FIND COMPLETION TASK
# ============================================================

def completion_task(info):

    tasks = info["tasks"]

    if not tasks:
        return None

    # Prefer tasks that occur together with completion language
    text = info["text"]

    if is_completion_event(info):

        # Specific explicit task first
        if tasks:
            return tasks[0]

    return tasks[0]


# ============================================================
# LOAD CHUNKS
# ============================================================

def load_chunks():

    chunks = []

    for path in DATASET_B.rglob("events.jsonl"):

        # Keep session/chunk identity
        events = []

        with path.open("r", encoding="utf-8") as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                    events.append(event)

                except json.JSONDecodeError:
                    continue

        if not events:
            continue

        chunks.append({
            "path": path,
            "events": events,
        })

    chunks.sort(
        key=lambda x: parse_ts(x["events"][0])
    )

    return chunks


# ============================================================
# SEGMENT CREATION
# ============================================================

def create_segment(
    session_name,
    chunk_name,
    segment_number,
    events,
    completion_info=None
):

    if not events:
        return None

    start_ts = events[0]["ts"]
    end_ts = events[-1]["ts"]

    duration = max(
        0,
        (end_ts - start_ts) / 1000
    )

    task, score, all_scores = choose_task(events)

    # If we have an actual completion event, prefer its task.
    if completion_info:

        completion_task_name = completion_task(completion_info)

        if completion_task_name:
            task = completion_task_name

    area = TASK_AREA.get(task)

    if area is None:

        area_scores = Counter()

        for e in events:

            for t in e["tasks"]:
                a = TASK_AREA.get(t)

                if a:
                    area_scores[a] += 1

            for doc in e["documents"]:
                t = DOCUMENT_TASK.get(doc)

                if t:
                    a = TASK_AREA.get(t)

                    if a:
                        area_scores[a] += 0.25

        if area_scores:
            area = area_scores.most_common(1)[0][0]

    if area is None:
        area = "OTHER"

    # --------------------------------------------------------
    # Counts
    # --------------------------------------------------------

    apps = Counter(e["app"] for e in events)

    documents = Counter()

    explicit_tasks = Counter()

    for e in events:

        for doc in e["documents"]:
            documents[doc] += 1

        for t in e["tasks"]:
            explicit_tasks[t] += 1

    # --------------------------------------------------------
    # Completion
    # --------------------------------------------------------

    completion_text = ""

    if completion_info:
        completion_text = normalize_text(
            completion_info["text"]
        )[:500]

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    if completion_info and completion_task(completion_info):
        confidence = "high"

    elif score >= 10:
        confidence = "medium"

    elif documents:
        confidence = "low"

    else:
        confidence = "low"

    return {
        "id": (
            f"{session_name}_{chunk_name}"
            f"_SEG_{segment_number:03d}"
        ),

        "session": session_name,
        "chunk": chunk_name,

        "start_ts": start_ts,
        "end_ts": end_ts,

        "duration_seconds": round(duration, 2),

        "event_count": len(events),

        "area": area,

        "task": task,

        "confidence": confidence,

        "completion_evidence": completion_text,

        "completion_timestamp_ms": (
            completion_info["ts"]
            if completion_info
            else None
        ),

        "apps": dict(apps),

        "documents": dict(documents),

        "explicit_task_evidence": dict(explicit_tasks),

        "task_scores": dict(all_scores),

        "start_event_index": events[0]["index"],
        "end_event_index": events[-1]["index"],
    }


# ============================================================
# SEGMENT ONE CHUNK
# ============================================================

def segment_chunk(chunk):

    raw_events = chunk["events"]

    enriched = []

    for index, event in enumerate(raw_events):

        info = enrich_event(event)

        info["index"] = index

        enriched.append(info)

    if not enriched:
        return []

    segments = []

    current = []

    segment_number = 1

    last_completion_ts = None

    # --------------------------------------------------------
    # Parameters
    # --------------------------------------------------------

    MAX_CONTEXT_SECONDS = 45

    # Events after a completion can belong to the next task.
    PRE_COMPLETION_LOOKBACK = 35

    # --------------------------------------------------------
    # Main loop
    # --------------------------------------------------------

    for info in enriched:

        current.append(info)

        # ----------------------------------------------------
        # Strong completion detected
        # ----------------------------------------------------

        completion = None

        if is_completion_event(info):

            detected = completion_task(info)

            if detected:
                completion = info

        if completion:

            # ------------------------------------------------
            # Determine whether this completion belongs to the
            # current dominant task.
            # ------------------------------------------------

            current_task, current_score, _ = choose_task(current)

            completion_name = completion_task(completion)

            # ------------------------------------------------
            # Normal case:
            # completion closes current business unit.
            # ------------------------------------------------

            if completion_name:

                seg = create_segment(
                    chunk["path"].parent.name,
                    chunk["path"].stem,
                    segment_number,
                    current,
                    completion
                )

                if seg:

                    segments.append(seg)
                    segment_number += 1

                current = []

                last_completion_ts = completion["ts"]

    # --------------------------------------------------------
    # Remaining events
    # --------------------------------------------------------

    if current:

        # Only keep meaningful trailing context.
        task, score, _ = choose_task(current)

        has_documents = any(
            e["documents"]
            for e in current
        )

        has_business_tasks = any(
            e["tasks"]
            for e in current
        )

        # Avoid emitting pure UI/dashboard noise.
        if (
            has_business_tasks
            or has_documents
            or score >= 5
        ):

            seg = create_segment(
                chunk["path"].parent.name,
                chunk["path"].stem,
                segment_number,
                current,
                None
            )

            if seg:
                segments.append(seg)

    return segments


# ============================================================
# POST-PROCESSING
# ============================================================

def merge_tiny_segments(segments):

    """
    Tiny segments can happen when a completion screenshot is
    separated from the surrounding interaction.

    We merge ONLY when:
      - same task
      - same session/chunk
      - temporal distance is small
    """

    if not segments:
        return []

    result = []

    for seg in segments:

        if not result:

            result.append(seg)
            continue

        prev = result[-1]

        gap = (
            seg["start_ts"] - prev["end_ts"]
        ) / 1000

        same_task = (
            seg["task"] is not None
            and seg["task"] == prev["task"]
        )

        same_chunk = (
            seg["session"] == prev["session"]
            and seg["chunk"] == prev["chunk"]
        )

        if (
            same_task
            and same_chunk
            and gap <= 3
            and (
                seg["duration_seconds"] < 5
                or prev["duration_seconds"] < 5
            )
        ):

            prev["end_ts"] = seg["end_ts"]

            prev["duration_seconds"] = round(
                (
                    prev["end_ts"]
                    - prev["start_ts"]
                ) / 1000,
                2
            )

            prev["event_count"] += seg["event_count"]

            for key in [
                "apps",
                "documents",
                "explicit_task_evidence",
                "task_scores",
            ]:

                for k, v in seg[key].items():
                    prev[key][k] = (
                        prev[key].get(k, 0) + v
                    )

            if seg.get("completion_evidence"):
                prev["completion_evidence"] = (
                    seg["completion_evidence"]
                )

            continue

        result.append(seg)

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("DATASET B - V4 COMPLETION-DRIVEN SEGMENTATION")
    print("=" * 70)

    chunks = load_chunks()

    print(f"Chunks: {len(chunks)}")

    all_segments = []

    total_events = 0

    for chunk in chunks:

        events = chunk["events"]

        total_events += len(events)

        segments = segment_chunk(chunk)

        all_segments.extend(segments)

    print(f"Raw events: {total_events}")
    print(f"Initial segments: {len(all_segments)}")

    # Sort globally
    all_segments.sort(
        key=lambda x: (
            x["start_ts"],
            x["session"],
            x["chunk"]
        )
    )

    all_segments = merge_tiny_segments(
        all_segments
    )

    # Re-number IDs after merging
    for i, seg in enumerate(all_segments, 1):

        seg["global_segment_number"] = i

        seg["id"] = (
            f"{seg['session']}_"
            f"{seg['chunk']}_"
            f"SEG_{i:03d}"
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    with OUTPUT.open(
        "w",
        encoding="utf-8"
    ) as f:

        for seg in all_segments:

            f.write(
                json.dumps(
                    seg,
                    ensure_ascii=False
                )
                + "\n"
            )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    durations = [
        s["duration_seconds"]
        for s in all_segments
    ]

    tasks = Counter(
        s["task"]
        for s in all_segments
    )

    areas = Counter(
        s["area"]
        for s in all_segments
    )

    confidence = Counter(
        s["confidence"]
        for s in all_segments
    )

    tiny = sum(
        d < 10
        for d in durations
    )

    long = sum(
        d > 180
        for d in durations
    )

    print()
    print("=" * 70)
    print("V4 RESULTS")
    print("=" * 70)

    print(f"Segments: {len(all_segments)}")

    if durations:

        print(
            f"Average duration: "
            f"{sum(durations) / len(durations):.1f}s"
        )

        print(
            f"Minimum duration: "
            f"{min(durations):.1f}s"
        )

        print(
            f"Maximum duration: "
            f"{max(durations):.1f}s"
        )

    print(f"Segments <10s: {tiny}")
    print(f"Segments >180s: {long}")

    print()
    print("AREAS")

    for k, v in areas.most_common():
        print(f"  {k}: {v}")

    print()
    print("TASKS")

    for k, v in tasks.most_common():
        print(f"  {k}: {v}")

    print()
    print("CONFIDENCE")

    for k, v in confidence.most_common():
        print(f"  {k}: {v}")

    print()
    print(f"Output: {OUTPUT}")

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()