import json
from pathlib import Path
from collections import defaultdict


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

SEGMENTS_FILE = (
    BASE_DIR
    / "outputs"
    / "dataset_b_segments_v6.jsonl"
)

COVERAGE_FILE = (
    BASE_DIR
    / "outputs"
    / "coverage_full.txt"
)


# ============================================================
# LOAD V5 SEGMENTS
# ============================================================

def load_segments():

    segments = []

    with open(
        SEGMENTS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            segments.append(json.loads(line))

    return segments


# ============================================================
# READ COVERAGE FILE
#
# PowerShell may have written coverage_full.txt as UTF-16,
# while the V5 JSONL file is UTF-8.
#
# Detect the encoding automatically.
# ============================================================

def read_coverage_file():

    with open(
        COVERAGE_FILE,
        "rb"
    ) as f:

        raw_data = f.read()

    # UTF-16 with BOM
    if (
        raw_data.startswith(b"\xff\xfe")
        or raw_data.startswith(b"\xfe\xff")
    ):
        text = raw_data.decode("utf-16")

    else:
        text = raw_data.decode("utf-8-sig")

    return text.splitlines()


# ============================================================
# PARSE UNMATCHED COMPLETIONS
# ============================================================

def parse_unmatched():

    results = []

    lines = read_coverage_file()

    in_section = False
    current = {}

    for line in lines:

        line = line.rstrip()

        # Start of unmatched section
        if line == "UNMATCHED COMPLETIONS":
            in_section = True
            continue

        if not in_section:
            continue

        # New record
        if (
            line.startswith("[")
            and line.endswith("]")
        ):

            if current:
                results.append(current)

            current = {}
            continue

        # Stop if another major section starts
        if line == "SANITY CHECK":
            break

        if line.startswith("Session"):
            current["session"] = (
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("Chunk"):
            current["chunk"] = (
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("Raw index"):
            current["raw_index"] = int(
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("Timestamp"):
            current["timestamp_ms"] = int(
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("Task"):
            current["task"] = (
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("Text"):
            current["text"] = (
                line.split(":", 1)[1].strip()
            )

    # Add final record
    if current:
        results.append(current)

    return results


# ============================================================
# FIND NEAREST V5 SEGMENTS
# ============================================================

def find_nearest_segments(
    completion,
    segment_groups
):

    key = (
        completion["session"],
        completion["chunk"],
        completion["task"],
    )

    candidates = segment_groups.get(key, [])

    timestamp = completion["timestamp_ms"]

    before = None
    after = None

    # --------------------------------------------------------
    # Find nearest segment BEFORE completion
    # --------------------------------------------------------

    for segment in candidates:

        end_ts = segment.get(
            "end_timestamp_ms"
        )

        if end_ts is None:
            continue

        if end_ts < timestamp:

            if (
                before is None
                or end_ts > before["end_timestamp_ms"]
            ):
                before = segment

    # --------------------------------------------------------
    # Find nearest segment AFTER completion
    # --------------------------------------------------------

    for segment in candidates:

        start_ts = segment.get(
            "start_timestamp_ms"
        )

        if start_ts is None:
            continue

        if start_ts > timestamp:

            if (
                after is None
                or start_ts < after["start_timestamp_ms"]
            ):
                after = segment

    return before, after


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("UNMATCHED V5 COMPLETIONS - COMPACT ANALYSIS")
    print("=" * 80)

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    segments = load_segments()

    unmatched = parse_unmatched()

    print()
    print(f"V5 segments          : {len(segments)}")
    print(f"Unmatched completions: {len(unmatched)}")

    # --------------------------------------------------------
    # Group V5 segments
    # --------------------------------------------------------

    segment_groups = defaultdict(list)

    for segment in segments:

        key = (
            str(segment["session"]),
            str(segment["chunk"]),
            segment["task"],
        )

        segment_groups[key].append(segment)

    # Sort each group by start timestamp

    for key in segment_groups:

        segment_groups[key].sort(
            key=lambda x: x.get(
                "start_timestamp_ms",
                0
            )
        )

    # --------------------------------------------------------
    # Analyze each unmatched completion
    # --------------------------------------------------------

    for i, completion in enumerate(
        unmatched,
        start=1
    ):

        before, after = find_nearest_segments(
            completion,
            segment_groups
        )

        print()
        print("-" * 80)

        print(
            f"[{i}/{len(unmatched)}] "
            f"{completion.get('task', 'UNKNOWN')}"
        )

        print(
            f"Session   : "
            f"{completion.get('session', '')}"
        )

        print(
            f"Chunk     : "
            f"{completion.get('chunk', '')}"
        )

        print(
            f"Raw index : "
            f"{completion.get('raw_index', '')}"
        )

        print(
            f"Timestamp : "
            f"{completion.get('timestamp_ms', '')}"
        )

        print(
            f"Text      : "
            f"{completion.get('text', '')[:300]}"
        )

        # ----------------------------------------------------
        # BEFORE
        # ----------------------------------------------------

        if before:

            gap_before = (
                completion["timestamp_ms"]
                - before["end_timestamp_ms"]
            ) / 1000

            print()
            print("NEAREST V5 SEGMENT BEFORE")

            print(
                f"segment_id : "
                f"{before.get('segment_id', '')}"
            )

            print(
                f"start      : "
                f"{before.get('start_timestamp_ms', '')}"
            )

            print(
                f"end        : "
                f"{before.get('end_timestamp_ms', '')}"
            )

            print(
                f"duration   : "
                f"{before.get('duration_seconds', 0):.2f}s"
            )

            print(
                f"task       : "
                f"{before.get('task', '')}"
            )

            print(
                f"gap        : "
                f"{gap_before:.2f}s"
            )

        else:

            print()
            print("NEAREST V5 SEGMENT BEFORE : NONE")

        # ----------------------------------------------------
        # AFTER
        # ----------------------------------------------------

        if after:

            gap_after = (
                after["start_timestamp_ms"]
                - completion["timestamp_ms"]
            ) / 1000

            print()
            print("NEAREST V5 SEGMENT AFTER")

            print(
                f"segment_id : "
                f"{after.get('segment_id', '')}"
            )

            print(
                f"start      : "
                f"{after.get('start_timestamp_ms', '')}"
            )

            print(
                f"end        : "
                f"{after.get('end_timestamp_ms', '')}"
            )

            print(
                f"duration   : "
                f"{after.get('duration_seconds', 0):.2f}s"
            )

            print(
                f"task       : "
                f"{after.get('task', '')}"
            )

            print(
                f"gap        : "
                f"{gap_after:.2f}s"
            )

        else:

            print()
            print("NEAREST V5 SEGMENT AFTER : NONE")

    # --------------------------------------------------------
    # END
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("END")
    print("=" * 80)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()