import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ROI_FILE = BASE_DIR / "outputs" / "dataset_b_automation_roi.json"
SEGMENTS_FILE = BASE_DIR / "outputs" / "dataset_b_segments_v6.jsonl"


# ------------------------------------------------------------------
# Load data
# ------------------------------------------------------------------

with open(ROI_FILE, "r", encoding="utf-8") as f:
    roi_data = json.load(f)

segments = []

with open(SEGMENTS_FILE, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            segments.append(json.loads(line))


# ------------------------------------------------------------------
# Aggregate task-level information
# ------------------------------------------------------------------

tasks = {}

for segment in segments:

    task = segment["task"]

    if task not in tasks:
        tasks[task] = {
            "executions": 0,
            "total_duration": 0.0,
            "apps": set(),
        }

    tasks[task]["executions"] += 1
    tasks[task]["total_duration"] += segment["duration_seconds"]

    for app in segment.get("applications", []):
        tasks[task]["apps"].add(app)


# ------------------------------------------------------------------
# Evidence-based qualitative scores
#
# Scores are deliberately transparent and documented.
# ------------------------------------------------------------------

RULE_CLARITY = {
    "FINANCE_INVOICE": 5,
    "LOGISTICS_ORDER": 4,
    "FINANCE_PAYMENT": 4,
    "FINANCE_BUDGET": 4,
    "HR_ONBOARDING": 3,
    "LOGISTICS_INVENTORY": 3,
    "HR_ATTENDANCE": 3,
    "HR_PAYROLL": 3,
}

DATA_READINESS = {
    "FINANCE_INVOICE": 5,
    "LOGISTICS_ORDER": 4,
    "FINANCE_PAYMENT": 4,
    "FINANCE_BUDGET": 4,
    "HR_ONBOARDING": 3,
    "LOGISTICS_INVENTORY": 4,
    "HR_ATTENDANCE": 3,
    "HR_PAYROLL": 3,
}


# ------------------------------------------------------------------
# Normalize quantitative factors
# ------------------------------------------------------------------

max_executions = max(
    x["executions"] for x in tasks.values()
)

max_duration = max(
    x["total_duration"] for x in tasks.values()
)


results = []

for task, info in tasks.items():

    frequency_score = (
        info["executions"] / max_executions * 5
    )

    time_score = (
        info["total_duration"] / max_duration * 5
    )

    repeatability_score = min(
        5,
        2 + frequency_score * 0.6
    )

    rule_score = RULE_CLARITY.get(task, 3)

    data_score = DATA_READINESS.get(task, 3)

    # Cross-app workflows generally have more integration
    # opportunity than single-application atomic actions.
    app_count = len(info["apps"])

    if app_count >= 3:
        app_complexity_score = 5
    elif app_count == 2:
        app_complexity_score = 4
    else:
        app_complexity_score = 2

    total_score = (
        frequency_score
        + time_score
        + repeatability_score
        + rule_score
        + data_score
        + app_complexity_score
    )

    results.append({
        "task": task,
        "executions": info["executions"],
        "total_duration_seconds": round(
            info["total_duration"], 2
        ),
        "applications": sorted(info["apps"]),
        "frequency_score": round(frequency_score, 2),
        "time_score": round(time_score, 2),
        "repeatability_score": round(
            repeatability_score, 2
        ),
        "rule_clarity_score": rule_score,
        "data_readiness_score": data_score,
        "cross_app_score": app_complexity_score,
        "total_score": round(total_score, 2),
    })


results.sort(
    key=lambda x: x["total_score"],
    reverse=True
)


# ------------------------------------------------------------------
# Print
# ------------------------------------------------------------------

print("=" * 78)
print("DATASET B — AUTOMATION OPPORTUNITY SCORING")
print("=" * 78)

print()
print(
    "This is an explainable heuristic prioritization score, "
    "not a predictive model."
)
print()

for rank, result in enumerate(results, 1):

    print(
        f"{rank}. {result['task']:25s} "
        f"| {result['total_score']:5.2f}/30"
    )

    print(
        f"   executions={result['executions']} | "
        f"time={result['total_duration_seconds']:.2f}s | "
        f"apps={len(result['applications'])}"
    )

    print(
        f"   frequency={result['frequency_score']:.2f}, "
        f"time={result['time_score']:.2f}, "
        f"repeatability={result['repeatability_score']:.2f}, "
        f"rules={result['rule_clarity_score']}, "
        f"data={result['data_readiness_score']}, "
        f"cross-app={result['cross_app_score']}"
    )

print()
print("=" * 78)

# ------------------------------------------------------------------
# Save
# ------------------------------------------------------------------

output_file = (
    BASE_DIR
    / "outputs"
    / "dataset_b_automation_opportunity_scores.json"
)

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(
        results,
        f,
        ensure_ascii=False,
        indent=2
    )

print("Saved:")
print(output_file)
print("=" * 78)