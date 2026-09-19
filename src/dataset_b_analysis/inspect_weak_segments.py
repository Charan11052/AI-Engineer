import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

QUALITY_FILE = BASE_DIR / "outputs" / "dataset_b_segment_quality.json"
SEGMENTS_FILE = BASE_DIR / "outputs" / "dataset_b_segments_v6.jsonl"

with open(QUALITY_FILE, "r", encoding="utf-8") as f:
    quality = json.load(f)

weak = quality.get("potentially_weak_segments", [])

segments = {}

with open(SEGMENTS_FILE, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            seg = json.loads(line)
            segments[seg["segment_id"]] = seg

print("=" * 70)
print("DATASET B — WEAK SEGMENT INSPECTION")
print("=" * 70)

print(f"Weak segments reported : {len(weak)}")
print()

for item in weak[:30]:
    segment_id = item["segment_id"]

    seg = segments.get(segment_id)

    if not seg:
        continue

    print("-" * 70)
    print("Segment :", segment_id)
    print("Task    :", seg["task"])
    print("Duration:", round(seg["duration_seconds"], 3), "seconds")
    print("Events  :", seg["event_count"])
    print("Apps    :", ", ".join(seg["applications"]))
    print("Reason  :", item.get("reason"))

    print("Completion evidence:")
    print(seg.get("completion_evidence", "")[:500])

    print("Event types:")
    print(seg.get("event_type_counts", {}))

print()
print("=" * 70)
print("Showing first 30 weak segments")
print("=" * 70)