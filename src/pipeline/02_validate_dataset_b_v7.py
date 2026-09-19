import json
from pathlib import Path
from collections import Counter
import importlib.util


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATASET_B = ROOT / "data" / "dataset_b"
OUTPUT_DIR = ROOT / "outputs" / "dataset_b"

V7_FILE = OUTPUT_DIR / "dataset_b_segments_v7.jsonl"
V6_FILE = OUTPUT_DIR / "dataset_b_segments_v6.jsonl"

PIPELINE_V6 = (
    ROOT
    / "src"
    / "pipeline"
    / "01_segment_dataset_b.py"
)


# ============================================================
# LOAD V6 MODULE
# ============================================================

def load_v6():

    spec = importlib.util.spec_from_file_location(
        "dataset_b_v6",
        PIPELINE_V6,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Could not load V6 pipeline."
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


V6 = load_v6()


# ============================================================
# LOAD JSONL
# ============================================================

def load_jsonl(path):

    if not path.exists():
        return []

    records = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            records.append(
                json.loads(line)
            )

    return records


# ============================================================
# LOAD RAW DATA
# ============================================================

def load_chunks():

    chunks = []

    for path in sorted(
        DATASET_B.rglob("events.jsonl")
    ):

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

                timestamp = V6.parse_timestamp(
                    event
                )

                if timestamp is None:
                    continue

                event["_ts"] = timestamp

                events.append(event)

        if not events:
            continue

        events.sort(
            key=lambda x: x["_ts"]
        )

        chunks.append(
            {
                "path": path,
                "session":
                    path.parent.parent.name,
                "chunk":
                    path.parent.name,
                "events":
                    events,
            }
        )

    return chunks


# ============================================================
# DISCOVER COMPLETIONS
# ============================================================

def find_completions(chunks):

    completions = []

    for chunk in chunks:

        events = chunk["events"]

        for index, event in enumerate(events):

            task = V6.detect_completion(
                event
            )

            if task is None:
                continue

            completions.append(
                {
                    "session":
                        chunk["session"],

                    "chunk":
                        chunk["chunk"],

                    "index":
                        index,

                    "timestamp_ms":
                        event["_ts"],

                    "task":
                        task,
                }
            )

    return completions


# ============================================================
# INDEX V7 SEGMENTS
# ============================================================

def build_segment_index(segments):

    index = {}

    for segment in segments:

        key = (
            segment["session"],
            segment["chunk"],
            segment["completion_event_index"],
        )

        index[key] = segment

    return index


# ============================================================
# DURATION BUCKETS
# ============================================================

def duration_bucket(duration):

    if duration < 1:
        return "<1s"

    if duration < 2:
        return "1-2s"

    if duration < 5:
        return "2-5s"

    if duration < 10:
        return "5-10s"

    if duration < 30:
        return "10-30s"

    if duration < 60:
        return "30-60s"

    return "60s+"


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "DATASET B V7 — SEGMENT VALIDATION"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    v7 = load_jsonl(V7_FILE)
    v6 = load_jsonl(V6_FILE)

    chunks = load_chunks()

    completions = find_completions(
        chunks
    )

    print()
    print(
        f"Raw completion anchors : "
        f"{len(completions)}"
    )

    print(
        f"V7 segments            : "
        f"{len(v7)}"
    )

    print(
        f"V6 segments            : "
        f"{len(v6)}"
    )

    # --------------------------------------------------------
    # Completion coverage
    # --------------------------------------------------------

    v7_index = build_segment_index(
        v7
    )

    matched = []
    missing = []

    for completion in completions:

        key = (
            completion["session"],
            completion["chunk"],
            completion["index"],
        )

        if key in v7_index:

            matched.append(
                (
                    completion,
                    v7_index[key],
                )
            )

        else:

            missing.append(
                completion
            )

    print()
    print("=" * 70)
    print("COMPLETION COVERAGE")
    print("=" * 70)

    print(
        f"Matched completion anchors : "
        f"{len(matched)}"
    )

    print(
        f"Missing completion anchors : "
        f"{len(missing)}"
    )

    if completions:

        print(
            f"Coverage                  : "
            f"{100 * len(matched) / len(completions):.2f}%"
        )

    # --------------------------------------------------------
    # V7 duration
    # --------------------------------------------------------

    durations = [
        segment["duration_seconds"]
        for segment in v7
    ]

    buckets = Counter(
        duration_bucket(duration)
        for duration in durations
    )

    print()
    print("=" * 70)
    print("V7 DURATION DISTRIBUTION")
    print("=" * 70)

    ordered_buckets = [
        "<1s",
        "1-2s",
        "2-5s",
        "5-10s",
        "10-30s",
        "30-60s",
        "60s+",
    ]

    for bucket in ordered_buckets:

        count = buckets[bucket]

        print(
            f"{bucket:<10} "
            f"{count:>4} "
            f"({100 * count / len(v7):.2f}%)"
        )

    print()
    print(
        f"Average : "
        f"{sum(durations) / len(durations):.2f}s"
    )

    print(
        f"Min     : "
        f"{min(durations):.2f}s"
    )

    print(
        f"Max     : "
        f"{max(durations):.2f}s"
    )

    # --------------------------------------------------------
    # Start detection methods
    # --------------------------------------------------------

    methods = Counter()

    reasons = Counter()

    confidence = Counter()

    for segment in v7:

        detection = segment[
            "start_detection"
        ]

        methods[
            detection["method"]
        ] += 1

        confidence[
            segment["confidence"]
        ] += 1

        for reason in detection[
            "reasons"
        ]:

            reasons[reason] += 1

    print()
    print("=" * 70)
    print("START DETECTION METHODS")
    print("=" * 70)

    for method, count in methods.most_common():

        print(
            f"{method:<30} "
            f"{count:>4}"
        )

    print()
    print("Start reasons:")

    for reason, count in reasons.most_common():

        print(
            f"  {reason:<28} "
            f"{count:>4}"
        )

    print()
    print("Confidence:")

    for value, count in confidence.most_common():

        print(
            f"  {value:<26} "
            f"{count:>4}"
        )

    # --------------------------------------------------------
    # Distance from completion
    # --------------------------------------------------------

    distances = []

    for segment in v7:

        distance = (
            segment["end_timestamp_ms"]
            - segment["start_timestamp_ms"]
        ) / 1000.0

        distances.append(distance)

    print()
    print("=" * 70)
    print("START → COMPLETION DISTANCE")
    print("=" * 70)

    for threshold in [
        1,
        2,
        5,
        10,
        20,
        30,
        45,
    ]:

        count = sum(
            distance <= threshold
            for distance in distances
        )

        print(
            f"<= {threshold:>2}s : "
            f"{count:>4} / {len(distances):>4} "
            f"({100 * count / len(distances):.2f}%)"
        )

    # --------------------------------------------------------
    # Compare V6
    # --------------------------------------------------------

    if v6:

        v6_durations = [
            segment[
                "duration_seconds"
            ]
            for segment in v6
        ]

        print()
        print("=" * 70)
        print("V6 vs V7")
        print("=" * 70)

        print(
            f"V6 average duration : "
            f"{sum(v6_durations) / len(v6_durations):.2f}s"
        )

        print(
            f"V7 average duration : "
            f"{sum(durations) / len(durations):.2f}s"
        )

        print(
            f"V6 median duration  : "
            f"{sorted(v6_durations)[len(v6_durations)//2]:.2f}s"
        )

        print(
            f"V7 median duration  : "
            f"{sorted(durations)[len(durations)//2]:.2f}s"
        )

    # --------------------------------------------------------
    # Suspiciously short examples
    # --------------------------------------------------------

    short_segments = sorted(
        v7,
        key=lambda segment:
            segment["duration_seconds"]
    )[:20]

    print()
    print("=" * 70)
    print(
        "20 SHORTEST V7 SEGMENTS"
    )
    print("=" * 70)

    for segment in short_segments:

        detection = segment[
            "start_detection"
        ]

        print(
            f"{segment['duration_seconds']:>6.2f}s | "
            f"{segment['task']:<24} | "
            f"{detection['method']:<20} | "
            f"{','.join(detection['reasons'])}"
        )

    # --------------------------------------------------------
    # Longest examples
    # --------------------------------------------------------

    long_segments = sorted(
        v7,
        key=lambda segment:
            segment["duration_seconds"],
        reverse=True,
    )[:10]

    print()
    print("=" * 70)
    print(
        "10 LONGEST V7 SEGMENTS"
    )
    print("=" * 70)

    for segment in long_segments:

        detection = segment[
            "start_detection"
        ]

        print(
            f"{segment['duration_seconds']:>6.2f}s | "
            f"{segment['task']:<24} | "
            f"{detection['method']:<20} | "
            f"{','.join(detection['reasons'])}"
        )

    # --------------------------------------------------------
    # Missing anchors
    # --------------------------------------------------------

    if missing:

        print()
        print("=" * 70)
        print("MISSING COMPLETION ANCHORS")
        print("=" * 70)

        for item in missing[:20]:

            print(
                item["session"],
                item["chunk"],
                item["task"],
                item["index"],
            )

    print()
    print("=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()