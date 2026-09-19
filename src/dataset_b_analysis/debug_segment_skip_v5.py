from segment_dataset_b_v5 import (
    load_chunks,
    detect_completion,
    find_start,
    find_end,
)


TARGETS = {
    1782930067091,
    1782930453957,
    1782933975494,
}


def main():

    chunks = load_chunks()

    print("=" * 90)
    print("V5 SEGMENT SKIP DEBUG")
    print("=" * 90)

    for chunk in chunks:

        events = chunk["events"]

        used_until = -1

        for i, event in enumerate(events):

            task = detect_completion(event)

            if task is None:
                continue

            start_index = find_start(
                events,
                i,
                task
            )

            end_index = find_end(
                events,
                i
            )

            ts = event["_ts"]

            # ------------------------------------------------
            # Print normal processing information only when
            # close to one of our targets.
            # ------------------------------------------------

            target_hit = ts in TARGETS

            if target_hit:

                print()
                print("-" * 90)
                print("TARGET")
                print("-" * 90)

                print("Session:", chunk["session"])
                print("Chunk:", chunk["chunk"])
                print("Index:", i)
                print("Timestamp:", ts)
                print("Task:", task)

                print()
                print("Calculated start index:", start_index)
                print("Calculated end index  :", end_index)
                print("Current used_until    :", used_until)

                print()
                print("Start timestamp:")

                print(
                    events[start_index]["_ts"]
                )

                print()
                print("End timestamp:")

                print(
                    events[end_index]["_ts"]
                )

                print()
                print(
                    "Start <= used_until:",
                    start_index <= used_until
                )

                print(
                    "Index <= used_until:",
                    i <= used_until
                )

                print()
                print(
                    "Would V5 create segment:",
                    start_index > used_until
                    and i > used_until
                )

                if start_index <= used_until:

                    print()
                    print(
                        "*** SKIPPED BECAUSE "
                        "START OVERLAPS PREVIOUS SEGMENT ***"
                    )

                elif i <= used_until:

                    print()
                    print(
                        "*** SKIPPED BECAUSE "
                        "COMPLETION EVENT WAS ALREADY USED ***"
                    )

                else:

                    print()
                    print(
                        "*** THIS EVENT WOULD CREATE A SEGMENT ***"
                    )

            # ------------------------------------------------
            # Reproduce V5's used_until update.
            # ------------------------------------------------

            if i <= used_until:
                continue

            if start_index <= used_until:
                continue

            used_until = end_index

    print()
    print("=" * 90)
    print("DEBUG COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()