"""
Final Dataset B V8 automation-opportunity scoring.

This is an explainable heuristic, not a predictive model.
All inputs and outputs are kept under outputs/dataset_b.
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "dataset_b"
SEGMENTS_FILE = OUTPUT_DIR / "dataset_b_segments_v8.jsonl"
OUTPUT_FILE = OUTPUT_DIR / "dataset_b_automation_opportunities_v8.json"


def main():
    segments = []

    with SEGMENTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                segments.append(json.loads(line))

    if not segments:
        raise RuntimeError(f"No V8 segments found: {SEGMENTS_FILE}")

    by_task = defaultdict(list)
    for segment in segments:
        by_task[segment["task"]].append(segment)

    results = []

    for task, items in sorted(by_task.items()):
        count = len(items)
        durations = [float(x["duration_seconds"]) for x in items]
        avg_duration = statistics.mean(durations)
        total_duration = sum(durations)
        low_confidence = sum(
            x.get("start_confidence") == "low"
            for x in items
        )

        frequency_score = min(10.0, count / 3.0)
        duration_score = min(10.0, avg_duration / 4.0)
        effort_score = min(10.0, total_duration / 300.0)
        confidence_penalty = min(5.0, low_confidence * 0.5)

        total_score = max(
            0.0,
            frequency_score
            + duration_score
            + effort_score
            - confidence_penalty
        )

        if count >= 20:
            frequency_level = "high"
        elif count >= 10:
            frequency_level = "moderate"
        else:
            frequency_level = "low"

        if avg_duration >= 30:
            duration_level = "high"
        elif avg_duration >= 15:
            duration_level = "moderate"
        else:
            duration_level = "low"

        if total_duration >= 600:
            effort_level = "high"
        elif total_duration >= 300:
            effort_level = "moderate"
        else:
            effort_level = "low"

        results.append({
            "task": task,
            "executions": count,
            "average_duration_seconds": round(avg_duration, 2),
            "total_duration_seconds": round(total_duration, 2),
            "low_confidence_starts": low_confidence,
            "frequency_score": round(frequency_score, 2),
            "duration_score": round(duration_score, 2),
            "cumulative_effort_score": round(effort_score, 2),
            "confidence_penalty": round(confidence_penalty, 2),
            "automation_opportunity_score": round(total_score, 2),
            "score_scale": "0-30",
            "factors": {
                "frequency": frequency_level,
                "execution_time": duration_level,
                "cumulative_effort": effort_level,
                "confidence_risk": (
                    "present" if low_confidence else "none"
                ),
            },
        })

    results.sort(
        key=lambda x: x["automation_opportunity_score"],
        reverse=True,
    )

    output = {
        "method": "V8 explainable automation opportunity heuristic",
        "input": str(SEGMENTS_FILE),
        "segments": len(segments),
        "scoring_note": (
            "Heuristic prioritization only; not a predictive model "
            "and not an automation success probability."
        ),
        "formula": (
            "min(10,count/3) + min(10,avg_duration/4) + "
            "min(10,total_duration/300) - "
            "min(5,low_confidence_starts*0.5)"
        ),
        "results": results,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("=" * 70)
    print("DATASET B V8 AUTOMATION OPPORTUNITY SCORING")
    print("=" * 70)
    print(f"Segments: {len(segments)}")
    print()

    for i, result in enumerate(results, 1):
        print(
            f"{i}. {result['task']:25s} "
            f"{result['automation_opportunity_score']:5.2f}/30"
        )

    print()
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
