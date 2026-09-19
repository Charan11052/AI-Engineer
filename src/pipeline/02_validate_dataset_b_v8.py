from pathlib import Path
import json
import statistics
from collections import Counter


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "outputs" / "dataset_b"

V8_FILE = OUTPUT_DIR / "dataset_b_segments_v8.jsonl"
V6_FILE = OUTPUT_DIR / "dataset_b_segments_v6.jsonl"


# ============================================================
# HELPERS
# ============================================================

def load_jsonl(path):
    records = []

    if not path.exists():
        return records

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    return records


def get_duration(seg):
    if "duration_seconds" in seg:
        return float(seg["duration_seconds"])

    start = (
        seg.get("start_timestamp_ms")
        or seg.get("start_ts_ms")
        or seg.get("start_time_ms")
    )

    end = (
        seg.get("end_timestamp_ms")
        or seg.get("end_ts_ms")
        or seg.get("end_time_ms")
    )

    if start is not None and end is not None:
        return max(0.0, (float(end) - float(start)) / 1000.0)

    return 0.0


def get_start_ts(seg):
    for key in (
        "start_timestamp_ms",
        "start_ts_ms",
        "start_time_ms",
    ):
        if key in seg and seg[key] is not None:
            return float(seg[key])

    return None


def get_end_ts(seg):
    for key in (
        "end_timestamp_ms",
        "end_ts_ms",
        "end_time_ms",
    ):
        if key in seg and seg[key] is not None:
            return float(seg[key])

    return None


def task_name(seg):
    return (
        seg.get("task")
        or seg.get("task_type")
        or seg.get("task_name")
        or "UNKNOWN"
    )


def confidence(seg):
    return seg.get("start_confidence", "unknown")


def method(seg):
    return seg.get(
        "start_detection_method",
        "unknown"
    )


def print_duration_buckets(durations):
    buckets = [
        ("<1s", lambda x: x < 1),
        ("1-2s", lambda x: 1 <= x < 2),
        ("2-5s", lambda x: 2 <= x < 5),
        ("5-10s", lambda x: 5 <= x < 10),
        ("10-30s", lambda x: 10 <= x < 30),
        ("30-60s", lambda x: 30 <= x < 60),
        ("60-120s", lambda x: 60 <= x <= 120),
        (">120s", lambda x: x > 120),
    ]

    for name, predicate in buckets:
        count = sum(predicate(x) for x in durations)
        print(f"{name:<10}: {count}")


def print_stats(name, durations):
    if not durations:
        print(f"{name}: no data")
        return

    print(f"{name}:")
    print(f"  count   : {len(durations)}")
    print(f"  avg     : {statistics.mean(durations):.2f}s")
    print(f"  median  : {statistics.median(durations):.2f}s")
    print(f"  min     : {min(durations):.2f}s")
    print(f"  max     : {max(durations):.2f}s")


# ============================================================
# LOAD
# ============================================================

print("=" * 70)
print("DATASET B V8 — SEGMENT VALIDATION")
print("=" * 70)

v8 = load_jsonl(V8_FILE)
v6 = load_jsonl(V6_FILE)

print()
print(f"V8 segments : {len(v8)}")
print(f"V6 segments : {len(v6)}")


if not v8:
    raise SystemExit(
        f"\nERROR: V8 output not found or empty:\n{V8_FILE}"
    )


# ============================================================
# BASIC VALIDATION
# ============================================================

durations = [get_duration(x) for x in v8]

print()
print("=" * 70)
print("V8 DURATION")
print("=" * 70)

print_stats("V8", durations)

print()
print("Duration buckets:")
print_duration_buckets(durations)


# ============================================================
# TASK DISTRIBUTION
# ============================================================

print()
print("=" * 70)
print("TASK DISTRIBUTION")
print("=" * 70)

tasks = Counter(task_name(x) for x in v8)

for task, count in tasks.most_common():
    print(f"{task:<30} {count}")


# ============================================================
# BUSINESS AREA
# ============================================================

print()
print("=" * 70)
print("BUSINESS AREAS")
print("=" * 70)

areas = Counter(
    x.get("business_area", "UNKNOWN")
    for x in v8
)

for area, count in areas.most_common():
    print(f"{area:<20} {count}")


# ============================================================
# START DETECTION
# ============================================================

print()
print("=" * 70)
print("START DETECTION METHODS")
print("=" * 70)

methods = Counter(method(x) for x in v8)

for name, count in methods.most_common():
    print(f"{name:<35} {count}")


print()
print("=" * 70)
print("START CONFIDENCE")
print("=" * 70)

conf = Counter(confidence(x) for x in v8)

for name, count in conf.most_common():
    print(f"{name:<15} {count}")


# ============================================================
# START → COMPLETION DISTANCE
# ============================================================

distances = []

for seg in v8:
    start = get_start_ts(seg)
    end = get_end_ts(seg)

    if start is None or end is None:
        continue

    distances.append(max(0.0, (end - start) / 1000.0))


print()
print("=" * 70)
print("START → COMPLETION DISTANCE")
print("=" * 70)

print_stats("Distance", distances)

if distances:
    for threshold in [1, 2, 5, 10, 20, 30, 45, 60]:
        count = sum(x <= threshold for x in distances)

        print(
            f"<= {threshold:>2}s : "
            f"{count:>3} / {len(distances):>3} "
            f"({100 * count / len(distances):.2f}%)"
        )


# ============================================================
# SHORTEST SEGMENTS
# ============================================================

print()
print("=" * 70)
print("20 SHORTEST V8 SEGMENTS")
print("=" * 70)

shortest = sorted(
    v8,
    key=get_duration
)[:20]

for seg in shortest:
    print(
        f"{get_duration(seg):6.2f}s | "
        f"{task_name(seg):25} | "
        f"{method(seg):25} | "
        f"{confidence(seg)}"
    )


# ============================================================
# LONGEST SEGMENTS
# ============================================================

print()
print("=" * 70)
print("20 LONGEST V8 SEGMENTS")
print("=" * 70)

longest = sorted(
    v8,
    key=get_duration,
    reverse=True
)[:20]

for seg in longest:
    print(
        f"{get_duration(seg):6.2f}s | "
        f"{task_name(seg):25} | "
        f"{method(seg):25} | "
        f"{confidence(seg)}"
    )


# ============================================================
# QUALITY FLAGS
# ============================================================

print()
print("=" * 70)
print("QUALITY FLAGS")
print("=" * 70)

zero_or_negative = sum(
    d <= 0 for d in durations
)

over_120 = sum(
    d > 120 for d in durations
)

very_short = sum(
    d < 2 for d in durations
)

short = sum(
    d < 5 for d in durations
)

print(f"Zero/negative duration : {zero_or_negative}")
print(f">120s segments         : {over_120}")
print(f"<2s segments           : {very_short}")
print(f"<5s segments           : {short}")


# ============================================================
# V6 COMPARISON
# ============================================================

if v6:

    v6_durations = [
        get_duration(x)
        for x in v6
    ]

    print()
    print("=" * 70)
    print("V6 → V8 COMPARISON")
    print("=" * 70)

    print_stats("V6", v6_durations)
    print()
    print_stats("V8", durations)

    if v6_durations and durations:
        v6_avg = statistics.mean(v6_durations)
        v8_avg = statistics.mean(durations)

        print()
        print(
            f"Average duration change : "
            f"{v6_avg:.2f}s → {v8_avg:.2f}s "
            f"({v8_avg - v6_avg:+.2f}s)"
        )

else:

    print()
    print("V6 output not found; skipping V6 comparison.")


# ============================================================
# FINAL SUMMARY
# ============================================================

print()
print("=" * 70)
print("V8 VALIDATION SUMMARY")
print("=" * 70)

print(f"Segments                    : {len(v8)}")
print(f"Average duration            : {statistics.mean(durations):.2f}s")
print(f"Median duration             : {statistics.median(durations):.2f}s")
print(f"Minimum duration            : {min(durations):.2f}s")
print(f"Maximum duration            : {max(durations):.2f}s")
print(f"Segments <5s                : {short}")
print(f"Segments >120s              : {over_120}")
print(f"Start-distance observations : {len(distances)}")

print()
print("VALIDATION COMPLETE")
print("=" * 70)