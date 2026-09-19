import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_B_DIR = BASE_DIR / "dataset_b"
SEGMENTS_FILE = (
    BASE_DIR
    / "outputs"
    / "dataset_b_segments_v5.jsonl"
)


COMPLETION_PATTERNS = {
    "FINANCE_INVOICE": [
        r"請求書照合完了",
    ],

    "FINANCE_PAYMENT": [
        r"支払処理確認.*完了",
    ],

    "FINANCE_BUDGET": [
        r"予算差異分析完了",
    ],

    "HR_ATTENDANCE": [
        r"勤怠申請確認.*問題なし承認",
    ],

    "HR_ONBOARDING": [
        r"入社照合完了",
    ],

    "HR_PAYROLL": [
        r"給与変更登録.*確認完了",
    ],

    "LOGISTICS_INVENTORY": [
        r"在庫調整登録.*調整数",
    ],

    "LOGISTICS_ORDER": [
        r"発注管理処理.*発注書確認・登録完了",
    ],
}


def extract_text(event):

    context = event.get("context", {})
    extracted = context.get("extracted_text")

    if isinstance(extracted, dict):
        return str(
            extracted.get("text") or ""
        )

    if isinstance(extracted, str):
        return extracted

    return ""


def detect_completion(text):

    matches = []

    for task, patterns in COMPLETION_PATTERNS.items():

        for pattern in patterns:

            if re.search(
                pattern,
                text,
                re.IGNORECASE
            ):
                matches.append(task)

    return matches


def load_raw_events():

    chunks = {}

    for path in sorted(
        DATASET_B_DIR.rglob("events.jsonl")
    ):

        session = None

        for parent in path.parents:

            if parent.name.startswith("ses_"):
                session = parent.name
                break

        chunk = path.parent.name

        key = (session, chunk)

        events = []

        with path.open(
            "r",
            encoding="utf-8"
        ) as f:

            for index, line in enumerate(f):

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                except Exception:
                    continue

                events.append(event)

        chunks[key] = events

    return chunks


def load_segments():

    segments = []

    with SEGMENTS_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if line:
                segments.append(
                    json.loads(line)
                )

    return segments


def find_unmatched(chunks, segments):

    unmatched = []

    for (session, chunk), events in chunks.items():

        for index, event in enumerate(events):

            text = extract_text(event)

            tasks = detect_completion(text)

            for task in tasks:

                captured = False

                for segment in segments:

                    if segment.get("session") != session:
                        continue

                    if segment.get("chunk") != chunk:
                        continue

                    if segment.get("task") != task:
                        continue

                    start = segment.get(
                        "start_event_index"
                    )

                    end = segment.get(
                        "end_event_index"
                    )

                    if (
                        start is not None
                        and end is not None
                        and start <= index <= end
                    ):
                        captured = True
                        break

                if not captured:

                    unmatched.append(
                        {
                            "task": task,
                            "session": session,
                            "chunk": chunk,
                            "index": index,
                            "event": event,
                        }
                    )

    return unmatched


def print_event(index, event):

    timestamp = event.get(
        "timestamp_ms"
    )

    event_type = event.get(
        "event_type"
    )

    text = extract_text(event)

    context = event.get(
        "context",
        {}
    )

    active_app = context.get(
        "active_app",
        {}
    )

    if isinstance(active_app, dict):
        app = (
            active_app.get("app_name")
            or active_app.get("process_name")
            or ""
        )

        title = active_app.get(
            "window_title",
            ""
        )
    else:
        app = ""
        title = ""

    print(
        f"[{index:4d}] "
        f"{timestamp} | "
        f"{event_type:22s} | "
        f"{app}"
    )

    if title:
        print(
            f"       TITLE: {title[:180]}"
        )

    if text:
        print(
            f"       TEXT : {text[:400]}"
        )


def main():

    print("=" * 70)
    print("INSPECT UNMATCHED V5 COMPLETIONS")
    print("=" * 70)

    chunks = load_raw_events()
    segments = load_segments()

    unmatched = find_unmatched(
        chunks,
        segments
    )

    print(
        f"\nUnmatched completions: "
        f"{len(unmatched)}"
    )

    for number, item in enumerate(
        unmatched,
        start=1
    ):

        session = item["session"]
        chunk = item["chunk"]
        index = item["index"]
        task = item["task"]

        events = chunks[
            (session, chunk)
        ]

        print("\n")
        print("=" * 70)

        print(
            f"UNMATCHED #{number}"
        )

        print(
            f"Task       : {task}"
        )

        print(
            f"Session    : {session}"
        )

        print(
            f"Chunk      : {chunk}"
        )

        print(
            f"Event index: {index}"
        )

        print("-" * 70)
        print("RAW EVENTS AROUND COMPLETION")
        print("-" * 70)

        start = max(
            0,
            index - 8
        )

        end = min(
            len(events),
            index + 9
        )

        for i in range(
            start,
            end
        ):

            print_event(
                i,
                events[i]
            )

        print("-" * 70)
        print("V5 SEGMENTS IN SAME CHUNK")
        print("-" * 70)

        found_segment = False

        for segment in segments:

            if (
                segment.get("session")
                == session
                and
                segment.get("chunk")
                == chunk
            ):

                found_segment = True

                print(
                    f"{segment.get('segment_id')}"
                )

                print(
                    f"  task   = "
                    f"{segment.get('task')}"
                )

                print(
                    f"  range  = "
                    f"{segment.get('start_event_index')}"
                    f" -> "
                    f"{segment.get('end_event_index')}"
                )

                print(
                    f"  time   = "
                    f"{segment.get('duration_seconds')}s"
                )

                print(
                    f"  evidence = "
                    f"{segment.get('completion_evidence', '')[:250]}"
                )

        if not found_segment:
            print(
                "NO V5 SEGMENTS EXIST "
                "IN THIS CHUNK."
            )


if __name__ == "__main__":
    main()
    