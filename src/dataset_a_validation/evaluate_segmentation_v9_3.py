import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# ============================================================
# DATASET A — INDEPENDENT V9.3 EVALUATION
#
# IMPORTANT:
# V9.3 segmentation was performed using RAW EVENTS ONLY.
# Ground truth is used ONLY here for evaluation.
# ============================================================


PROJECT_DIR = Path(__file__).resolve().parents[2]

PREDICTIONS_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_predicted_segments_v9_3.jsonl"
)

GT_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_execution_intervals.jsonl"
)

OUTPUT_DIR = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
)

OUTPUT_SUMMARY = (
    OUTPUT_DIR
    / "dataset_a_independent_segmentation_v9_3_evaluation.json"
)


# ============================================================
# CONFIGURATION
# ============================================================

IOU_THRESHOLD = 0.50

BOUNDARY_TOLERANCE_SECONDS = 5.0


# ============================================================
# LOADING
# ============================================================

def load_jsonl(path):

    records = []

    with path.open("r", encoding="utf-8") as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            records.append(
                json.loads(line)
            )

    return records


# ============================================================
# TIMESTAMP HANDLING
# ============================================================

def parse_iso_timestamp(timestamp):
    """
    Accept either:
      - integer/float Unix timestamp in milliseconds
      - ISO-8601 timestamp string

    Return timestamp in milliseconds.
    """

    if timestamp is None:
        return None

    # Raw event/prediction timestamps may already be
    # represented as milliseconds.
    if isinstance(timestamp, (int, float)):

        return int(timestamp)

    if not isinstance(timestamp, str):
        return None

    timestamp = timestamp.strip()

    if not timestamp:
        return None

    try:

        return int(
            datetime.fromisoformat(
                timestamp.replace(
                    "Z",
                    "+00:00"
                )
            ).timestamp()
            * 1000
        )

    except (
        ValueError,
        TypeError,
    ):

        return None
    
    
def get_start_ms(record):

    if record.get("start_timestamp_ms") is not None:

        return int(
            record["start_timestamp_ms"]
        )

    return parse_iso_timestamp(
        record.get("start_ts")
    )


def get_end_ms(record):

    # Prefer an explicit end timestamp.
    if record.get("end_timestamp_ms") is not None:

        return int(
            record["end_timestamp_ms"]
        )

    # Preserve the inferred GT end when present.
    if record.get("inferred_end_timestamp_ms") is not None:

        return int(
            record["inferred_end_timestamp_ms"]
        )

    if record.get("inferred_end_ts"):

        return parse_iso_timestamp(
            record["inferred_end_ts"]
        )

    return parse_iso_timestamp(
        record.get("end_ts")
    )


# ============================================================
# GROUND-TRUTH FILTERING
# ============================================================

def filter_valid_ground_truth(ground_truth):

    valid = []

    skipped_missing = 0
    skipped_invalid = 0

    for gt in ground_truth:

        start_ms = get_start_ms(gt)
        end_ms = get_end_ms(gt)

        if (
            start_ms is None
            or end_ms is None
        ):

            skipped_missing += 1
            continue

        if end_ms < start_ms:

            skipped_invalid += 1
            continue

        gt["start_timestamp_ms"] = start_ms
        gt["end_timestamp_ms"] = end_ms

        valid.append(gt)

    print()
    print("GT interval filtering:")
    print(
        f"  Original GT records : "
        f"{len(ground_truth):,}"
    )
    print(
        f"  Valid intervals     : "
        f"{len(valid):,}"
    )
    print(
        f"  Missing timestamps  : "
        f"{skipped_missing:,}"
    )
    print(
        f"  Invalid intervals   : "
        f"{skipped_invalid:,}"
    )

    return valid


# ============================================================
# TEMPORAL IoU
# ============================================================

def interval_iou(
    prediction,
    ground_truth
):

    pred_start = get_start_ms(prediction)
    pred_end = get_end_ms(prediction)

    gt_start = get_start_ms(ground_truth)
    gt_end = get_end_ms(ground_truth)

    if (
        pred_start is None
        or pred_end is None
        or gt_start is None
        or gt_end is None
    ):

        return 0.0

    intersection = max(
        0,
        min(
            pred_end,
            gt_end
        )
        -
        max(
            pred_start,
            gt_start
        )
    )

    union = (
        max(
            pred_end,
            gt_end
        )
        -
        min(
            pred_start,
            gt_start
        )
    )

    if union <= 0:

        return 0.0

    return (
        intersection
        / union
    )


# ============================================================
# ONE-TO-ONE MATCHING
# ============================================================

def match_segments(
    predictions,
    ground_truth
):

    candidates = []

    for pred_index, prediction in enumerate(
        predictions
    ):

        for gt_index, gt in enumerate(
            ground_truth
        ):

            iou = interval_iou(
                prediction,
                gt
            )

            if iou >= IOU_THRESHOLD:

                candidates.append(
                    (
                        iou,
                        pred_index,
                        gt_index,
                    )
                )

    # Highest IoU matches first.
    candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    used_predictions = set()
    used_gt = set()

    matches = []

    for (
        iou,
        pred_index,
        gt_index,
    ) in candidates:

        if pred_index in used_predictions:
            continue

        if gt_index in used_gt:
            continue

        used_predictions.add(
            pred_index
        )

        used_gt.add(
            gt_index
        )

        matches.append(
            {
                "prediction_index":
                    pred_index,

                "gt_index":
                    gt_index,

                "iou":
                    iou,
            }
        )

    return matches


# ============================================================
# SESSION EVALUATION
# ============================================================

def evaluate_session(
    session_id,
    predictions,
    ground_truth
):

    matches = match_segments(
        predictions,
        ground_truth
    )

    matched_predictions = {
        match["prediction_index"]
        for match in matches
    }

    matched_gt = {
        match["gt_index"]
        for match in matches
    }

    false_positives = (
        len(predictions)
        -
        len(matched_predictions)
    )

    false_negatives = (
        len(ground_truth)
        -
        len(matched_gt)
    )

    ious = []
    start_errors = []
    end_errors = []

    boundaries_within_tolerance = 0

    for match in matches:

        prediction = predictions[
            match["prediction_index"]
        ]

        gt = ground_truth[
            match["gt_index"]
        ]

        ious.append(
            match["iou"]
        )

        start_error = (
            abs(
                get_start_ms(prediction)
                -
                get_start_ms(gt)
            )
            / 1000.0
        )

        end_error = (
            abs(
                get_end_ms(prediction)
                -
                get_end_ms(gt)
            )
            / 1000.0
        )

        start_errors.append(
            start_error
        )

        end_errors.append(
            end_error
        )

        if (
            start_error
            <= BOUNDARY_TOLERANCE_SECONDS
            and
            end_error
            <= BOUNDARY_TOLERANCE_SECONDS
        ):

            boundaries_within_tolerance += 1

    if matches:

        mean_iou = (
            sum(ious)
            /
            len(ious)
        )

        mean_start_error = (
            sum(start_errors)
            /
            len(start_errors)
        )

        mean_end_error = (
            sum(end_errors)
            /
            len(end_errors)
        )

    else:

        mean_iou = 0.0
        mean_start_error = None
        mean_end_error = None

    precision = (
        len(matches)
        /
        len(predictions)
        if predictions
        else 0.0
    )

    recall = (
        len(matches)
        /
        len(ground_truth)
        if ground_truth
        else 0.0
    )

    if precision + recall > 0:

        f1 = (
            2
            * precision
            * recall
            /
            (
                precision
                + recall
            )
        )

    else:

        f1 = 0.0

    return {

        "session_id":
            session_id,

        "predicted_segments":
            len(predictions),

        "ground_truth_executions":
            len(ground_truth),

        "matched_segments":
            len(matches),

        "false_positive_predictions":
            false_positives,

        "missed_ground_truth_executions":
            false_negatives,

        "precision":
            precision,

        "recall":
            recall,

        "f1":
            f1,

        "mean_iou":
            mean_iou,

        "mean_start_boundary_error_seconds":
            mean_start_error,

        "mean_end_boundary_error_seconds":
            mean_end_error,

        "boundaries_within_5_seconds":
            boundaries_within_tolerance,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "DATASET A — "
        "INDEPENDENT V9.3 SEGMENTATION EVALUATION"
    )
    print("=" * 70)

    print()
    print("Prediction:")
    print(PREDICTIONS_FILE)

    print()
    print("Reference:")
    print(GT_FILE)

    print()
    print(
        f"IoU threshold          : "
        f"{IOU_THRESHOLD}"
    )

    print(
        f"Boundary tolerance     : "
        f"{BOUNDARY_TOLERANCE_SECONDS}s"
    )

    print()
    print(
        "IMPORTANT: "
        "GT is NOT used during V9.3 segmentation."
    )
    print(
        "GT is used here ONLY for independent evaluation."
    )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    if not PREDICTIONS_FILE.exists():

        raise FileNotFoundError(
            f"Prediction file not found:\n"
            f"{PREDICTIONS_FILE}"
        )

    if not GT_FILE.exists():

        raise FileNotFoundError(
            f"GT file not found:\n"
            f"{GT_FILE}"
        )

    predictions = load_jsonl(
        PREDICTIONS_FILE
    )

    ground_truth = load_jsonl(
        GT_FILE
    )

    print()
    print(
        f"Loaded predictions : "
        f"{len(predictions):,}"
    )

    print(
        f"Loaded GT records  : "
        f"{len(ground_truth):,}"
    )

    # --------------------------------------------------------
    # Filter GT
    # --------------------------------------------------------

    ground_truth = filter_valid_ground_truth(
        ground_truth
    )

    # --------------------------------------------------------
    # Group by session
    # --------------------------------------------------------

    predictions_by_session = defaultdict(list)
    gt_by_session = defaultdict(list)

    for prediction in predictions:

        predictions_by_session[
            prediction["session_id"]
        ].append(
            prediction
        )

    for gt in ground_truth:

        gt_by_session[
            gt["session_id"]
        ].append(
            gt
        )

    all_sessions = sorted(
        set(predictions_by_session)
        |
        set(gt_by_session)
    )

    print()
    print(
        f"Sessions evaluated : "
        f"{len(all_sessions)}"
    )

    # --------------------------------------------------------
    # Evaluate every session
    # --------------------------------------------------------

    session_results = []

    for session_id in all_sessions:

        result = evaluate_session(
            session_id,

            predictions_by_session.get(
                session_id,
                []
            ),

            gt_by_session.get(
                session_id,
                []
            )
        )

        session_results.append(
            result
        )

    # --------------------------------------------------------
    # Overall counts
    # --------------------------------------------------------

    total_predictions = sum(
        r["predicted_segments"]
        for r in session_results
    )

    total_gt = sum(
        r["ground_truth_executions"]
        for r in session_results
    )

    total_matches = sum(
        r["matched_segments"]
        for r in session_results
    )

    total_fp = sum(
        r["false_positive_predictions"]
        for r in session_results
    )

    total_fn = sum(
        r["missed_ground_truth_executions"]
        for r in session_results
    )

    # --------------------------------------------------------
    # Overall metrics
    # --------------------------------------------------------

    precision = (
        total_matches
        /
        total_predictions
        if total_predictions
        else 0.0
    )

    recall = (
        total_matches
        /
        total_gt
        if total_gt
        else 0.0
    )

    if precision + recall > 0:

        f1 = (
            2
            * precision
            * recall
            /
            (
                precision
                + recall
            )
        )

    else:

        f1 = 0.0

    # --------------------------------------------------------
    # Matched interval statistics
    # --------------------------------------------------------

    all_ious = []
    all_start_errors = []
    all_end_errors = []

    boundaries_within_5s = 0

    for session_id in all_sessions:

        predictions_session = (
            predictions_by_session.get(
                session_id,
                []
            )
        )

        gt_session = (
            gt_by_session.get(
                session_id,
                []
            )
        )

        matches = match_segments(
            predictions_session,
            gt_session
        )

        for match in matches:

            prediction = predictions_session[
                match["prediction_index"]
            ]

            gt = gt_session[
                match["gt_index"]
            ]

            all_ious.append(
                match["iou"]
            )

            start_error = (
                abs(
                    get_start_ms(prediction)
                    -
                    get_start_ms(gt)
                )
                /
                1000.0
            )

            end_error = (
                abs(
                    get_end_ms(prediction)
                    -
                    get_end_ms(gt)
                )
                /
                1000.0
            )

            all_start_errors.append(
                start_error
            )

            all_end_errors.append(
                end_error
            )

            if (
                start_error
                <= BOUNDARY_TOLERANCE_SECONDS
                and
                end_error
                <= BOUNDARY_TOLERANCE_SECONDS
            ):

                boundaries_within_5s += 1

    if all_ious:

        mean_iou = (
            sum(all_ious)
            /
            len(all_ious)
        )

        mean_start_error = (
            sum(all_start_errors)
            /
            len(all_start_errors)
        )

        mean_end_error = (
            sum(all_end_errors)
            /
            len(all_end_errors)
        )

    else:

        mean_iou = 0.0
        mean_start_error = None
        mean_end_error = None

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = {

        "method":
            "dataset_a_v9_3_independent_evaluation",

        "prediction_input":
            "outputs/dataset_a/"
            "dataset_a_predicted_segments_v9_3.jsonl",

        "gt_used_during_prediction":
            False,

        "evaluation_reference":
            "outputs/dataset_a/"
            "dataset_a_execution_intervals.jsonl",

        "configuration": {

            "iou_threshold":
                IOU_THRESHOLD,

            "boundary_tolerance_seconds":
                BOUNDARY_TOLERANCE_SECONDS,
        },

        "dataset": {

            "sessions":
                len(all_sessions),

            "predicted_segments":
                total_predictions,

            "ground_truth_valid_intervals":
                total_gt,
        },

        "overall": {

            "matched_segments":
                total_matches,

            "false_positive_predictions":
                total_fp,

            "missed_ground_truth_executions":
                total_fn,

            "precision":
                precision,

            "recall":
                recall,

            "f1":
                f1,

            "mean_temporal_iou":
                mean_iou,

            "mean_start_boundary_error_seconds":
                mean_start_error,

            "mean_end_boundary_error_seconds":
                mean_end_error,

            "matched_boundaries_within_5_seconds":
                boundaries_within_5s,
        },

        "per_session":
            session_results,
    }

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_SUMMARY.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            summary,
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # Console result
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("V9.3 FINAL INDEPENDENT EVALUATION")
    print("=" * 70)

    print()
    print(
        f"Predicted segments : "
        f"{total_predictions:,}"
    )

    print(
        f"Valid GT intervals : "
        f"{total_gt:,}"
    )

    print(
        f"Matched            : "
        f"{total_matches:,}"
    )

    print(
        f"False positives    : "
        f"{total_fp:,}"
    )

    print(
        f"Missed GT          : "
        f"{total_fn:,}"
    )

    print()

    print(
        f"Precision           : "
        f"{precision:.4f}"
    )

    print(
        f"Recall              : "
        f"{recall:.4f}"
    )

    print(
        f"F1                  : "
        f"{f1:.4f}"
    )

    print(
        f"Mean temporal IoU   : "
        f"{mean_iou:.4f}"
    )

    if mean_start_error is not None:

        print(
            f"Mean start error    : "
            f"{mean_start_error:.2f}s"
        )

        print(
            f"Mean end error      : "
            f"{mean_end_error:.2f}s"
        )

    print(
        f"Boundaries <= 5s    : "
        f"{boundaries_within_5s:,}"
    )

    print()
    print("Summary written to:")
    print(OUTPUT_SUMMARY)

    print("=" * 70)


if __name__ == "__main__":
    main()