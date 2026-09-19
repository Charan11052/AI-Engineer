import os
import json
import csv
from collections import Counter


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DATASET_B_DIR = os.path.join(
    BASE_DIR,
    "data",
    "dataset_b"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "outputs"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def load_jsonl(path):
    records = []

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return records


def get_event_type(event):

    return (
        event.get("event")
        or event.get("event_type")
        or event.get("type")
        or "unknown"
    )


def get_timestamp(event):

    return (
        event.get("timestamp")
        or event.get("ts")
        or event.get("time")
    )


def get_app(event):

    app = event.get("active_app")

    if isinstance(app, dict):

        return str(
            app.get("app_name")
            or app.get("process_name")
            or "unknown"
        ).lower()

    if app:
        return str(app).lower()

    context = event.get("context")

    if isinstance(context, dict):

        app = (
            context.get("active_app")
            or context.get("application")
            or context.get("app")
        )

        if isinstance(app, dict):

            return str(
                app.get("app_name")
                or app.get("process_name")
                or "unknown"
            ).lower()

        if app:
            return str(app).lower()

    return "unknown"


def has_text(event):

    context = event.get("context")

    if not isinstance(context, dict):
        return False

    text = context.get("extracted_text")

    return bool(
        text and str(text).strip()
    )


# ============================================================
# FIND SESSIONS
# ============================================================

session_files = []

for root, dirs, files in os.walk(DATASET_B_DIR):

    for filename in files:

        if filename == "events.jsonl":

            session_files.append(
                os.path.join(root, filename)
            )

session_files.sort()


# ============================================================
# GLOBAL COUNTERS
# ============================================================

event_counter = Counter()
app_counter = Counter()

session_rows = []

total_events = 0
total_text_events = 0


# ============================================================
# ANALYZE EACH SESSION
# ============================================================

for path in session_files:

    session_id = os.path.basename(
        os.path.dirname(path)
    )

    events = load_jsonl(path)

    total_events += len(events)

    session_event_counter = Counter()
    session_app_counter = Counter()

    text_count = 0

    timestamps = []

    for event in events:

        event_type = get_event_type(event)
        app = get_app(event)

        session_event_counter[event_type] += 1
        session_app_counter[app] += 1

        event_counter[event_type] += 1
        app_counter[app] += 1

        if has_text(event):
            text_count += 1
            total_text_events += 1

        timestamp = get_timestamp(event)

        if timestamp:
            timestamps.append(timestamp)

    session_rows.append(
        {
            "session_id": session_id,
            "events": len(events),
            "unique_event_types": len(
                session_event_counter
            ),
            "unique_apps": len(
                session_app_counter
            ),
            "text_events": text_count,
            "first_timestamp": (
                timestamps[0]
                if timestamps
                else None
            ),
            "last_timestamp": (
                timestamps[-1]
                if timestamps
                else None
            ),
        }
    )


# ============================================================
# PRINT COMPACT SUMMARY
# ============================================================

print()
print("=" * 70)
print("DATASET B INITIAL INSPECTION")
print("=" * 70)

print()
print(f"Sessions           : {len(session_files)}")
print(f"Total events       : {total_events}")
print(f"Events with text   : {total_text_events}")
print(f"Event types        : {len(event_counter)}")
print(f"Applications       : {len(app_counter)}")


# ============================================================
# EVENT TYPES
# ============================================================

print()
print("=" * 70)
print("TOP EVENT TYPES")
print("=" * 70)

for event_type, count in event_counter.most_common(20):

    percentage = (
        100 * count / total_events
        if total_events
        else 0
    )

    print(
        f"{event_type:30s}"
        f"{count:8d}"
        f"  {percentage:6.2f}%"
    )


# ============================================================
# APPLICATIONS
# ============================================================

print()
print("=" * 70)
print("TOP APPLICATIONS")
print("=" * 70)

for app, count in app_counter.most_common(20):

    percentage = (
        100 * count / total_events
        if total_events
        else 0
    )

    print(
        f"{app:30s}"
        f"{count:8d}"
        f"  {percentage:6.2f}%"
    )


# ============================================================
# SESSION SUMMARY
# ============================================================

print()
print("=" * 70)
print("SESSION SUMMARY")
print("=" * 70)

for row in sorted(
    session_rows,
    key=lambda x: x["events"],
    reverse=True
):

    print(
        f"{row['session_id']:25s}"
        f" events={row['events']:5d}"
        f" apps={row['unique_apps']:2d}"
        f" text={row['text_events']:4d}"
    )


# ============================================================
# SAVE SESSION CSV
# ============================================================

csv_path = os.path.join(
    OUTPUT_DIR,
    "dataset_b_session_summary.csv"
)

with open(
    csv_path,
    "w",
    encoding="utf-8",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "session_id",
            "events",
            "unique_event_types",
            "unique_apps",
            "text_events",
            "first_timestamp",
            "last_timestamp",
        ]
    )

    writer.writeheader()

    writer.writerows(session_rows)


# ============================================================
# SAVE COMPLETE SUMMARY
# ============================================================

json_path = os.path.join(
    OUTPUT_DIR,
    "dataset_b_initial_summary.json"
)

summary = {
    "sessions": len(session_files),
    "total_events": total_events,
    "events_with_text": total_text_events,
    "event_types": dict(event_counter),
    "applications": dict(app_counter),
    "sessions": session_rows,
}

with open(
    json_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        summary,
        f,
        indent=2,
        ensure_ascii=False
    )


# ============================================================
# DONE
# ============================================================

print()
print("=" * 70)
print("OUTPUTS")
print("=" * 70)

print(
    f"Session summary : {csv_path}"
)

print(
    f"Initial summary : {json_path}"
)

print()
print("Dataset B inspection complete.")