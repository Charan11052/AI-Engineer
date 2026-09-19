# AI Engineer Intern Task -- Workflow Segmentation and Automation

## Student Information

| Field | Details |
|---|---|
| **Full Name** |Charan Rongali |
| **University** | Indian Institute of Technology Hyderabad (IIT Hyderabad) |
| **Department / Major** | Electrical Engineering |
| **Round 1 Application Email id college** | ee24btech11052@iith.ac.in |
| **Round 1 Application Email id personal** | charanrongali4@gmail.com |
---

## Project Overview

This project was developed as part of the AI Engineer intern selection task. The main objective is to identify meaningful workflow segments from raw user activity logs and explore how these workflows could be used for automation.

## Overview

This project was developed as part of the AI Engineer intern task. The
main goal was to understand user activity from raw event logs, identify
meaningful work sessions, and use those sessions as the basis for
possible workflow automation.

The work is divided into two parts:

-   **Dataset A:** development and validation of an activity-based
    segmentation method using the available ground-truth execution
    intervals.
-   **Dataset B:** segmentation of real workflow activity into
    task-level sessions, followed by validation, automation analysis,
    and a small invoice-reconciliation prototype.

The implementation was deliberately kept interpretable. Instead of
treating every event as a separate task boundary, the segmentation logic
uses combinations of application changes, browser navigation, user
activity, screenshots, idle periods, and task-specific evidence.

------------------------------------------------------------------------

The `outputs` directory is split by dataset so that intermediate and
final results are easier to trace.

------------------------------------------------------------------------

# 1. Dataset A

Dataset A was used to develop and validate the segmentation approach.

The dataset contains:

-   **63 sessions**
-   **162,768 raw events**
-   **2,009 ground-truth execution intervals**
-   **7,300 events with extracted text**

The raw event stream contains application switches, screenshots,
keystrokes, mouse activity, browser actions, clipboard changes,
shortcuts and other events.

### Segmentation approach

The final Dataset A implementation used an activity-based approach
rather than using the ground-truth intervals to generate predictions.

Important signals include:

-   application identity changes
-   browser navigation
-   mouse clicks
-   active user events
-   screenshots as checkpoint evidence
-   short and medium idle gaps
-   bursts of activity around transitions
-   minimum activity/maturity checks

A key observation from the data was that task boundaries are not always
identical to application switches. Some tasks have a clear transition,
while others have a delayed or manually initiated boundary. Because of
this, the final method combines several signals rather than relying on a
single event type.

### Dataset A validation

The final selected version is **V7**.

  Metric                      Result
  ------------------------- --------
  Ground-truth executions      2,009
  Predicted segments           2,419
  Precision                   46.47%
  Recall                      55.95%
  F1                          50.77%
  Mean IoU                    66.37%
  Mean start error            5.94 s
  Mean end error              6.96 s

The predictions were generated without using the ground-truth intervals.
The ground truth was used only afterwards for evaluation.

This separation was important because using the labels while
constructing the predictions would make the evaluation misleading.

------------------------------------------------------------------------

# 2. Dataset B

Dataset B contains the workflow activity used for the final task-level
segmentation.

The available data contains:

-   **20 event-log chunks**
-   **20,477 events**
-   **939 events with extracted text**
-   **21 event types**
-   **11 recorded applications**

The observed workflows cover three broad business areas:

-   HR
-   Finance
-   Logistics

The final Dataset B segmentation is **V8**.

### Final segmentation

The V8 pipeline produced:

-   **173 segments**
-   Average duration: **32.63 s**
-   Median duration: **30.90 s**
-   Minimum duration: **1.19 s**
-   Maximum duration: **61.57 s**
-   Total segment time: **94.09 min**

Start detection used two methods:

-   `activity_block_boundary`: 165 segments
-   `fallback_activity`: 8 segments

Confidence levels:

-   High: 56
-   Medium: 109
-   Low: 8

The segmentation intentionally keeps the start detector separate from
the task completion signal. Completion evidence is useful for
identifying what a task was, but it should not automatically be treated
as the beginning of the task.

### Task distribution

  Task                    Segments
  --------------------- ----------
  LOGISTICS_INVENTORY           31
  FINANCE_INVOICE               29
  LOGISTICS_ORDER               26
  HR_ATTENDANCE                 23
  HR_ONBOARDING                 22
  FINANCE_PAYMENT               21
  HR_PAYROLL                    16
  FINANCE_BUDGET                 5

### Business-area distribution

  Area          Segments
  ----------- ----------
  HR                  61
  Logistics           57
  Finance             55

------------------------------------------------------------------------

# 3. Interruption and coverage checks

The Dataset B pipeline was also checked for overlapping segments and
repeated task patterns.

The analysis found:

-   **0 overlapping V8 segment pairs**
-   **7 A→B→A task patterns across 5 sessions**

Examples included patterns such as:

``` text
LOGISTICS_ORDER → HR_ONBOARDING → LOGISTICS_ORDER
LOGISTICS_INVENTORY → HR_ATTENDANCE → LOGISTICS_INVENTORY
HR_ONBOARDING → LOGISTICS_ORDER → HR_ONBOARDING
```

These patterns are useful evidence that workflows can be interrupted and
later resumed. They should be treated as diagnostic evidence rather than
as proof of a complete multi-task state machine.

The total V8 segment time is approximately **41.86% of the measured raw
active-time span**. This is a simple time-coverage measure and should
not be interpreted as a claim that every uncovered event is irrelevant.

------------------------------------------------------------------------

# 4. Automation opportunity analysis

The segmented Dataset B data was used to estimate where automation could
have the largest potential impact.

The ROI calculation is intentionally presented as a **scenario**, not as
a measured production saving. The report assumes that 70% of the
observed execution time could potentially be removed for an automated
workflow.

Across all 173 segments:

-   Observed segment time: **94.09 minutes**
-   Scenario saving at 70%: **65.87 minutes**

### Observed execution time by task

  Task                    Segments   Average time   Total time
  --------------------- ---------- -------------- ------------
  FINANCE_INVOICE               29        35.60 s    17.21 min
  HR_ONBOARDING                 22        39.62 s    14.53 min
  LOGISTICS_INVENTORY           31        27.96 s    14.44 min
  LOGISTICS_ORDER               26        31.64 s    13.71 min
  FINANCE_PAYMENT               21        35.78 s    12.52 min
  HR_ATTENDANCE                 23        28.94 s    11.09 min
  HR_PAYROLL                    16        29.51 s     7.87 min
  FINANCE_BUDGET                 5        32.61 s     2.72 min

The automation opportunity score is an explainable heuristic based on
frequency, execution time, cumulative effort and confidence information.
It is not a machine-learned probability and should not be interpreted as
one.

------------------------------------------------------------------------

# 5. Invoice reconciliation prototype

A small prototype was implemented to demonstrate how a segmented
workflow could feed into an automation system.

The prototype extracts available invoice evidence such as:

-   invoice number
-   amount
-   supplier information, when present

It then applies explicit reconciliation rules and records the decision
in an audit log.

The important design choice is the safety boundary:

> If the evidence required for an automatic approval is missing or
> ambiguous, the system returns `REVIEW` instead of guessing.

For the current Dataset B evidence, supplier information could not be
reliably extracted. Therefore the current run produced:

-   27 invoice observations
-   0 automatic approvals
-   27 reviews

This is a limitation of the available evidence, not something the
prototype should hide. Automatically inventing a supplier would make the
automation unsafe.

------------------------------------------------------------------------

# 6. Final deliverable

The required segmentation deliverable is:

``` text
segments.jsonl
```

Each line follows the required four-field format:

``` json
{
  "session_id": "...",
  "start": "...",
  "end": "...",
  "label": "..."
}
```

The file contains **173 records**.

The rich V8 segmentation file is kept separately at:

``` text
outputs/dataset_b/dataset_b_segments_v8.jsonl
```

This distinction is intentional:

-   `dataset_b_segments_v8.jsonl` is the internal analysis output.
-   `segments.jsonl` is the final submission-format artifact.

The final export is produced by:

``` text
src/pipeline/02_export_final_segments.py
```

------------------------------------------------------------------------

# 7. Running the pipeline

Run the following commands from the project root.

``` powershell
python "src\dataset_a_validation\analyze_dataset_a.py"
python "src\dataset_a_validation\build_ground_truth.py"
python "src\dataset_a_validation\validate_ground_truth.py"
python "src\segmentation\segmentation_v7.py"
python "src\dataset_a_validation\evaluate_independent_segmentation.py"

python "src\dataset_b_analysis\analyze_task_start_signals.py"
python "src\pipeline\01_segment_dataset_b_v8.py"
python "src\pipeline\02_validate_dataset_b_v8.py"
python "src\pipeline\04_validate_segment_quality_v8.py"
python "src\pipeline\05_analyze_automation_roi_v8.py"
python "src\pipeline\06_score_automation_opportunities_v8.py"
python "src\pipeline\07_validate_v8_coverage_interruptions.py"
python "src\pipeline\02_export_final_segments.py"

python "prototype\src\validate_prototype_v8.py"
python "prototype\src\run_dataset_b.py"
python "prototype\src\demo.py"
python -m unittest discover -s "prototype\tests" -p "test_*.py"
```

The final file can then be checked with:

``` powershell
Get-Content "segments.jsonl" | Measure-Object -Line
```

Expected result:

``` text
Lines : 173
```

------------------------------------------------------------------------

# 8. Limitations

There are several limitations worth keeping explicit.

1.  **Task boundaries are heuristic.**\
    The event logs do not provide a perfect task-start annotation for
    every workflow.

2.  **Dataset A and Dataset B serve different purposes.**\
    Dataset A provides a useful validation setting with ground truth.
    Dataset B is used for workflow discovery and task segmentation.

3.  **A→B→A patterns are evidence of interruption, not proof of a
    complete task-state model.**

4.  **Eight Dataset B segments have low-confidence starts.**\
    These should be treated carefully in any downstream automation
    system.

5.  **The 70% ROI saving is a scenario assumption.**\
    It is not a measured business saving.

6.  **The invoice prototype currently cannot safely auto-approve the
    available observations because supplier evidence is missing.**\
    The conservative result is `REVIEW`.

7.  **Historical experiments are retained where useful for
    traceability.**\
    The final reproducible path uses Dataset A V7 and Dataset B V8.

------------------------------------------------------------------------

# 9. Final note

The main focus of this implementation was not just to produce a
segmentation file, but to keep the reasoning behind the segmentation
visible.

The pipeline therefore separates:

``` text
raw events
    ↓
signal analysis
    ↓
task segmentation
    ↓
validation
    ↓
automation analysis
    ↓
prototype
    ↓
submission-format export
```

This makes it possible to inspect where a segment came from, evaluate
the segmentation independently, and keep uncertain cases from being
silently converted into automated actions.
