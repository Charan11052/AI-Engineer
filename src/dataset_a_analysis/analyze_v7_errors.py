from pathlib import Path
import json


PROJECT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_DIR / "outputs" / "dataset_a"

PREDICTIONS_FILE = (
    OUTPUT_DIR /
    "dataset_a_predicted_segments_v7.jsonl"
)

GT_FILE = (
    OUTPUT_DIR /
    "dataset_a_execution_intervals.jsonl"
)


IOU_THRESHOLD = 0.5


def parse_ts(ts):
    if not ts:
        return None

    from datetime import datetime

    return (
        datetime.fromisoformat(
            ts.replace("Z", "+00:00")
        ).timestamp()
        * 1000
    )


def interval_iou(a_start, a_end, b_start, b_end):

    if a_start is None or b_start is None:
        return 0.0

    if a_end is None or b_end is None:
        return 0.0

    intersection_start = max(
        a_start,
        b_start
    )

    intersection_end = min(
        a_end,
        b_end
    )

    intersection = max(
        0.0,
        intersection_end - intersection_start
    )

    union_start = min(
        a_start,
        b_start
    )

    union_end = max(
        a_end,
        b_end
    )

    union = union_end - union_start

    if union <= 0:
        return 0.0

    return intersection / union


def load_jsonl(path):

    records = []

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if line:
                records.append(
                    json.loads(line)
                )

    return records


def get_interval(record):
    start = record.get("start_timestamp_ms")
    end = record.get("end_timestamp_ms")

    if start is None:
        start = parse_ts(
            record.get("start_timestamp") or record.get("start_ts")
        )

    if end is None:
        end = parse_ts(
            record.get("end_timestamp") or record.get("end_ts")
        )

    return start, end

def group_by_session(records):

    grouped = {}

    for record in records:

        session = record.get(
            "session_id"
        )

        if session:
            grouped.setdefault(
                session,
                []
            ).append(record)

    for session in grouped:

        grouped[session].sort(
            key=lambda x:
                x.get("start_timestamp_ms") or 0
        )

    return grouped


def find_best_match(
    prediction,
    gt_records
):

    p_start, p_end = get_interval(
        prediction
    )

    best = None
    best_iou = 0.0

    for gt in gt_records:

        g_start, g_end = get_interval(gt)

        iou = interval_iou(
            p_start,
            p_end,
            g_start,
            g_end
        )

        if iou > best_iou:

            best_iou = iou
            best = gt

    return best, best_iou


def main():

    predictions = load_jsonl(
        PREDICTIONS_FILE
    )

    gt_records = load_jsonl(
        GT_FILE
    )

    predictions_by_session = group_by_session(
        predictions
    )

    gt_by_session = group_by_session(
        gt_records
    )

    matched_gt = set()

    false_positive_categories = {
        "hard_gap": 0,
        "checkpoint_transition_burst": 0,
        "medium_gap_transition_burst": 0,
        "other": 0,
    }

    missed_categories = {
        "no_overlapping_prediction": 0,
        "weak_overlap": 0,
    }

    false_positive_examples = []
    missed_examples = []

    # ========================================================
    # MATCH PREDICTIONS → GT
    # ========================================================

    prediction_matches = []

    for session_id, preds in predictions_by_session.items():

        gt_session = gt_by_session.get(
            session_id,
            []
        )

        for prediction in preds:

            best_gt = None
            best_iou = 0.0
            best_index = None

            p_start, p_end = get_interval(
                prediction
            )

            for index, gt in enumerate(
                gt_session
            ):

                g_start, g_end = get_interval(
                    gt
                )

                iou = interval_iou(
                    p_start,
                    p_end,
                    g_start,
                    g_end
                )

                if iou > best_iou:

                    best_iou = iou
                    best_gt = gt
                    best_index = index

            matched = (
                best_iou >= IOU_THRESHOLD
                and best_gt is not None
            )

            if matched:

                gt_key = (
                    session_id,
                    best_index
                )

                matched_gt.add(
                    gt_key
                )

            else:

                reason = prediction.get(
                    "boundary_before",
                    "other"
                )

                if (
                    reason
                    not in false_positive_categories
                ):
                    reason = "other"

                false_positive_categories[
                    reason
                ] += 1

                if len(
                    false_positive_examples
                ) < 30:

                    false_positive_examples.append({
                        "session_id": session_id,
                        "prediction": prediction,
                        "best_iou": best_iou,
                        "nearest_gt": best_gt,
                    })

            prediction_matches.append({
                "prediction": prediction,
                "matched": matched,
                "best_gt": best_gt,
                "best_iou": best_iou,
            })

    # ========================================================
    # MISSED GT
    # ========================================================

    for session_id, gt_session in gt_by_session.items():

        preds = predictions_by_session.get(
            session_id,
            []
        )

        for index, gt in enumerate(
            gt_session
        ):

            gt_key = (
                session_id,
                index
            )

            if gt_key in matched_gt:
                continue

            g_start, g_end = get_interval(
                gt
            )

            best_iou = 0.0
            best_prediction = None

            for prediction in preds:

                p_start, p_end = get_interval(
                    prediction
                )

                iou = interval_iou(
                    p_start,
                    p_end,
                    g_start,
                    g_end
                )

                if iou > best_iou:

                    best_iou = iou
                    best_prediction = prediction

            if best_iou == 0:

                category = (
                    "no_overlapping_prediction"
                )

            else:

                category = "weak_overlap"

            missed_categories[
                category
            ] += 1

            if len(
                missed_examples
            ) < 30:

                missed_examples.append({
                    "session_id": session_id,
                    "gt": gt,
                    "best_iou": best_iou,
                    "best_prediction": best_prediction,
                })

    # ========================================================
    # OUTPUT
    # ========================================================

    print("=" * 100)
    print("DATASET A — V7 ERROR ANALYSIS")
    print("=" * 100)

    print(
        f"Predictions : {len(predictions)}"
    )

    print(
        f"GT records  : {len(gt_records)}"
    )

    print("\nFALSE POSITIVES BY BOUNDARY TYPE")
    print("-" * 100)

    total_fp = sum(
        false_positive_categories.values()
    )

    for category, count in sorted(
        false_positive_categories.items(),
        key=lambda x: -x[1]
    ):

        percentage = (
            count / total_fp * 100
            if total_fp
            else 0
        )

        print(
            f"{category:35s}: "
            f"{count:5d} "
            f"({percentage:6.2f}%)"
        )

    print("\nMISSED GT CATEGORIES")
    print("-" * 100)

    total_missed = sum(
        missed_categories.values()
    )

    for category, count in missed_categories.items():

        percentage = (
            count / total_missed * 100
            if total_missed
            else 0
        )

        print(
            f"{category:35s}: "
            f"{count:5d} "
            f"({percentage:6.2f}%)"
        )

    print("\nFIRST 30 FALSE POSITIVE EXAMPLES")
    print("-" * 100)

    for i, example in enumerate(
        false_positive_examples,
        1
    ):

        prediction = example[
            "prediction"
        ]

        print(
            f"\n#{i} "
            f"session={example['session_id']}"
        )

        print(
            f"  reason   : "
            f"{prediction.get('boundary_before')}"
        )

        print(
            f"  start    : "
            f"{prediction.get('start_timestamp')}"
        )

        print(
            f"  end      : "
            f"{prediction.get('end_timestamp')}"
        )

        print(
            f"  duration : "
            f"{prediction.get('duration_seconds', 0):.2f}s"
        )

        print(
            f"  events   : "
            f"{prediction.get('event_count')}"
        )

        print(
            f"  best IoU  : "
            f"{example['best_iou']:.3f}"
        )

    print("\nFIRST 30 MISSED GT EXAMPLES")
    print("-" * 100)

    for i, example in enumerate(
        missed_examples,
        1
    ):

        gt = example["gt"]

        print(
            f"\n#{i} "
            f"session={example['session_id']}"
        )

        print(
            f"  execution: "
            f"{gt.get('execution_id')}"
        )

        print(
            f"  process  : "
            f"{gt.get('process_code')}"
        )

        print(
            f"  variant  : "
            f"{gt.get('process_variant')}"
        )

        print(
            f"  start    : "
            f"{gt.get('start_ts')}"
        )

        print(
            f"  end      : "
            f"{gt.get('end_ts')}"
        )

        print(
            f"  best IoU : "
            f"{example['best_iou']:.3f}"
        )

        prediction = example[
            "best_prediction"
        ]

        if prediction:

            print(
                f"  predicted : "
                f"{prediction.get('start_timestamp')} "
                f"→ "
                f"{prediction.get('end_timestamp')}"
            )

            print(
                f"  boundary  : "
                f"{prediction.get('boundary_before')}"
            )

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()