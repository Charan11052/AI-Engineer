import json
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SEGMENTS_FILE = (
    BASE_DIR
    / "outputs"
    / "dataset_b_segments_v6.jsonl"
)


def load_segments():
    segments = []

    with open(SEGMENTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                segments.append(json.loads(line))

    return segments


def extract_operator(session):
    parts = session.split("-", 2)

    if len(parts) == 3:
        return parts[2]

    return "UNKNOWN"

def main():
    segments = load_segments()

    operators = defaultdict(int)

    for segment in segments:
        session = segment.get("session", "")
        operator = extract_operator(session)
        operators[operator] += 1

    print("DATASET B OPERATOR IDENTIFIER ANALYSIS")
    print("=" * 60)

    print(
        f"Distinct recorded identifiers : "
        f"{len(operators)}"
    )

    print()

    for operator, count in sorted(
        operators.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        print(
            f"{operator:<25} "
            f"{count} executions"
        )


if __name__ == "__main__":
    main()