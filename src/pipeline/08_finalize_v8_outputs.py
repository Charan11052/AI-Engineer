"""
Create the final derived artifacts from the frozen V7/V8 outputs.

This script does not modify segmentation results. It only:
1. exports Dataset B V8 to the required root segments.jsonl format,
2. writes V8 validation/quality summaries,
3. writes the automation-opportunity heuristic output,
4. writes a final-selection manifest.
"""

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
A_DIR = ROOT / "outputs" / "dataset_a"
B_DIR = ROOT / "outputs" / "dataset_b"

V7_EVAL = A_DIR / "dataset_a_independent_segmentation_v7_evaluation.json"
V7_PRED = A_DIR / "dataset_a_predicted_segments_v7.jsonl"
V8_SEG = B_DIR / "dataset_b_segments_v8.jsonl"
ROI = B_DIR / "dataset_b_automation_roi_v8.json"
COVERAGE = B_DIR / "dataset_b_v8_coverage_interruptions.json"

FINAL_SEGMENTS = ROOT / "segments.jsonl"
VALIDATION = B_DIR / "dataset_b_v8_validation.json"
QUALITY = B_DIR / "dataset_b_v8_quality.json"
OPPORTUNITIES = B_DIR / "dataset_b_automation_opportunities_v8.json"
MANIFEST = ROOT / "outputs" / "final_submission_manifest.json"


def iso_utc(ms):
    return datetime.fromtimestamp(
        int(ms) / 1000,
        tz=timezone.utc,
    ).isoformat().replace("+00:00", "Z")


def load_jsonl(path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    segments = load_jsonl(V8_SEG)
    if len(segments) != 173:
        raise RuntimeError(
            f"Expected frozen V8 output to contain 173 segments; "
            f"found {len(segments)}"
        )

    durations = [float(x["duration_seconds"]) for x in segments]
    tasks = Counter(x["task"] for x in segments)
    areas = Counter(x["business_area"] for x in segments)
    methods = Counter(x.get("start_detection_method") for x in segments)
    confidence = Counter(x.get("start_confidence") for x in segments)

    # ------------------------------------------------------------
    # Required submission artifact
    # ------------------------------------------------------------
    with FINAL_SEGMENTS.open("w", encoding="utf-8") as f:
        for segment in segments:
            record = {
                "session_id": segment["session"],
                "start": iso_utc(segment["start_timestamp_ms"]),
                "end": iso_utc(segment["end_timestamp_ms"]),
                "label": segment["task"],
            }
            f.write(
                json.dumps(record, ensure_ascii=False)
                + "\n"
            )

    # ------------------------------------------------------------
    # Validation summary
    # ------------------------------------------------------------
    validation = {
        "version": "V8",
        "segments": len(segments),
        "average_duration_seconds": round(statistics.mean(durations), 4),
        "median_duration_seconds": round(statistics.median(durations), 4),
        "minimum_duration_seconds": round(min(durations), 4),
        "maximum_duration_seconds": round(max(durations), 4),
        "average_events_per_segment": round(
            statistics.mean(
                x.get("event_count", 0) for x in segments
            ),
            4,
        ),
        "task_distribution": dict(tasks),
        "business_area_distribution": dict(areas),
        "start_detection_methods": dict(methods),
        "start_confidence": dict(confidence),
        "zero_or_negative_duration": sum(x <= 0 for x in durations),
        "segments_under_2_seconds": sum(x < 2 for x in durations),
        "segments_under_5_seconds": sum(x < 5 for x in durations),
        "segments_over_120_seconds": sum(x > 120 for x in durations),
    }

    VALIDATION.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ------------------------------------------------------------
    # Quality summary
    # ------------------------------------------------------------
    quality = {
        "version": "V8",
        "segments": len(segments),
        "average_duration_seconds": round(statistics.mean(durations), 4),
        "median_duration_seconds": round(statistics.median(durations), 4),
        "minimum_duration_seconds": round(min(durations), 4),
        "maximum_duration_seconds": round(max(durations), 4),
        "average_events_per_segment": round(
            statistics.mean(
                x.get("event_count", 0) for x in segments
            ),
            4,
        ),
        "start_detection_methods": dict(methods),
        "confidence": dict(confidence),
        "quality_flags": {
            "zero_or_negative_duration": sum(
                x <= 0 for x in durations
            ),
            "under_5_seconds": sum(
                x < 5 for x in durations
            ),
            "under_10_seconds": sum(
                x < 10 for x in durations
            ),
            "over_120_seconds": sum(
                x > 120 for x in durations
            ),
            "low_confidence": confidence.get("low", 0),
        },
    }

    QUALITY.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ------------------------------------------------------------
    # Automation opportunity score
    # ------------------------------------------------------------
    by_task = defaultdict(list)
    for x in segments:
        by_task[x["task"]].append(x)

    opportunity_results = []

    for task, items in by_task.items():
        durations_task = [
            float(x["duration_seconds"]) for x in items
        ]
        count = len(items)
        avg = statistics.mean(durations_task)
        total = sum(durations_task)
        low = sum(
            x.get("start_confidence") == "low"
            for x in items
        )

        frequency_score = min(10.0, count / 3.0)
        duration_score = min(10.0, avg / 4.0)
        effort_score = min(10.0, total / 300.0)
        confidence_penalty = min(5.0, low * 0.5)

        score = max(
            0.0,
            frequency_score
            + duration_score
            + effort_score
            - confidence_penalty,
        )

        opportunity_results.append({
            "task": task,
            "executions": count,
            "average_duration_seconds": round(avg, 2),
            "total_duration_seconds": round(total, 2),
            "low_confidence_starts": low,
            "frequency_score": round(frequency_score, 2),
            "duration_score": round(duration_score, 2),
            "cumulative_effort_score": round(effort_score, 2),
            "confidence_penalty": round(confidence_penalty, 2),
            "automation_opportunity_score": round(score, 2),
            "score_scale": "0-30",
        })

    opportunity_results.sort(
        key=lambda x: x["automation_opportunity_score"],
        reverse=True,
    )

    opportunity_output = {
        "method": "V8 explainable automation opportunity heuristic",
        "segments": len(segments),
        "formula": (
            "min(10,count/3) + min(10,avg_duration/4) + "
            "min(10,total_duration/300) - "
            "min(5,low_confidence_starts*0.5)"
        ),
        "note": (
            "Prioritization heuristic only; not a predictive model "
            "or automation-success probability."
        ),
        "results": opportunity_results,
    }

    OPPORTUNITIES.write_text(
        json.dumps(
            opportunity_output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------------
    # Final manifest
    # ------------------------------------------------------------
    manifest = {
        "dataset_a_final": {
            "prediction_file": str(V7_PRED.relative_to(ROOT)),
            "evaluation_file": str(V7_EVAL.relative_to(ROOT)),
        },
        "dataset_b_final": {
            "segments_file": str(V8_SEG.relative_to(ROOT)),
            "required_submission_file": str(
                FINAL_SEGMENTS.relative_to(ROOT)
            ),
            "roi_file": str(ROI.relative_to(ROOT)),
            "coverage_file": str(COVERAGE.relative_to(ROOT)),
            "validation_file": str(
                VALIDATION.relative_to(ROOT)
            ),
            "quality_file": str(QUALITY.relative_to(ROOT)),
            "automation_opportunities_file": str(
                OPPORTUNITIES.relative_to(ROOT)
            ),
        },
        "required_submission": "segments.jsonl",
        "frozen_versions": {
            "dataset_a": "V7",
            "dataset_b": "V8",
        },
    }

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 70)
    print("FINAL OUTPUTS CREATED")
    print("=" * 70)
    print(f"segments.jsonl: {FINAL_SEGMENTS}")
    print(f"V8 validation : {VALIDATION}")
    print(f"V8 quality    : {QUALITY}")
    print(f"Opportunities : {OPPORTUNITIES}")
    print(f"Manifest      : {MANIFEST}")
    print("=" * 70)


if __name__ == "__main__":
    main()
