import json
import csv
from collections import Counter, defaultdict
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parents[2]

LABELED_EVENTS = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_labeled_events.jsonl"
)

OUTPUT_DIR = PROJECT_DIR / "outputs" / "dataset_a"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_EVENT_TYPES = OUTPUT_DIR / "dataset_a_process_event_types.csv"
OUTPUT_TRANSITIONS = OUTPUT_DIR / "dataset_a_process_transitions.csv"
OUTPUT_APPS = OUTPUT_DIR / "dataset_a_process_app_patterns.csv"


# ============================================================
# HELPERS
# ============================================================

def get_event_type(event):
    """
    Ground-truth aware event type extraction.
    """
    return (
        event.get("event")
        or event.get("event_type")
        or event.get("type")
        or "unknown"
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

# ============================================================
# LOAD DATA
# ============================================================

print("=" * 70)
print("DATASET A PROCESS BEHAVIOR ANALYSIS")
print("=" * 70)

print("\nLoading labeled events...")

events = []

with open(LABELED_EVENTS, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()

        if not line:
            continue

        events.append(json.loads(line))

print(f"Events loaded: {len(events):,}")


# ============================================================
# GROUP EVENTS BY PROCESS
# ============================================================

process_events = defaultdict(list)

for event in events:

    process_code = event.get("process_code")

    if process_code:
        process_events[process_code].append(event)


print(f"Processes found: {len(process_events)}")


# ============================================================
# EVENT TYPE ANALYSIS
# ============================================================

print("\nCalculating event-type patterns...")

event_rows = []

for process_code in sorted(process_events):

    counter = Counter()

    for event in process_events[process_code]:
        event_type = get_event_type(event)
        counter[event_type] += 1

    total = sum(counter.values())

    for event_type, count in counter.most_common():

        event_rows.append({
            "process_code": process_code,
            "event_type": event_type,
            "count": count,
            "share": round(count / total, 4) if total else 0
        })


with open(OUTPUT_EVENT_TYPES, "w", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "process_code",
            "event_type",
            "count",
            "share"
        ]
    )

    writer.writeheader()
    writer.writerows(event_rows)


# ============================================================
# APPLICATION PATTERNS
# ============================================================

print("Calculating application patterns...")

app_rows = []

for process_code in sorted(process_events):

    counter = Counter()

    for event in process_events[process_code]:

        app = get_app(event)

        if app != "unknown":
            counter[app] += 1

    total = sum(counter.values())

    for app, count in counter.most_common():

        app_rows.append({
            "process_code": process_code,
            "application": app,
            "event_count": count,
            "share": round(count / total, 4) if total else 0
        })


with open(OUTPUT_APPS, "w", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "process_code",
            "application",
            "event_count",
            "share"
        ]
    )

    writer.writeheader()
    writer.writerows(app_rows)


# ============================================================
# APPLICATION TRANSITIONS
# ============================================================

print("Calculating application transitions...")

transition_counter = Counter()

for process_code in sorted(process_events):

    # Sort by timestamp if available.
    process_list = process_events[process_code]

    previous_app = None

    for event in process_list:

        app = get_app(event)

        if app == "unknown":
            continue

        if previous_app is not None and app != previous_app:

            transition_counter[
                (
                    process_code,
                    previous_app,
                    app
                )
            ] += 1

        previous_app = app


transition_rows = []

for (
    process_code,
    from_app,
    to_app
), count in transition_counter.most_common():

    transition_rows.append({
        "process_code": process_code,
        "from_app": from_app,
        "to_app": to_app,
        "count": count
    })


with open(OUTPUT_TRANSITIONS, "w", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "process_code",
            "from_app",
            "to_app",
            "count"
        ]
    )

    writer.writeheader()
    writer.writerows(transition_rows)


# ============================================================
# COMPACT SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("COMPACT PROCESS BEHAVIOR SUMMARY")
print("=" * 70)

for process_code in sorted(process_events):

    process_list = process_events[process_code]

    event_counter = Counter(
        get_event_type(event)
        for event in process_list
    )

    app_counter = Counter(
        get_app(event)
        for event in process_list
        if get_app(event) != "unknown"
    )

    print(f"\nPROCESS {process_code}")
    print("-" * 50)

    print(
        "Top events:",
        ", ".join(
            f"{event}={count}"
            for event, count in event_counter.most_common(5)
        )
    )

    print(
        "Top apps:",
        ", ".join(
            f"{app}={count}"
            for app, count in app_counter.most_common(5)
        )
    )


# ============================================================
# TOP TRANSITIONS
# ============================================================

print("\n" + "=" * 70)
print("TOP APPLICATION TRANSITIONS")
print("=" * 70)

for (
    process_code,
    from_app,
    to_app
), count in transition_counter.most_common(30):

    print(
        f"{process_code}: "
        f"{from_app} -> {to_app} "
        f"({count})"
    )


# ============================================================
# OUTPUT FILES
# ============================================================

print("\n" + "=" * 70)
print("OUTPUT FILES")
print("=" * 70)

print(f"Event types  : {OUTPUT_EVENT_TYPES}")
print(f"Transitions  : {OUTPUT_TRANSITIONS}")
print(f"App patterns : {OUTPUT_APPS}")

print("\nDataset A process behavior analysis complete.")

