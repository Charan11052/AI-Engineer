import json
import re
from pathlib import Path
from collections import Counter, defaultdict


BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_B_DIR = BASE_DIR / "dataset_b"
SEGMENTS_FILE = BASE_DIR / "outputs" / "dataset_b_segments_v6.jsonl"


TASK_PATTERNS = {
    "FINANCE_BUDGET": [
        r"予算差異分析完了",
    ],
    "FINANCE_INVOICE": [
        r"請求書照合完了",
    ],
    "FINANCE_PAYMENT": [
        r"支払処理確認.*完了",
        r"支払処理.*完了",
    ],
    "HR_ATTENDANCE": [
        r"勤怠申請確認.*(?:承認|完了)",
    ],
    "HR_ONBOARDING": [
        r"入社照合完了",
    ],
    "HR_PAYROLL": [
        r"給与変更登録.*確認完了",
    ],
    "LOGISTICS_INVENTORY": [
        r"在庫調整登録.*(?:個|完了)",
    ],
    "LOGISTICS_ORDER": [
        r"発注書確認・登録完了",
        r"発注管理処理.*完了",
    ],
}


def detect_completion(text):
    matches = []

    for task, patterns in TASK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text):
                matches.append(task)
                break

    if len(matches) == 1:
        return matches[0]

    return None


def get_extracted_text(event):
    context = event.get("context", {})
    extracted = context.get("extracted_text", {})

    if isinstance(extracted, dict):
        return str(extracted.get("text", "") or "")

    return ""


def load_raw_completion_events():
    results = []

    event_files = sorted(DATASET_B_DIR.rglob("events.jsonl"))

    for event_file in event_files:

        # Identify session/chunk from path
        parts = event_file.parts

        session = None
        chunk = None

        for part in parts:
            if part.startswith("ses_"):
                session = part
            elif re.fullmatch(r"\d+", part):
                chunk = part

        if session is None:
            session = event_file.parent.parent.name

        if chunk is None:
            chunk = event_file.parent.name

        with open(event_file, "r", encoding="utf-8") as f:

            for raw_index, line in enumerate(f):

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                text = get_extracted_text(event)

                if not text:
                    continue

                task = detect_completion(text)

                if task is None:
                    continue

                timestamp_ms = event.get("timestamp_ms")

                if timestamp_ms is None:
                    continue

                results.append({
                    "session": str(session),
                    "chunk": str(chunk),
                    "raw_index": raw_index,
                    "timestamp_ms": int(timestamp_ms),
                    "task": task,
                    "text": text,
                })

    return results


def load_segments():

    segments = []

    with open(SEGMENTS_FILE, "r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            seg = json.loads(line)
            segments.append(seg)

    return segments


def main():

    print("=" * 70)
    print("DATASET B V5 COMPLETION COVERAGE CHECK - TIMESTAMP VERSION")
    print("=" * 70)

    raw = load_raw_completion_events()
    segments = load_segments()

    print()
    print(f"Raw completion events : {len(raw)}")
    print(f"V5 segments           : {len(segments)}")

    # ------------------------------------------------------------
    # Match raw completion events against V5 segment intervals
    # ------------------------------------------------------------

    matched = []
    unmatched = []

    # Group segments by session + chunk + task
    segment_groups = defaultdict(list)

    for seg in segments:

        key = (
            str(seg.get("session")),
            str(seg.get("chunk")),
            seg.get("task"),
        )

        segment_groups[key].append(seg)

    for key in segment_groups:
        segment_groups[key].sort(
            key=lambda x: x.get("start_timestamp_ms", 0)
        )

    for completion in raw:

        key = (
            completion["session"],
            completion["chunk"],
            completion["task"],
        )

        candidates = segment_groups.get(key, [])

        found = None

        for seg in candidates:

            start = seg.get("start_timestamp_ms")
            end = seg.get("end_timestamp_ms")

            if start is None or end is None:
                continue

            ts = completion["timestamp_ms"]

            # Completion event falls inside segment interval
            if start <= ts <= end:

                found = seg
                break

        if found is not None:

            matched.append({
                "completion": completion,
                "segment": found,
            })

        else:
            unmatched.append(completion)

    # ------------------------------------------------------------
    # Overall coverage
    # ------------------------------------------------------------

    print()
    print("OVERALL COVERAGE")
    print("-" * 70)

    print(f"Raw completion events : {len(raw)}")
    print(f"V5 completion anchors : {len(segments)}")
    print(f"Matched              : {len(matched)}")
    print(f"Unmatched            : {len(unmatched)}")

    coverage = (
        len(matched) / len(raw) * 100
        if raw
        else 0
    )

    print(f"Coverage             : {coverage:.2f}%")

    # ------------------------------------------------------------
    # Coverage by task
    # ------------------------------------------------------------

    print()
    print("COVERAGE BY TASK")
    print("-" * 70)

    raw_counts = Counter(x["task"] for x in raw)
    matched_counts = Counter(
        x["completion"]["task"]
        for x in matched
    )

    for task in sorted(raw_counts):

        r = raw_counts[task]
        m = matched_counts[task]

        pct = m / r * 100 if r else 0

        print(
            f"{task:<25} "
            f"raw={r:3d} "
            f"matched={m:3d} "
            f"coverage={pct:6.2f}%"
        )

    # ------------------------------------------------------------
    # Unmatched details
    # ------------------------------------------------------------

    print()
    print("UNMATCHED COMPLETIONS")
    print("-" * 70)

    for i, item in enumerate(unmatched, 1):

        print()
        print(f"[{i}]")
        print(f"Session    : {item['session']}")
        print(f"Chunk      : {item['chunk']}")
        print(f"Raw index  : {item['raw_index']}")
        print(f"Timestamp  : {item['timestamp_ms']}")
        print(f"Task       : {item['task']}")
        print(f"Text       : {item['text'][:300]}")

    # ------------------------------------------------------------
    # Sanity check
    # ------------------------------------------------------------

    print()
    print("SANITY CHECK")
    print("-" * 70)

    # Check that matched completion timestamps actually fall
    # inside the corresponding segment.
    bad_matches = []

    for item in matched:

        completion = item["completion"]
        seg = item["segment"]

        ts = completion["timestamp_ms"]
        start = seg["start_timestamp_ms"]
        end = seg["end_timestamp_ms"]

        if not (start <= ts <= end):
            bad_matches.append(item)

    print(f"Matched records with invalid timestamp range : {len(bad_matches)}")

    if len(bad_matches) == 0:
        print("PASS")
    else:
        print("FAIL")

    print()
    print("=" * 70)
    print("END")
    print("=" * 70)


if __name__ == "__main__":
    main()