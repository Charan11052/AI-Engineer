from pathlib import Path
import json


PROJECT_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_independent_segmentation_v7_evaluation.json"
)


def print_sessions(sessions, title):
    print()
    print("=" * 130)
    print(title)
    print("=" * 130)

    for i, s in enumerate(sessions, 1):
        print(
            f"{i:2}. "
            f"F1={s['f1']:.3f}  "
            f"P={s['precision']:.3f}  "
            f"R={s['recall']:.3f}  "
            f"pred={s['predicted_segments']:3}  "
            f"gt={s['ground_truth_executions']:3}  "
            f"matched={s['matched_segments']:3}  "
            f"FP={s['false_positive_predictions']:3}  "
            f"missed={s['missed_ground_truth_executions']:3}  "
            f"session={s['session_id']}"
        )


def main():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    sessions = data["per_session"]

    worst = sorted(
        sessions,
        key=lambda s: s["f1"]
    )[:15]

    best = sorted(
        sessions,
        key=lambda s: s["f1"],
        reverse=True
    )[:15]

    print_sessions(
        worst,
        "V7 SESSION PERFORMANCE — WORST 15"
    )

    print_sessions(
        best,
        "V7 SESSION PERFORMANCE — BEST 15"
    )


if __name__ == "__main__":
    main()