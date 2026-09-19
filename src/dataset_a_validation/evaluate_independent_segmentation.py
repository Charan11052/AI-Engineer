import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# ============================================================
# PATHS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parents[2]

PREDICTIONS_FILE = (
    PROJECT_DIR
    / "outputs"
    / "dataset_a"
    / "dataset_a_predicted_segments_v7.jsonl"
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
    / "dataset_a_independent_segmentation_v7_evaluation.json"
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
    Convert an ISO timestamp into milliseconds.

    Returns None if timestamp is missing or invalid.
    """

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
        TypeError
    ):

        return None


def get_start_ms(record):

    if (
        record.get(
            "start_timestamp_ms"
        )
        is not None
    ):

        return int(
            record[
                "start_timestamp_ms"
            ]
        )

    return parse_iso_timestamp(
        record.get("start_ts")
    )


def get_end_ms(record):
    

    if record.get("end_timestamp_ms") is not None:
        return int(record["end_timestamp_ms"])

    end_ms = parse_iso_timestamp(
        record.get("end_ts")
    )

    if end_ms is not None:
        return end_ms

    if record.get("inferred_end_timestamp_ms") is not None:
        return int(
            record["inferred_end_timestamp_ms"]
        )

    return parse_iso_timestamp(
        record.get("inferred_end_ts")
    )
# ============================================================
# VALID GT INTERVALS
# ============================================================

def filter_valid_ground_truth(ground_truth):

    valid = []

    skipped_missing = 0
    skipped_invalid = 0

    explicit_end_count = 0
    inferred_end_count = 0

    for gt in ground_truth:

        start_ms = get_start_ms(gt)

        # Check the ORIGINAL source end separately so we
        # can report whether this interval was inferred.
        explicit_end_ms = None

        if gt.get("end_timestamp_ms") is not None:
            explicit_end_ms = int(
                gt["end_timestamp_ms"]
            )
        else:
            explicit_end_ms = parse_iso_timestamp(
                gt.get("end_ts")
            )

        end_ms = get_end_ms(gt)

        if start_ms is None or end_ms is None:
            skipped_missing += 1
            continue

        if end_ms < start_ms:
            skipped_invalid += 1
            continue

        gt["start_timestamp_ms"] = start_ms
        gt["end_timestamp_ms"] = end_ms

        if explicit_end_ms is not None:
            gt["evaluation_end_source"] = "manifest"
            explicit_end_count += 1
        else:
            gt["evaluation_end_source"] = "inferred_next_start"
            inferred_end_count += 1

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
        f"  Manifest ends       : "
        f"{explicit_end_count:,}"
    )
    print(
        f"  Inferred ends       : "
        f"{inferred_end_count:,}"
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
# INTERVAL UTILITIES
# ============================================================

def interval_iou(
    prediction,
    ground_truth
):
    """
    Temporal Intersection over Union.

        IoU = intersection / union
    """

    pred_start = get_start_ms(
        prediction
    )

    pred_end = get_end_ms(
        prediction
    )

    gt_start = get_start_ms(
        ground_truth
    )

    gt_end = get_end_ms(
        ground_truth
    )

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
        - max(
            pred_start,
            gt_start
        )
    )

    union = (
        max(
            pred_end,
            gt_end
        )
        - min(
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
    """
    Greedy one-to-one matching.

    Candidate matches must have IoU >= threshold.

    Highest-IoU matches are selected first.

    Each prediction and GT interval can be matched
    at most once.
    """

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
                        gt_index
                    )
                )

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
        gt_index
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
        match[
            "prediction_index"
        ]
        for match in matches
    }

    matched_gt = {
        match["gt_index"]
        for match in matches
    }

    false_positives = (
        len(predictions)
        - len(matched_predictions)
    )

    false_negatives = (
        len(ground_truth)
        - len(matched_gt)
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

        start_error = abs(
            get_start_ms(
                prediction
            )
            -
            get_start_ms(
                gt
            )
        ) / 1000.0

        end_error = abs(
            get_end_ms(
                prediction
            )
            -
            get_end_ms(
                gt
            )
        ) / 1000.0

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

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    if matches:

        mean_iou = (
            sum(ious)
            / len(ious)
        )

        mean_start_error = (
            sum(start_errors)
            / len(start_errors)
        )

        mean_end_error = (
            sum(end_errors)
            / len(end_errors)
        )

    else:

        mean_iou = 0.0

        mean_start_error = None

        mean_end_error = None

    precision = (
        len(matches)
        / len(predictions)
        if predictions
        else 0.0
    )

    recall = (
        len(matches)
        / len(ground_truth)
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

        "matches":
            matches,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)

    print(
        "DATASET A — "
        "INDEPENDENT SEGMENTATION V8 EVALUATION"
    )

    print("=" * 70)

    print()

    print(
        "Prediction:"
    )

    print(
        PREDICTIONS_FILE
    )

    print()

    print(
        "Reference:"
    )

    print(
        GT_FILE
    )

    print()

    print(
        f"IoU threshold: "
        f"{IOU_THRESHOLD}"
    )

    print(
        f"Boundary tolerance: "
        f"{BOUNDARY_TOLERANCE_SECONDS} seconds"
    )

    # --------------------------------------------------------
    # Load files
    # --------------------------------------------------------

    predictions = load_jsonl(
        PREDICTIONS_FILE
    )

    ground_truth = load_jsonl(
        GT_FILE
    )

    print()

    print(
        f"Loaded predictions: "
        f"{len(predictions):,}"
    )

    print(
        f"Loaded GT records: "
        f"{len(ground_truth):,}"
    )

    # --------------------------------------------------------
    # Filter GT to actual temporal intervals
    # --------------------------------------------------------

    ground_truth = (
        filter_valid_ground_truth(
            ground_truth
        )
    )

    # --------------------------------------------------------
    # Group records by session
    # --------------------------------------------------------

    predictions_by_session = (
        defaultdict(list)
    )

    gt_by_session = (
        defaultdict(list)
    )

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
        set(
            predictions_by_session
        )
        |
        set(
            gt_by_session
        )
    )

    print()

    print(
        f"Sessions evaluated: "
        f"{len(all_sessions)}"
    )

    # --------------------------------------------------------
    # Per-session evaluation
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
            ),
        )

        session_results.append(
            result
        )

    # --------------------------------------------------------
    # Overall counts
    # --------------------------------------------------------

    total_predictions = sum(
        result[
            "predicted_segments"
        ]
        for result in session_results
    )

    total_gt = sum(
        result[
            "ground_truth_executions"
        ]
        for result in session_results
    )

    total_matches = sum(
        result[
            "matched_segments"
        ]
        for result in session_results
    )

    total_false_positives = sum(
        result[
            "false_positive_predictions"
        ]
        for result in session_results
    )

    total_false_negatives = sum(
        result[
            "missed_ground_truth_executions"
        ]
        for result in session_results
    )

    # --------------------------------------------------------
    # Overall metrics
    # --------------------------------------------------------

    overall_precision = (
        total_matches
        / total_predictions
        if total_predictions
        else 0.0
    )

    overall_recall = (
        total_matches
        / total_gt
        if total_gt
        else 0.0
    )

    if (
        overall_precision
        + overall_recall
        > 0
    ):

        overall_f1 = (
            2
            * overall_precision
            * overall_recall
            /
            (
                overall_precision
                + overall_recall
            )
        )

    else:

        overall_f1 = 0.0

    # --------------------------------------------------------
    # Boundary / IoU statistics
    # --------------------------------------------------------

    all_ious = []

    all_start_errors = []

    all_end_errors = []

    total_boundaries_within_tolerance = 0

    for result in session_results:

        session_id = result[
            "session_id"
        ]

        predictions_session = (
            predictions_by_session[
                session_id
            ]
        )

        gt_session = (
            gt_by_session[
                session_id
            ]
        )

        for match in result[
            "matches"
        ]:

            all_ious.append(
                match["iou"]
            )

            prediction = (
                predictions_session[
                    match[
                        "prediction_index"
                    ]
                ]
            )

            gt = (
                gt_session[
                    match[
                        "gt_index"
                    ]
                ]
            )

            start_error = abs(
                get_start_ms(
                    prediction
                )
                -
                get_start_ms(
                    gt
                )
            ) / 1000.0

            end_error = abs(
                get_end_ms(
                    prediction
                )
                -
                get_end_ms(
                    gt
                )
            ) / 1000.0

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

                total_boundaries_within_tolerance += 1

    if all_ious:

        mean_iou = (
            sum(all_ious)
            / len(all_ious)
        )

        mean_start_error = (
            sum(all_start_errors)
            / len(all_start_errors)
        )

        mean_end_error = (
            sum(all_end_errors)
            / len(all_end_errors)
        )

    else:

        mean_iou = 0.0

        mean_start_error = None

        mean_end_error = None

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    summary = {

        "method":
            "independent_activity_episode_segmentation_v4",

        "prediction_input":
            "raw data/dataset_a/**/events.jsonl",

        "gt_used_during_prediction":
            False,

        "evaluation_reference":
            (
                "outputs/dataset_a/"
                "dataset_a_execution_intervals.jsonl"
            ),

        "configuration": {

            "hard_gap_seconds":
                20.0,

            "medium_gap_seconds":
                8.0,

            "min_events_for_medium_split":
                20,

            "min_duration_for_medium_split_seconds":
                5.0,

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

            "ground_truth_total_records":
                len(load_jsonl(GT_FILE)),

            "ground_truth_valid_intervals":
                total_gt,

            "ground_truth_manifest_end_intervals":
                sum(
                    1
                    for gt in ground_truth
                    if gt.get("evaluation_end_source")
                    == "manifest"
                ),

            "ground_truth_inferred_end_intervals":
                sum(
                    1
                    for gt in ground_truth
                    if gt.get("evaluation_end_source")
                    == "inferred_next_start"
                ),
        },
        "overall": {

            "matched_segments":
                total_matches,

            "false_positive_predictions":
                total_false_positives,

            "missed_ground_truth_executions":
                total_false_negatives,

            "precision":
                overall_precision,

            "recall":
                overall_recall,

            "f1":
                overall_f1,

            "mean_temporal_iou":
                mean_iou,

            "mean_start_boundary_error_seconds":
                mean_start_error,

            "mean_end_boundary_error_seconds":
                mean_end_error,

            "matched_boundaries_within_5_seconds":
                total_boundaries_within_tolerance,
        },

        "per_session":
            session_results,
    }

    # --------------------------------------------------------
    # Save results
    # --------------------------------------------------------

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
    # Console report
    # --------------------------------------------------------

    print()

    print("=" * 70)

    print(
        "FINAL RESULT"
    )

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
        f"{total_false_positives:,}"
    )

    print(
        f"Missed GT          : "
        f"{total_false_negatives:,}"
    )

    print()

    print(
        f"Precision           : "
        f"{overall_precision:.4f}"
    )

    print(
        f"Recall              : "
        f"{overall_recall:.4f}"
    )

    print(
        f"F1                  : "
        f"{overall_f1:.4f}"
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
        f"{total_boundaries_within_tolerance:,}"
    )

    print()

    print(
        "Output:"
    )

    print(
        OUTPUT_SUMMARY
    )


if __name__ == "__main__":
    main()