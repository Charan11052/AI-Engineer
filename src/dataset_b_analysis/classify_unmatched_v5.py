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

COMPACT_FILE = (
    BASE_DIR
    / "outputs"
    / "coverage_full.txt"
)


# ============================================================
# READ COMPACT REPORT
# ============================================================

def read_compact_report():

    with open(COMPACT_FILE, "rb") as f:
        raw = f.read()

    # Detect UTF-16 / UTF-8 automatically
    if (
        raw.startswith(b"\xff\xfe")
        or raw.startswith(b"\xfe\xff")
    ):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig")

    return text.splitlines()


# ============================================================
# PARSE UNMATCHED COMPLETIONS
# ============================================================

def parse_unmatched():

    lines = read_compact_report()

    results = []

    current = None

    for line in lines:

        line = line.strip()

        # Example:
        # [1/22] LOGISTICS_ORDER
        if (
            line.startswith("[")
            and "/" in line
            and "]" in line
        ):

            if current is not None:
                results.append(current)

            task = line.split("]", 1)[1].strip()

            current = {
                "task": task
            }

            continue

        if current is None:
            continue

        if line.startswith("Session"):
            current["session"] = (
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("Chunk"):
            current["chunk"] = (
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("Timestamp"):
            current["timestamp_ms"] = int(
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("Text"):
            current["text"] = (
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("NEAREST V5 SEGMENT BEFORE"):
            current["reading_before"] = True
            current["reading_after"] = False

        elif line.startswith("NEAREST V5 SEGMENT AFTER"):
            current["reading_before"] = False
            current["reading_after"] = True

        elif line.startswith("segment_id"):

            if current.get("reading_before"):

                current["before_id"] = (
                    line.split(":", 1)[1].strip()
                )

            elif current.get("reading_after"):

                current["after_id"] = (
                    line.split(":", 1)[1].strip()
                )

        elif line.startswith("gap"):

            value = line.split(":", 1)[1].strip()

            try:
                gap = float(
                    value.replace("s", "")
                )
            except ValueError:
                continue

            if current.get("reading_before"):

                current["gap_before"] = gap

            elif current.get("reading_after"):

                current["gap_after"] = gap

    if current is not None:
        results.append(current)

    return results


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

            if line:
                segments.append(
                    json.loads(line)
                )

    return segments


# ============================================================
# CLASSIFICATION
# ============================================================

def classify(item):

    before = item.get(
        "gap_before",
        float("inf")
    )

    after = item.get(
        "gap_after",
        float("inf")
    )

    nearest_gap = min(
        before,
        after
    )

    # --------------------------------------------------------
    # Very close to an existing V5 segment
    # --------------------------------------------------------

    if nearest_gap <= 1.0:
        return "BOUNDARY_ARTIFACT"

    # --------------------------------------------------------
    # Large gap = likely missing execution
    # --------------------------------------------------------

    if nearest_gap > 5.0:
        return "LIKELY_MISSING_EXECUTION"

    # --------------------------------------------------------
    # Middle range needs manual inspection
    # --------------------------------------------------------

    return "NEEDS_REVIEW"


# ============================================================
# MAIN
# ============================================================

def main():

    unmatched = parse_unmatched()
    segments = load_segments()

    print("=" * 80)
    print("V5 UNMATCHED COMPLETION CLASSIFICATION")
    print("=" * 80)

    print()
    print(
        f"V5 segments          : {len(segments)}"
    )

    print(
        f"Unmatched completions: {len(unmatched)}"
    )

    # --------------------------------------------------------
    # Classify
    # --------------------------------------------------------

    classified = defaultdict(list)

    for item in unmatched:

        category = classify(item)

        classified[category].append(item)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("SUMMARY")
    print("-" * 80)

    for category in [
        "BOUNDARY_ARTIFACT",
        "NEEDS_REVIEW",
        "LIKELY_MISSING_EXECUTION"
    ]:

        items = classified[category]

        print(
            f"{category:<28}: "
            f"{len(items)}"
        )

    # --------------------------------------------------------
    # Detailed output
    # --------------------------------------------------------

    for category in [
        "BOUNDARY_ARTIFACT",
        "NEEDS_REVIEW",
        "LIKELY_MISSING_EXECUTION"
    ]:

        items = classified[category]

        print()
        print("=" * 80)
        print(category)
        print("=" * 80)

        if not items:
            print("None")
            continue

        for i, item in enumerate(
            items,
            start=1
        ):

            before = item.get(
                "gap_before"
            )

            after = item.get(
                "gap_after"
            )

            nearest = min(
                x for x in [
                    before,
                    after
                ]
                if x is not None
            )

            print()
            print(
                f"[{i}] {item.get('task', '')}"
            )

            print(
                f"Session   : "
                f"{item.get('session', '')}"
            )

            print(
                f"Chunk     : "
                f"{item.get('chunk', '')}"
            )

            print(
                f"Timestamp : "
                f"{item.get('timestamp_ms', '')}"
            )

            print(
                f"Text      : "
                f"{item.get('text', '')[:180]}"
            )

            print(
                f"Gap before: "
                f"{before if before is not None else 'NONE'} s"
            )

            print(
                f"Gap after : "
                f"{after if after is not None else 'NONE'} s"
            )

            print(
                f"Nearest   : "
                f"{nearest:.2f} s"
            )

    # --------------------------------------------------------
    # Task counts for likely missing executions
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("LIKELY MISSING EXECUTIONS BY TASK")
    print("=" * 80)

    task_counts = defaultdict(int)

    for item in classified[
        "LIKELY_MISSING_EXECUTION"
    ]:

        task_counts[
            item.get("task", "UNKNOWN")
        ] += 1

    if task_counts:

        for task in sorted(task_counts):

            print(
                f"{task:<28}: "
                f"{task_counts[task]}"
            )

    else:

        print("None")

    print()
    print("=" * 80)
    print("END")
    print("=" * 80)


if __name__ == "__main__":
    main()