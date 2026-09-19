import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATASET_B = ROOT / "dataset_b"
CLASSIFICATION_FILE = ROOT / "outputs" / "unmatched_compact.txt"

# Only the 17 cases classified as likely missing.
TARGETS = [
    ("ses_20260701-164424-CHAITANYA0BCF", 1782924496954),
    ("ses_20260701-171614-CHAITANYA0BCF", 1782926462284),
    ("ses_20260701-173246-SIDDHIGUPTAB00B", 1782927570535),
    ("ses_20260701-173642-NEELA9BAF", 1782927448567),
    ("ses_20260701-175258-LAPTOP-76QMG9DE", 1782928609962),
    ("ses_20260701-175258-LAPTOP-76QMG9DE", 1782928737595),
    ("ses_20260701-175747-SIDDHIGUPTAB00B", 1782928994279),
    ("ses_20260701-175747-SIDDHIGUPTAB00B", 1782929330314),
    ("ses_20260701-180923-NEELA9BAF", 1782929409419),
    ("ses_20260701-181413-LAPTOP-76QMG9DE", 1782929978359),
    ("ses_20260701-181413-LAPTOP-76QMG9DE", 1782930140600),
    ("ses_20260701-181913-SIDDHIGUPTAB00B", 1782930067091),
    ("ses_20260701-181913-SIDDHIGUPTAB00B", 1782930453957),
    ("ses_20260701-183232-LAPTOP-76QMG9DE", 1782931024893),
    ("ses_20260701-184201-LAPTOP-76QMG9DE", 1782932023963),
    ("ses_20260701-190250-NEELA9BAF", 1782932650349),
    ("ses_20260701-191537-LAPTOP-76QMG9DE", 1782933975494),
]

TARGET_MAP = defaultdict(list)
for session, ts in TARGETS:
    TARGET_MAP[session].append(ts)


def get_app(event):
    context = event.get("context") or {}
    active = context.get("active_app") or {}

    if isinstance(active, dict):
        return (
            active.get("app_name")
            or active.get("process_name")
            or "UNKNOWN"
        )

    return "UNKNOWN"


def get_title(event):
    context = event.get("context") or {}
    active = context.get("active_app") or {}

    if isinstance(active, dict):
        return active.get("window_title") or ""

    return ""


def get_text(event):
    parts = []

    context = event.get("context") or {}
    extracted = context.get("extracted_text")

    if isinstance(extracted, dict):
        text = extracted.get("text")
        if text:
            parts.append(str(text))

    title = get_title(event)
    if title:
        parts.append(str(title))

    payload = event.get("payload") or {}

    if isinstance(payload, dict):
        for key in [
            "text",
            "value",
            "input_text",
            "new_app",
            "previous_app",
            "url",
        ]:
            value = payload.get(key)
            if value:
                parts.append(str(value))

    return " | ".join(parts)


def timestamp(event):
    value = event.get("timestamp_ms")

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_events():
    """
    Load all Dataset B events.

    Dataset B has:
        dataset_b/ses_*/chunk_*/events.jsonl
    """

    events_by_session = defaultdict(list)

    files = sorted(DATASET_B.glob("ses_*/chunk_*/events.jsonl"))

    print(f"Found {len(files)} events.jsonl files")

    for path in files:
        # session directory name
        session = path.parent.parent.name

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event["_source_file"] = str(path)
                event["_source_line"] = line_no
                event["_chunk"] = path.parent.name

                ts = timestamp(event)

                if ts is not None:
                    events_by_session[session].append(event)

    for session in events_by_session:
        events_by_session[session].sort(key=timestamp)

    return events_by_session


def classify_event(event):
    event_type = event.get("event_type", "")
    app = get_app(event)
    title = get_title(event)
    text = get_text(event)

    combined = f"{event_type} {app} {title} {text}".lower()

    markers = []

    # Strong completion evidence
    if any(x in text for x in [
        "INV-2026-",
        "在庫調整登録",
        "発注書確認",
        "予算差異分析完了",
        "給与変更登録",
        "入社照合完了",
        "請求書照合完了",
        "勤怠申請確認",
    ]):
        markers.append("TASK_EVIDENCE")

    if event_type in {
        "browser_click",
        "browser_form_input",
        "browser_navigation",
        "mouse_click",
        "keystroke",
        "clipboard_change",
        "shortcut",
        "text_input_complete",
    }:
        markers.append("ACTION")

    if event_type == "screenshot_smart":
        markers.append("SCREENSHOT")

    if event_type == "app_switch":
        markers.append("APP_SWITCH")

    if event_type == "window_title_change":
        markers.append("TITLE_CHANGE")

    return markers


def print_event(event, index, target_ts):
    ts = timestamp(event)
    delta = (ts - target_ts) / 1000 if ts is not None else None

    event_type = event.get("event_type", "")
    app = get_app(event)
    title = get_title(event)
    text = get_text(event)

    if len(text) > 280:
        text = text[:280] + "..."

    print(
        f"{index:5d} | "
        f"{delta:+8.3f}s | "
        f"{event_type:24s} | "
        f"{app:22s} | "
        f"{title[:55]:55s} | "
        f"{text}"
    )


def inspect_target(events, target_ts, number):
    """
    Print a compact window around the target completion.

    We inspect ±20 seconds first.
    """

    print()
    print("=" * 120)
    print(f"TARGET {number}")
    print("=" * 120)

    target_index = min(
        range(len(events)),
        key=lambda i: abs(timestamp(events[i]) - target_ts)
    )

    nearest_ts = timestamp(events[target_index])
    nearest_delta = (nearest_ts - target_ts) / 1000

    print(f"Target timestamp : {target_ts}")
    print(f"Nearest event    : {nearest_ts}")
    print(f"Difference       : {nearest_delta:+.3f}s")
    print(f"Chunk             : {events[target_index].get('_chunk')}")
    print()

    start_ts = target_ts - 20000
    end_ts = target_ts + 20000

    window = [
        (i, event)
        for i, event in enumerate(events)
        if start_ts <= timestamp(event) <= end_ts
    ]

    print(f"Events in ±20s window: {len(window)}")
    print()

    print(
        f"{'IDX':>5} | "
        f"{'ΔT':>8} | "
        f"{'EVENT TYPE':24s} | "
        f"{'APP':22s} | "
        f"{'WINDOW TITLE':55s} | "
        f"TEXT"
    )

    print("-" * 180)

    for i, event in window:
        print_event(event, i, target_ts)


def summarize_target(events, target_ts):
    start_ts = target_ts - 20000
    end_ts = target_ts + 20000

    window = [
        event
        for event in events
        if start_ts <= timestamp(event) <= end_ts
    ]

    apps = defaultdict(int)
    event_types = defaultdict(int)

    for event in window:
        apps[get_app(event)] += 1
        event_types[event.get("event_type", "")] += 1

    return apps, event_types


def main():

    print("=" * 120)
    print("INSPECTING V5 LIKELY MISSING EXECUTIONS")
    print("=" * 120)
    print(f"Targets: {len(TARGETS)}")
    print()

    events_by_session = load_events()

    print(f"Sessions loaded: {len(events_by_session)}")

    for number, (session, target_ts) in enumerate(TARGETS, start=1):

        if session not in events_by_session:
            print()
            print(f"WARNING: session not found: {session}")
            continue

        events = events_by_session[session]

        inspect_target(
            events,
            target_ts,
            number
        )

        apps, event_types = summarize_target(
            events,
            target_ts
        )

        print()
        print("APP COUNTS")
        for app, count in sorted(
            apps.items(),
            key=lambda x: (-x[1], x[0])
        ):
            print(f"  {app:30s} {count}")

        print()
        print("EVENT TYPE COUNTS")
        for event_type, count in sorted(
            event_types.items(),
            key=lambda x: (-x[1], x[0])
        ):
            print(f"  {event_type:30s} {count}")

    print()
    print("=" * 120)
    print("END OF INSPECTION")
    print("=" * 120)


if __name__ == "__main__":
    main()