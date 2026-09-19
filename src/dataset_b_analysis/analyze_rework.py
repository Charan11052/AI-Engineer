import json
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
SEGMENTS_FILE = BASE_DIR / "outputs" / "dataset_b_segments_v6.jsonl"


def extract_case_id(segment):
    evidence = segment.get("completion_evidence", "")
    task = segment.get("task", "")

    if task == "FINANCE_INVOICE":
        match = re.search(r"INV-\d{4}-\d+", evidence)
        if match:
            return match.group(0)

    if task == "LOGISTICS_INVENTORY":
        match = re.search(r"品番：([A-Z0-9-]+)", evidence)
        if match:
            return match.group(1)

    return None


def extract_operator(session):
    parts = session.split("-", 2)

    if len(parts) == 3:
        return parts[2]

    return "UNKNOWN"


segments = []

with open(SEGMENTS_FILE, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            segments.append(json.loads(line))


cases = defaultdict(list)

for segment in segments:
    case_id = extract_case_id(segment)

    if case_id:
        key = (segment["task"], case_id)
        cases[key].append(segment)


repeated = {
    key: values
    for key, values in cases.items()
    if len(values) > 1
}


print("=" * 70)
print("DATASET B — REPEATED CASE ANALYSIS")
print("=" * 70)

print(f"Total segments              : {len(segments)}")
print(f"Identifiable business cases : {len(cases)}")
print(f"Repeated cases              : {len(repeated)}")
print()


# ------------------------------------------------------------
# Repeated cases
# ------------------------------------------------------------

print("REPEATED BUSINESS CASES")
print("-" * 70)

for (task, case_id), values in sorted(
    repeated.items(),
    key=lambda x: len(x[1]),
    reverse=True
):
    operators = []

    for segment in values:
        operator = extract_operator(segment["session"])
        operators.append(operator)

    unique_operators = sorted(set(operators))

    total_duration = sum(
        segment["duration_seconds"]
        for segment in values
    )

    print(
        f"{task:25s} | "
        f"{case_id:15s} | "
        f"{len(values):2d} executions | "
        f"{total_duration:6.2f}s | "
        f"{len(unique_operators)} operators"
    )

    print(
        "  Operators:",
        ", ".join(unique_operators)
    )


# ------------------------------------------------------------
# Repeated cases by task
# ------------------------------------------------------------

print()
print("REPEATED CASES BY TASK")
print("-" * 70)

task_stats = defaultdict(lambda: {
    "repeated_cases": 0,
    "repeated_executions": 0
})

for (task, case_id), values in repeated.items():
    task_stats[task]["repeated_cases"] += 1
    task_stats[task]["repeated_executions"] += len(values)


for task, stats in sorted(task_stats.items()):
    print(
        f"{task:25s} | "
        f"{stats['repeated_cases']:2d} repeated cases | "
        f"{stats['repeated_executions']:2d} executions"
    )


# ------------------------------------------------------------
# Cross-operator repetition
# ------------------------------------------------------------

print()
print("CASES HANDLED BY MULTIPLE OPERATORS")
print("-" * 70)

cross_operator_count = 0

for (task, case_id), values in repeated.items():

    operators = {
        extract_operator(segment["session"])
        for segment in values
    }

    if len(operators) > 1:
        cross_operator_count += 1

        print(
            f"{task:25s} | "
            f"{case_id:15s} | "
            f"{len(operators)} operators | "
            f"{', '.join(sorted(operators))}"
        )

print()
print(
    "Repeated cases involving multiple recorded operators:",
    cross_operator_count
)

print()
print("=" * 70)