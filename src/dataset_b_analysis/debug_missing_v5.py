from segment_dataset_b_v5 import (
    load_chunks,
    detect_completion,
    get_event_text,
)


TARGETS = {
    1782930067091,  # FINANCE_INVOICE
    1782930453957,  # FINANCE_INVOICE
    1782933975494,  # FINANCE_BUDGET
}


def main():

    chunks = load_chunks()

    print("=" * 80)
    print("DEBUGGING V5 MISSED COMPLETIONS")
    print("=" * 80)

    found = 0

    for chunk in chunks:

        events = chunk["events"]

        for i, event in enumerate(events):

            ts = event["_ts"]

            if ts not in TARGETS:
                continue

            found += 1

            print()
            print("-" * 80)
            print("TARGET FOUND")
            print("-" * 80)

            print("Session  :", chunk["session"])
            print("Chunk    :", chunk["chunk"])
            print("Index    :", i)
            print("Timestamp:", ts)

            print()
            print("detect_completion():")
            print(detect_completion(event))

            print()
            print("Event type:")
            print(event.get("event_type"))

            print()
            print("Application:")

            active_app = (
                event
                .get("context", {})
                .get("active_app", {})
            )

            if isinstance(active_app, dict):
                print(
                    active_app.get("app_name")
                    or active_app.get("process_name")
                )

            print()
            print("Extracted text:")

            extracted = (
                event
                .get("context", {})
                .get("extracted_text", {})
            )

            if isinstance(extracted, dict):
                print(extracted.get("text", ""))

            print()
            print("get_event_text():")
            print(get_event_text(event))

            # ------------------------------------------------
            # Nearby events
            # ------------------------------------------------

            print()
            print("Nearby events:")
            print()

            start = max(0, i - 10)
            end = min(len(events), i + 11)

            for j in range(start, end):

                e = events[j]

                delta = (
                    e["_ts"] - ts
                ) / 1000

                completion = detect_completion(e)

                print(
                    f"{j:5d} "
                    f"{delta:+8.2f}s "
                    f"{e.get('event_type', 'unknown'):25s} "
                    f"completion={str(completion):22s}"
                )

    print()
    print("=" * 80)
    print(
        f"Targets found: {found}/{len(TARGETS)}"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()