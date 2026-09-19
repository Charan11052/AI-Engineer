import json
import importlib.util
from pathlib import Path
from collections import Counter
from statistics import median, mean


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATASET_B = ROOT / "data" / "dataset_b"
OUTPUT_DIR = ROOT / "outputs" / "dataset_b"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PIPELINE_FILE = ROOT / "src" / "pipeline" / "01_segment_dataset_b.py"


# ============================================================
# ANALYSIS CONFIGURATION
# ============================================================

LOOKBACK_SECONDS = 60

GAP_THRESHOLDS = [
    2,
    5,
    8,
    10,
    15,
    20,
    30,
]

ACTIVITY_TYPES = {
    "mouse_click",
    "browser_click",
    "browser_navigation",
    "browser_form_input",
    "keystroke",
    "shortcut",
    "clipboard_change",
    "mouse_scroll",
    "app_switch",
}


# ============================================================
# LOAD EXISTING V6 LOGIC
# ============================================================

def load_v6_module():

    spec = importlib.util.spec_from_file_location(
        "dataset_b_v6_pipeline",
        PIPELINE_FILE,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Could not load V6 pipeline: {PIPELINE_FILE}"
        )

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    return module


V6 = load_v6_module()


# ============================================================
# HELPERS
# ============================================================

def parse_timestamp(event):

    value = event.get("timestamp_ms")

    if value is not None:

        try:
            return int(value)
        except (TypeError, ValueError):
            pass

    return V6.parse_timestamp(event)


def get_event_type(event):

    return str(
        event.get(
            "event_type",
            "unknown",
        )
    )


def get_text(event):

    return V6.get_event_text(event)


def get_app(event):

    return V6.get_active_app(event)


def detect_completion(event):

    return V6.detect_completion(event)


def detect_supporting_tasks(event):

    return V6.detect_supporting_tasks(event)


def is_activity(event):

    return get_event_type(event) in ACTIVITY_TYPES


def identity(event):

    context = event.get("context", {})

    active_app = context.get("active_app")

    if isinstance(active_app, dict):

        app = (
            active_app.get("app_name")
            or active_app.get("process_name")
            or "unknown"
        )

        window = (
            active_app.get("window_title")
            or ""
        )

    else:

        app = "unknown"
        window = ""

    return (
        str(app).lower(),
        str(window).lower(),
    )


# ============================================================
# LOAD DATASET B
# ============================================================

def load_chunks():

    chunks = []

    files = sorted(
        DATASET_B.rglob("events.jsonl")
    )

    print(
        f"Dataset B root: {DATASET_B}"
    )

    print(
        f"Found events.jsonl files: {len(files)}"
    )

    for path in files:

        events = []

        with path.open(
            "r",
            encoding="utf-8",
        ) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                timestamp = parse_timestamp(event)

                if timestamp is None:
                    continue

                event["_ts"] = timestamp

                events.append(event)

        if not events:
            continue

        events.sort(
            key=lambda event: event["_ts"]
        )

        chunks.append(
            {
                "path": path,
                "events": events,
            }
        )

    return chunks


# ============================================================
# FIND COMPLETIONS
# ============================================================

def find_completions(chunks):

    completions = []

    for chunk_id, chunk in enumerate(chunks):

        events = chunk["events"]

        for index, event in enumerate(events):

            task = detect_completion(event)

            if task is None:
                continue

            completions.append(
                {
                    "chunk_id": chunk_id,
                    "index": index,
                    "timestamp_ms": event["_ts"],
                    "task": task,
                    "event_type": get_event_type(event),
                    "app": get_app(event),
                    "text": get_text(event),
                    "path": str(chunk["path"]),
                }
            )

    return completions


# ============================================================
# LOOKBACK WINDOW
# ============================================================

def get_window(
    events,
    completion_index,
):

    completion_ts = (
        events[completion_index]["_ts"]
    )

    lower_bound = (
        completion_ts
        - LOOKBACK_SECONDS * 1000
    )

    result = []

    for index in range(
        completion_index - 1,
        -1,
        -1,
    ):

        event = events[index]

        if event["_ts"] < lower_bound:
            break

        result.append(
            (
                index,
                event,
            )
        )

    result.reverse()

    return result


# ============================================================
# GAP ANALYSIS
# ============================================================

def calculate_gaps(window):

    gaps = []

    for i in range(
        1,
        len(window),
    ):

        previous = window[i - 1][1]
        current = window[i][1]

        gap = (
            current["_ts"]
            - previous["_ts"]
        ) / 1000.0

        if gap >= 0:

            gaps.append(
                {
                    "previous_index":
                        window[i - 1][0],

                    "current_index":
                        window[i][0],

                    "gap_seconds":
                        gap,

                    "current_event_type":
                        get_event_type(current),

                    "current_app":
                        get_app(current),

                    "current_text":
                        get_text(current),
                }
            )

    return gaps


# ============================================================
# CONTEXT CHANGES
# ============================================================

def find_context_changes(window):

    changes = []

    for i in range(
        1,
        len(window),
    ):

        previous_index, previous = (
            window[i - 1]
        )

        current_index, current = (
            window[i]
        )

        previous_identity = identity(
            previous
        )

        current_identity = identity(
            current
        )

        if previous_identity == current_identity:
            continue

        changes.append(
            {
                "previous_index":
                    previous_index,

                "current_index":
                    current_index,

                "previous_app":
                    previous_identity[0],

                "current_app":
                    current_identity[0],

                "previous_window":
                    previous_identity[1],

                "current_window":
                    current_identity[1],

                "gap_seconds":
                    (
                        current["_ts"]
                        - previous["_ts"]
                    ) / 1000.0,
            }
        )

    return changes


# ============================================================
# START SIGNALS
# ============================================================

def classify_start_signal(event):

    event_type = get_event_type(event)

    signals = []

    if event_type == "browser_navigation":
        signals.append("navigation")

    if event_type in {
        "mouse_click",
        "browser_click",
    }:
        signals.append("click")

    if event_type == "browser_form_input":
        signals.append("form_input")

    if event_type == "keystroke":
        signals.append("keystroke")

    if event_type == "shortcut":
        signals.append("shortcut")

    if event_type == "app_switch":
        signals.append("app_switch")

    if get_text(event):
        signals.append("text_evidence")

    return signals


def collect_start_signals(window):

    candidates = []

    for index, event in window:

        if not is_activity(event):
            continue

        signals = classify_start_signal(
            event
        )

        if not signals:
            continue

        candidates.append(
            {
                "index": index,
                "timestamp_ms": event["_ts"],
                "event_type":
                    get_event_type(event),
                "app":
                    get_app(event),
                "signals":
                    signals,
                "text":
                    get_text(event),
            }
        )

    return candidates


# ============================================================
# TASK-CONSISTENCY ANALYSIS
# ============================================================

def analyze_task_evidence(
    window,
    completion_task,
):

    matching = []
    different = []

    for index, event in window:

        tasks = detect_supporting_tasks(
            event
        )

        if completion_task in tasks:

            matching.append(
                {
                    "index": index,
                    "event_type":
                        get_event_type(event),
                    "timestamp_ms":
                        event["_ts"],
                    "text":
                        get_text(event),
                }
            )

        for task in tasks:

            if task != completion_task:

                different.append(
                    {
                        "index": index,
                        "task": task,
                        "event_type":
                            get_event_type(event),
                        "timestamp_ms":
                            event["_ts"],
                        "text":
                            get_text(event),
                    }
                )

    return matching, different


# ============================================================
# ONE COMPLETION ANALYSIS
# ============================================================

def analyze_completion(
    completion,
    chunk,
):

    events = chunk["events"]

    completion_index = (
        completion["index"]
    )

    completion_ts = (
        completion["timestamp_ms"]
    )

    window = get_window(
        events,
        completion_index,
    )

    gaps = calculate_gaps(
        window
    )

    context_changes = (
        find_context_changes(window)
    )

    start_signals = (
        collect_start_signals(window)
    )

    matching_evidence, different_evidence = (
        analyze_task_evidence(
            window,
            completion["task"],
        )
    )

    first_activity = None

    for index, event in window:

        if is_activity(event):

            first_activity = {
                "index": index,
                "timestamp_ms":
                    event["_ts"],
                "event_type":
                    get_event_type(event),
                "app":
                    get_app(event),
                "text":
                    get_text(event),
            }

            break

    last_activity = None

    for index, event in reversed(window):

        if is_activity(event):

            last_activity = {
                "index": index,
                "timestamp_ms":
                    event["_ts"],
                "event_type":
                    get_event_type(event),
                "app":
                    get_app(event),
                "text":
                    get_text(event),
            }

            break

    gap_candidates = {}

    for threshold in GAP_THRESHOLDS:

        candidates = [
            gap
            for gap in gaps
            if gap["gap_seconds"]
            >= threshold
        ]

        gap_candidates[
            str(threshold)
        ] = candidates

    candidate_distances = []

    for candidate in start_signals:

        distance = (
            completion_ts
            - candidate["timestamp_ms"]
        ) / 1000.0

        candidate_distances.append(
            {
                "event_type":
                    candidate["event_type"],
                "distance_seconds":
                    distance,
                "signals":
                    candidate["signals"],
            }
        )

    return {
        "completion": completion,
        "window_event_count":
            len(window),

        "window_duration_seconds":
            (
                (
                    completion_ts
                    - window[0][1]["_ts"]
                ) / 1000.0
                if window
                else 0
            ),

        "activity_event_count":
            sum(
                1
                for _, event in window
                if is_activity(event)
            ),

        "first_activity":
            first_activity,

        "last_activity":
            last_activity,

        "gaps":
            gaps,

        "gap_candidates":
            gap_candidates,

        "context_changes":
            context_changes,

        "start_signals":
            start_signals,

        "candidate_distances":
            candidate_distances,

        "matching_task_evidence":
            matching_evidence,

        "different_task_evidence":
            different_evidence,
    }


# ============================================================
# STATISTICS
# ============================================================

def percentile(
    values,
    fraction,
):

    if not values:
        return None

    values = sorted(values)

    position = (
        len(values) - 1
    ) * fraction

    lower = int(position)

    upper = min(
        lower + 1,
        len(values) - 1,
    )

    weight = position - lower

    return (
        values[lower] * (1 - weight)
        + values[upper] * weight
    )


def numeric_summary(values):

    values = [
        float(value)
        for value in values
        if value is not None
    ]

    if not values:
        return {}

    return {
        "count":
            len(values),

        "min":
            min(values),

        "p25":
            percentile(values, 0.25),

        "median":
            median(values),

        "mean":
            mean(values),

        "p75":
            percentile(values, 0.75),

        "p90":
            percentile(values, 0.90),

        "p95":
            percentile(values, 0.95),

        "max":
            max(values),
    }


# ============================================================
# AGGREGATE
# ============================================================

def aggregate(analyses):

    task_counts = Counter()
    first_activity = Counter()
    last_activity = Counter()
    start_types = Counter()
    signal_types = Counter()
    context_types = Counter()

    window_durations = []
    window_event_counts = []
    activity_counts = []
    largest_gaps = []
    candidate_distances = []

    gap_coverage = {
        str(threshold):
            0
        for threshold in GAP_THRESHOLDS
    }

    for analysis in analyses:

        completion = (
            analysis["completion"]
        )

        task_counts[
            completion["task"]
        ] += 1

        first = (
            analysis["first_activity"]
        )

        if first:

            first_activity[
                first["event_type"]
            ] += 1

        last = (
            analysis["last_activity"]
        )

        if last:

            last_activity[
                last["event_type"]
            ] += 1

        for candidate in (
            analysis["start_signals"]
        ):

            start_types[
                candidate["event_type"]
            ] += 1

            for signal in (
                candidate["signals"]
            ):
                signal_types[signal] += 1

        for change in (
            analysis["context_changes"]
        ):

            if (
                change["previous_app"]
                != change["current_app"]
            ):

                context_types[
                    "app_change"
                ] += 1

            elif (
                change["previous_window"]
                != change["current_window"]
            ):

                context_types[
                    "window_change"
                ] += 1

        window_durations.append(
            analysis[
                "window_duration_seconds"
            ]
        )

        window_event_counts.append(
            analysis[
                "window_event_count"
            ]
        )

        activity_counts.append(
            analysis[
                "activity_event_count"
            ]
        )

        gaps = analysis["gaps"]

        if gaps:

            largest_gaps.append(
                max(
                    gap["gap_seconds"]
                    for gap in gaps
                )
            )

        for candidate in (
            analysis["candidate_distances"]
        ):

            candidate_distances.append(
                candidate[
                    "distance_seconds"
                ]
            )

        for threshold in GAP_THRESHOLDS:

            if analysis[
                "gap_candidates"
            ][str(threshold)]:

                gap_coverage[
                    str(threshold)
                ] += 1

    completion_count = len(
        analyses
    )

    return {
        "completion_count":
            completion_count,

        "task_counts":
            dict(task_counts),

        "first_activity_types":
            dict(first_activity),

        "last_activity_types":
            dict(last_activity),

        "candidate_start_event_types":
            dict(start_types),

        "candidate_signal_types":
            dict(signal_types),

        "context_changes":
            dict(context_types),

        "window_duration_seconds":
            numeric_summary(
                window_durations
            ),

        "window_event_count":
            numeric_summary(
                window_event_counts
            ),

        "activity_event_count":
            numeric_summary(
                activity_counts
            ),

        "largest_gap_seconds":
            numeric_summary(
                largest_gaps
            ),

        "candidate_distance_seconds":
            numeric_summary(
                candidate_distances
            ),

        "gap_coverage": {
            threshold: {
                "count":
                    count,

                "percent":
                    (
                        100 * count
                        / completion_count
                        if completion_count
                        else 0
                    ),
            }

            for threshold, count
            in gap_coverage.items()
        },
    }


# ============================================================
# PRINT
# ============================================================

def print_counter(
    title,
    counter,
):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    for key, value in sorted(
        counter.items(),
        key=lambda item: -item[1],
    ):

        print(
            f"{key:<35} {value}"
        )


def print_numeric(
    title,
    data,
):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    for name, values in data.items():

        print()
        print(name)

        for metric, value in values.items():

            if isinstance(
                value,
                float,
            ):

                print(
                    f"  {metric:<10} "
                    f"{value:.3f}"
                )

            else:

                print(
                    f"  {metric:<10} "
                    f"{value}"
                )


def print_examples(
    analyses,
    count=20,
):

    print()
    print("=" * 70)
    print(
        "COMPLETION WINDOWS — EXAMPLES"
    )
    print("=" * 70)

    for number, analysis in enumerate(
        analyses[:count],
        start=1,
    ):

        completion = (
            analysis["completion"]
        )

        print()
        print(
            f"[{number}] "
            f"{completion['task']}"
        )

        print(
            f"  completion event : "
            f"{completion['event_type']}"
        )

        print(
            f"  application      : "
            f"{completion['app']}"
        )

        print(
            f"  window duration  : "
            f"{analysis['window_duration_seconds']:.2f}s"
        )

        print(
            f"  events in window : "
            f"{analysis['window_event_count']}"
        )

        if analysis[
            "first_activity"
        ]:

            first = analysis[
                "first_activity"
            ]

            distance = (
                completion[
                    "timestamp_ms"
                ]
                - first[
                    "timestamp_ms"
                ]
            ) / 1000.0

            print(
                f"  first activity   : "
                f"{first['event_type']} "
                f"({distance:.2f}s before)"
            )

        if analysis[
            "last_activity"
        ]:

            last = analysis[
                "last_activity"
            ]

            distance = (
                completion[
                    "timestamp_ms"
                ]
                - last[
                    "timestamp_ms"
                ]
            ) / 1000.0

            print(
                f"  last activity    : "
                f"{last['event_type']} "
                f"({distance:.2f}s before)"
            )

        if analysis[
            "context_changes"
        ]:

            print(
                f"  context changes  : "
                f"{len(analysis['context_changes'])}"
            )

        if analysis[
            "gaps"
        ]:

            largest = max(
                analysis["gaps"],
                key=lambda x:
                    x["gap_seconds"],
            )

            print(
                f"  largest gap      : "
                f"{largest['gap_seconds']:.2f}s "
                f"→ {largest['current_event_type']}"
            )

        print(
            f"  task evidence    : "
            f"{len(analysis['matching_task_evidence'])}"
        )

        if analysis[
            "different_task_evidence"
        ]:

            different = Counter(
                item["task"]
                for item in analysis[
                    "different_task_evidence"
                ]
            )

            print(
                f"  other task evidence: "
                f"{dict(different)}"
            )


# ============================================================
# SAVE
# ============================================================

def save_results(
    summary,
    analyses,
):

    output_file = (
        OUTPUT_DIR
        / "dataset_b_task_start_signal_analysis.json"
    )

    payload = {
        "analysis_config": {
            "lookback_seconds":
                LOOKBACK_SECONDS,

            "gap_thresholds":
                GAP_THRESHOLDS,

            "activity_types":
                sorted(
                    ACTIVITY_TYPES
                ),
        },

        "summary":
            summary,

        "completion_analyses":
            analyses,
    }

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            payload,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return output_file


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "DATASET B — RAW TASK START SIGNAL ANALYSIS"
    )
    print("=" * 70)

    print()
    print(
        f"Project root : {ROOT}"
    )

    print(
        f"Dataset B    : {DATASET_B}"
    )

    print(
        f"V6 pipeline  : {PIPELINE_FILE}"
    )

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    chunks = load_chunks()

    total_events = sum(
        len(chunk["events"])
        for chunk in chunks
    )

    print()
    print(
        f"Chunks loaded : {len(chunks)}"
    )

    print(
        f"Events loaded : {total_events}"
    )

    # --------------------------------------------------------
    # COMPLETIONS
    # --------------------------------------------------------

    completions = find_completions(
        chunks
    )

    print()
    print(
        f"Strong completion anchors found: "
        f"{len(completions)}"
    )

    if not completions:

        print()
        print(
            "ERROR: V6 completion detector "
            "returned zero anchors."
        )

        return

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    analyses = []

    for completion in completions:

        chunk = chunks[
            completion["chunk_id"]
        ]

        analyses.append(
            analyze_completion(
                completion,
                chunk,
            )
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    summary = aggregate(
        analyses
    )

    print_counter(
        "TASK DISTRIBUTION",
        Counter(
            summary[
                "task_counts"
            ]
        ),
    )

    print_counter(
        "FIRST ACTIVITY BEFORE COMPLETION",
        Counter(
            summary[
                "first_activity_types"
            ]
        ),
    )

    print_counter(
        "LAST ACTIVITY BEFORE COMPLETION",
        Counter(
            summary[
                "last_activity_types"
            ]
        ),
    )

    print_counter(
        "CANDIDATE START EVENT TYPES",
        Counter(
            summary[
                "candidate_start_event_types"
            ]
        ),
    )

    print_counter(
        "CANDIDATE START SIGNAL TYPES",
        Counter(
            summary[
                "candidate_signal_types"
            ]
        ),
    )

    print_counter(
        "CONTEXT CHANGES",
        Counter(
            summary[
                "context_changes"
            ]
        ),
    )

    print_numeric(
        "NUMERIC DISTRIBUTIONS",
        {
            "lookback duration":
                summary[
                    "window_duration_seconds"
                ],

            "events":
                summary[
                    "window_event_count"
                ],

            "activity events":
                summary[
                    "activity_event_count"
                ],

            "largest gaps":
                summary[
                    "largest_gap_seconds"
                ],

            "candidate start distance":
                summary[
                    "candidate_distance_seconds"
                ],
        },
    )

    print()
    print("=" * 70)
    print(
        "IDLE GAP COVERAGE"
    )
    print("=" * 70)

    for threshold, info in (
        summary[
            "gap_coverage"
        ].items()
    ):

        print(
            f">={threshold:>2}s : "
            f"{info['count']:>3} / "
            f"{summary['completion_count']:>3} "
            f"({info['percent']:.2f}%)"
        )

    print_examples(
        analyses,
        count=20,
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    output_file = save_results(
        summary,
        analyses,
    )

    print()
    print("=" * 70)
    print(
        "ANALYSIS COMPLETE"
    )
    print("=" * 70)

    print(
        f"Saved to:\n{output_file}"
    )


if __name__ == "__main__":
    main()