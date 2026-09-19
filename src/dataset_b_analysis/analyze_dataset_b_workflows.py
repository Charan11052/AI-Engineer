import os
import json
from collections import Counter, defaultdict


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DATASET_B_DIR = os.path.join(BASE_DIR, "data", "dataset_b")


# ============================================================
# HELPERS
# ============================================================

def load_jsonl(path):

    events = []

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
                events.append(
                    json.loads(line)
                )

            except json.JSONDecodeError:
                pass

    return events


def get_event_type(event):

    return (
        event.get("event_type")
        or event.get("event")
        or event.get("type")
        or "unknown"
    )


def get_app(event):

    context = event.get("context")

    if not isinstance(context, dict):
        return "unknown"

    app = context.get("active_app")

    if isinstance(app, dict):

        return str(
            app.get("app_name")
            or app.get("process_name")
            or "unknown"
        ).lower()

    if app:
        return str(app).lower()

    return "unknown"


def get_window(event):

    context = event.get("context")

    if not isinstance(context, dict):
        return ""

    app = context.get("active_app")

    if isinstance(app, dict):

        return str(
            app.get("window_title")
            or ""
        )

    return ""


def get_timestamp(event):

    value = (
        event.get("timestamp_ms")
        or event.get("timestamp")
        or event.get("ts")
    )

    if value is None:
        return None

    try:

        value = float(value)

        if value > 1_000_000_000_000:
            value /= 1000

        return value

    except (TypeError, ValueError):

        return None


def get_text(event):

    context = event.get("context")

    if not isinstance(context, dict):
        return ""

    extracted = context.get(
        "extracted_text"
    )

    if isinstance(extracted, dict):

        return str(
            extracted.get("text")
            or ""
        ).strip()

    if extracted:
        return str(extracted).strip()

    return ""


# ============================================================
# EVENT FILES
# ============================================================

session_files = []

for root, dirs, files in os.walk(
    DATASET_B_DIR
):

    if "events.jsonl" in files:

        session_files.append(
            os.path.join(
                root,
                "events.jsonl"
            )
        )

session_files.sort()

print()
print("DEBUG")
print("=" * 70)
print("DATASET_B_DIR :", DATASET_B_DIR)
print("Directory exists:", os.path.exists(DATASET_B_DIR))
print("events.jsonl files found:", len(session_files))

for path in session_files[:10]:
    print("FOUND:", path)

print("=" * 70)


# ============================================================
# GLOBAL PATTERNS
# ============================================================

app_transitions = Counter()

event_transitions = Counter()

app_event_patterns = Counter()

clipboard_contexts = Counter()

browser_workflows = Counter()

window_patterns = Counter()


# ============================================================
# PROCESS EACH SESSION
# ============================================================

for path in session_files:

    session_id = os.path.basename(
        os.path.dirname(path)
    )

    events = load_jsonl(path)

    # Sort chronologically
    events.sort(
        key=lambda e: (
            get_timestamp(e)
            if get_timestamp(e) is not None
            else 0
        )
    )

    previous_app = None
    previous_event = None

    recent_apps = []

    for event in events:

        event_type = get_event_type(event)
        app = get_app(event)
        window = get_window(event)
        text = get_text(event)

        # ----------------------------------------------------
        # App transitions
        # ----------------------------------------------------

        if (
            previous_app is not None
            and app != previous_app
        ):

            app_transitions[
                (
                    previous_app,
                    app
                )
            ] += 1

        # ----------------------------------------------------
        # Event transitions
        # ----------------------------------------------------

        if previous_event is not None:

            event_transitions[
                (
                    previous_event,
                    event_type
                )
            ] += 1

        # ----------------------------------------------------
        # App + event pattern
        # ----------------------------------------------------

        app_event_patterns[
            (
                app,
                event_type
            )
        ] += 1

        # ----------------------------------------------------
        # Clipboard context
        # ----------------------------------------------------

        if event_type == "clipboard_change":

            previous = (
                recent_apps[-3:]
                if recent_apps
                else []
            )

            clipboard_contexts[
                tuple(previous)
            ] += 1

        # ----------------------------------------------------
        # Browser workflow context
        # ----------------------------------------------------

        if event_type in {
            "browser_navigation",
            "browser_form_input",
            "browser_click"
        }:

            browser_workflows[
                (
                    event_type,
                    app
                )
            ] += 1

        # ----------------------------------------------------
        # Window titles
        # ----------------------------------------------------

        if window:

            # Keep only useful title patterns
            normalized = window.lower()

            window_patterns[
                normalized[:120]
            ] += 1

        # Maintain recent application history
        recent_apps.append(app)

        if len(recent_apps) > 5:
            recent_apps.pop(0)

        previous_app = app
        previous_event = event_type


# ============================================================
# OUTPUT
# ============================================================

print()
print("=" * 70)
print("DATASET B WORKFLOW ANALYSIS")
print("=" * 70)


# ============================================================
# APP TRANSITIONS
# ============================================================

print()
print("=" * 70)
print("TOP APPLICATION TRANSITIONS")
print("=" * 70)

for (a, b), count in (
    app_transitions.most_common(30)
):

    print(
        f"{a:25s} -> "
        f"{b:25s} "
        f"{count:5d}"
    )


# ============================================================
# EVENT TRANSITIONS
# ============================================================

print()
print("=" * 70)
print("TOP EVENT TRANSITIONS")
print("=" * 70)

for (a, b), count in (
    event_transitions.most_common(30)
):

    print(
        f"{a:30s} -> "
        f"{b:30s} "
        f"{count:5d}"
    )


# ============================================================
# APP + EVENT
# ============================================================

print()
print("=" * 70)
print("IMPORTANT APP + EVENT COMBINATIONS")
print("=" * 70)

for (app, event_type), count in (
    app_event_patterns.most_common(40)
):

    print(
        f"{app:25s} "
        f"{event_type:30s} "
        f"{count:5d}"
    )


# ============================================================
# CLIPBOARD
# ============================================================

print()
print("=" * 70)
print("CLIPBOARD CONTEXT")
print("=" * 70)

for apps, count in (
    clipboard_contexts.most_common(20)
):

    print(
        f"{' -> '.join(apps):70s}"
        f" {count:5d}"
    )


# ============================================================
# BROWSER EVENTS
# ============================================================

print()
print("=" * 70)
print("BROWSER WORKFLOW EVENTS")
print("=" * 70)

for (event_type, app), count in (
    browser_workflows.most_common()
):

    print(
        f"{event_type:30s}"
        f"{app:25s}"
        f"{count:5d}"
    )


# ============================================================
# WINDOW TITLES
# ============================================================

print()
print("=" * 70)
print("TOP WINDOW TITLE PATTERNS")
print("=" * 70)

for title, count in (
    window_patterns.most_common(30)
):

    print(
        f"{count:5d}  {title}"
    )


print()
print("=" * 70)
print("Workflow analysis complete.")
print("=" * 70)