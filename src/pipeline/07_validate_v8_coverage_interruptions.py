import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]

RAW_ROOT = ROOT / "data" / "dataset_b"
V8_FILE = ROOT / "outputs" / "dataset_b" / "dataset_b_segments_v8.jsonl"
OUT_FILE = ROOT / "outputs" / "dataset_b" / "dataset_b_v8_coverage_interruptions.json"


def load_v8_segments():
    segments = []

    with open(V8_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                segments.append(json.loads(line))

    return segments


def load_raw_events():
    """
    Load raw Dataset B events grouped by chunk.

    The important identifier is the chunk name because V8
    explicitly stores the source chunk for every segment.
    """
    events_by_chunk = defaultdict(list)

    files = sorted(RAW_ROOT.rglob("events.jsonl"))

    total_events = 0

    for path in files:
        chunk = path.parent.name

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = (
                    event.get("timestamp_ms")
                    or event.get("timestamp")
                    or event.get("time_ms")
                )

                if ts is None:
                    continue

                try:
                    ts = int(float(ts))
                except Exception:
                    continue

                event["_timestamp_ms"] = ts
                events_by_chunk[chunk].append(event)
                total_events += 1

    return events_by_chunk, files, total_events


def merge_intervals(intervals):
    """
    Merge overlapping/touching time intervals.
    """
    if not intervals:
        return []

    intervals = sorted(intervals)

    merged = [list(intervals[0])]

    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    return merged


def interval_duration(intervals):
    return sum(end - start for start, end in intervals)


def calculate_coverage(segments, events_by_chunk):
    """
    Calculate V8 temporal coverage relative to the raw active
    time span of each chunk.

    IMPORTANT:
    Coverage is calculated chunk-by-chunk so unrelated sessions
    cannot accidentally be merged.
    """

    raw_intervals = []
    segment_intervals = []

    chunks_used = set()
    chunks_missing = set()

    for chunk, events in events_by_chunk.items():

        if not events:
            continue

        timestamps = [e["_timestamp_ms"] for e in events]

        raw_start = min(timestamps)
        raw_end = max(timestamps)

        if raw_end > raw_start:
            raw_intervals.append((raw_start, raw_end))

    for seg in segments:

        chunk = seg.get("chunk")

        if not chunk:
            continue

        chunks_used.add(chunk)

        start = seg.get("start_timestamp_ms")
        end = seg.get("end_timestamp_ms")

        if start is None or end is None:
            continue

        start = int(start)
        end = int(end)

        if end > start:
            segment_intervals.append((chunk, start, end))

        if chunk not in events_by_chunk:
            chunks_missing.add(chunk)

    # Calculate raw active duration chunk by chunk.
    raw_duration_ms = 0

    for chunk, events in events_by_chunk.items():

        if not events:
            continue

        timestamps = [e["_timestamp_ms"] for e in events]

        start = min(timestamps)
        end = max(timestamps)

        if end > start:
            raw_duration_ms += end - start

    # Calculate covered duration chunk by chunk.
    covered_duration_ms = 0

    segments_by_chunk = defaultdict(list)

    for chunk, start, end in segment_intervals:
        segments_by_chunk[chunk].append((start, end))

    for chunk, intervals in segments_by_chunk.items():

        merged = merge_intervals(intervals)

        covered_duration_ms += interval_duration(merged)

    coverage = (
        covered_duration_ms / raw_duration_ms
        if raw_duration_ms > 0
        else 0
    )

    return {
        "raw_duration_ms": raw_duration_ms,
        "covered_duration_ms": covered_duration_ms,
        "coverage_fraction": coverage,
        "coverage_percent": coverage * 100,
        "chunks_with_segments": len(chunks_used),
        "missing_segment_chunks": sorted(chunks_missing),
    }


def analyze_ab_a(segments):
    """
    Detect A -> B -> A task patterns within the same session.
    """

    by_session = defaultdict(list)

    for seg in segments:
        by_session[seg.get("session")].append(seg)

    patterns = []

    for session, items in by_session.items():

        items.sort(key=lambda x: x["start_timestamp_ms"])

        for i in range(1, len(items) - 1):

            a = items[i - 1].get("task")
            b = items[i].get("task")
            c = items[i + 1].get("task")

            if a and b and c and a == c and a != b:

                patterns.append({
                    "session": session,
                    "tasks": [a, b, c],
                    "segments": [
                        items[i - 1]["segment_id"],
                        items[i]["segment_id"],
                        items[i + 1]["segment_id"],
                    ],
                })

    return patterns


def check_overlaps(segments):
    """
    Check whether V8 segments overlap within the same chunk.
    """

    by_chunk = defaultdict(list)

    for seg in segments:

        chunk = seg.get("chunk")

        start = seg.get("start_timestamp_ms")
        end = seg.get("end_timestamp_ms")

        if chunk and start is not None and end is not None:
            by_chunk[chunk].append(
                (
                    int(start),
                    int(end),
                    seg["segment_id"],
                )
            )

    overlaps = []

    for chunk, items in by_chunk.items():

        items.sort()

        for i in range(1, len(items)):

            prev_start, prev_end, prev_id = items[i - 1]
            start, end, seg_id = items[i]

            if start < prev_end:

                overlaps.append({
                    "chunk": chunk,
                    "previous_segment": prev_id,
                    "current_segment": seg_id,
                    "overlap_seconds": (prev_end - start) / 1000,
                })

    return overlaps


def main():

    print("=" * 70)
    print("DATASET B V8 COVERAGE + INTERRUPTION VALIDATION")
    print("=" * 70)

    segments = load_v8_segments()

    print(f"V8 segments: {len(segments)}")

    events_by_chunk, raw_files, total_events = load_raw_events()

    print(f"Raw events.jsonl files: {len(raw_files)}")
    print(f"Raw events loaded: {total_events}")
    print(f"Raw chunks: {len(events_by_chunk)}")

    # ------------------------------------------------------------
    # COVERAGE
    # ------------------------------------------------------------

    coverage = calculate_coverage(
        segments,
        events_by_chunk
    )

    print()
    print("-" * 70)
    print("RAW ACTIVE-TIME COVERAGE")
    print("-" * 70)

    raw_min = coverage["raw_duration_ms"] / 60000
    covered_min = coverage["covered_duration_ms"] / 60000

    print(f"Raw active span:      {raw_min:.2f} min")
    print(f"V8 covered time:      {covered_min:.2f} min")
    print(f"Coverage:             {coverage['coverage_percent']:.2f}%")
    print(
        f"Chunks with segments: "
        f"{coverage['chunks_with_segments']}"
    )

    if coverage["missing_segment_chunks"]:
        print(
            "WARNING: V8 chunks missing from raw data:",
            coverage["missing_segment_chunks"]
        )

    # ------------------------------------------------------------
    # A -> B -> A
    # ------------------------------------------------------------

    patterns = analyze_ab_a(segments)

    print()
    print("-" * 70)
    print("A -> B -> A INTERRUPTION ANALYSIS")
    print("-" * 70)

    sessions = set(p["session"] for p in patterns)

    print(f"Sessions containing A->B->A: {len(sessions)}")
    print(f"A->B->A patterns:             {len(patterns)}")

    for p in patterns[:20]:

        print(
            f"{p['session']}: "
            f"{' -> '.join(p['tasks'])}"
        )

    # ------------------------------------------------------------
    # OVERLAPS
    # ------------------------------------------------------------

    overlaps = check_overlaps(segments)

    print()
    print("-" * 70)
    print("SEGMENT OVERLAP CHECK")
    print("-" * 70)

    print(f"Overlapping segment pairs: {len(overlaps)}")

    if overlaps:
        for item in overlaps[:10]:
            print(item)

    # ------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------

    result = {
        "v8_segments": len(segments),
        "raw_event_files": len(raw_files),
        "raw_events": total_events,

        "coverage": coverage,

        "a_b_a": {
            "sessions": len(sessions),
            "patterns": len(patterns),
            "examples": patterns[:20],
        },

        "overlap_check": {
            "overlapping_pairs": len(overlaps),
            "examples": overlaps[:20],
        },
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(
        OUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print(f"Saved: {OUT_FILE}")

    print()
    print("=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()