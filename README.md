# PawPal+ — Pet Care Planning Assistant

**PawPal+** is a Streamlit app that helps busy pet owners stay consistent with daily pet care. It lets you define tasks, set priorities and time constraints, and generate a smart daily schedule — with conflict warnings and automatic recurrence built in.

---

## Table of Contents

1. [Scenario](#scenario)
2. [Features](#features)
3. [Project Structure](#project-structure)
4. [Getting Started](#getting-started)
5. [How to Use the App](#how-to-use-the-app)
6. [Scheduling Logic](#scheduling-logic)
7. [Running Tests](#running-tests)
8. [How Agent Mode Was Used](#how-agent-mode-was-used)

---

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track care tasks (walks, feeding, medication, grooming, enrichment, etc.)
- Consider constraints like available time, task priority, and preferred schedule times
- Produce a daily plan and explain why each task was chosen or skipped

---

## Features

- **Priority-based scheduling** — tasks are ranked `HIGH > MEDIUM > LOW` using a Python `Enum`. The scheduler greedily fills the owner's daily time budget with the highest-priority tasks first.
- **Weighted scoring** — an optional advanced mode ranks tasks by a composite score: `priority value × urgency multiplier`. A `LOW` task due today (score 3.0) is scheduled ahead of a `MEDIUM` task with no due date (score 2.0), reflecting real-world urgency over fixed labels.
- **Sorting by priority then time** — the task table is sorted by priority level first, then by preferred start time (`HH:MM`) as a tiebreaker.
- **Conflict warnings** — the scheduler checks every pair of tasks per pet for overlapping time windows and surfaces human-readable warnings in the UI. Conflicts are flagged but do not block the schedule, leaving the final decision to the owner.
- **Daily and weekly recurrence** — when a recurring task is marked complete, the next occurrence is automatically created using Python's `timedelta` (`+1 day` for `"daily"`, `+7 days` for `"weekly"`). One-off tasks (`"as needed"`) complete without spawning a follow-up.
- **Filtering** — tasks can be filtered by completion status or pet name, making it easy to see only what still needs to be done.
- **Multi-pet support** — an owner can have multiple pets, each with their own independent task list. The scheduler aggregates across all pets when generating a plan.
- **Persistent UI state** — Streamlit's `session_state` keeps the owner, pets, and tasks in memory across button clicks so no data is lost on page rerun.
- **Data persistence** — the full owner, pet, and task state is serialised to `data.json` after every change and automatically reloaded on app startup, so data survives browser refreshes and server restarts.
- **Professional UI** — emoji task-type icons (`🐕 🍽️ 💊 ✂️ 🏥 🎾`), colour-coded priority labels (`🔴 🟡 🟢`), `st.metric()` dashboard cards, a live time-budget progress bar, and interactive `st.dataframe()` tables.
- **Formatted CLI output** — `main.py` uses the `tabulate` library to render all task lists and schedules as clean rounded tables, with an ASCII progress bar for time budget visualisation.

---

## Project Structure

```
pawpal-starter/
├── app.py               # Streamlit UI — connects the interface to the logic layer
├── pawpal_system.py     # Logic layer — all classes and scheduling algorithms
├── main.py              # Terminal demo — run to verify logic without the UI
├── data.json            # Auto-generated — persisted owner/pet/task state
├── requirements.txt     # Python dependencies (streamlit, pytest, tabulate)
└── tests/
    └── test_pawpal.py   # Pytest tests for core scheduling behaviors
```
---

## UML diagram

<a href="/assets/uml_final.png" target="_blank"><img src='assets/uml_final.png' title='UML' width='' alt='UML Diafram' class='center-block' /></a>.

---

## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run the app

```bash
streamlit run app.py
```

### Run the terminal demo

```bash
python main.py
```

### 📸 Demo
<a href="/assets/app_screenshot_1.png" target="_blank"><img src='assets/app_screenshot_1.png' title='PawPal App' width='' alt='PawPal App' class='center-block' /></a>.

<a href="/assets/app_screenshot_2.png" target="_blank"><img src='assets/app_screenshot_2.png' title='PawPal App' width='' alt='PawPal App' class='center-block' /></a>.

<a href="/assets/app_screenshot_3.png" target="_blank"><img src='assets/app_screenshot_3.png' title='PawPal App' width='' alt='PawPal App' class='center-block' /></a>.

---

## How to Use the App

The app is organized into three sections:

### 1. Owner & Pet Setup
Enter your name, how many minutes you have available today, and your pet's name and species. Click **Save owner & pet** to initialize the session.

### 2. Add Tasks
Fill in the task title, duration, priority, preferred start time, and an optional due date, then click **Add task**. Tasks appear in an interactive table sorted by priority then start time, with emoji task-type icons, colour-coded priority labels, a live urgency indicator, and a composite **Score** column that shows how the weighted scheduler will rank each task. Conflict warnings appear immediately below the table.

### 3. Generate Schedule
Choose a scheduling mode using the toggle at the top of this section:

- **Standard mode** (default) — greedy algorithm, highest priority first
- **Weighted mode** — ranks tasks by `priority × urgency`; tasks with imminent due dates are promoted regardless of their base priority label

Click **Generate schedule**. The app displays:
- Summary metrics (scheduled count, skipped count, time used)
- A time-budget progress bar
- A table of **scheduled tasks** with start/end times and, in weighted mode, the score and urgency for each task
- A list of **skipped tasks** that did not fit within the available time budget
- Any **conflict warnings** re-surfaced so they are not missed

---

## Scheduling Logic

The scheduler (`Scheduler` in `pawpal_system.py`) uses the following algorithms:

| Method | Description |
|---|---|
| `generate_plan()` | Greedy algorithm — sorts pending tasks by raw priority (`HIGH` first), then fits them into the time budget one by one |
| `generate_weighted_plan()` | Greedy algorithm using composite score (`priority.value × urgency_multiplier`) — tasks with imminent due dates are promoted over higher-labelled tasks with no urgency |
| `task_score(task)` | Returns the composite float score for a task; exposed to the UI so the Score column updates live as tasks are added |
| `_urgency_multiplier(task)` | Returns 3.0 (overdue/today), 2.0 (1–3 days), 1.5 (4–7 days), or 1.0 (no due date / >7 days) |
| `sort_by_time()` | Sorts tasks by `HH:MM` start time using a lambda key on string comparison |
| `sort_by_priority_then_time()` | Tuple key `(-priority.value, time)` — priority descending, time ascending as tiebreaker |
| `filter_tasks()` | Filters a task list by `completed` status and/or `pet_name` |
| `detect_conflicts()` | Checks all task pairs per pet for overlapping windows: conflict if `a_start < b_end AND b_start < a_end` |
| `mark_task_complete()` | Marks a task done; if `frequency` is `"daily"` or `"weekly"`, auto-creates the next occurrence via `Task.next_occurrence()` using `timedelta` |

**Serialisation methods** (on `Task`, `Pet`, `Owner`):

| Method | Description |
|---|---|
| `to_dict()` | Converts the object to a JSON-serialisable dictionary; `Priority` stored as its `.name` string, `date` as ISO format |
| `from_dict(data)` | Class method — reconstructs the object from a dictionary, reversing the type conversions above |
| `Owner.save_to_json(path)` | Writes the full owner tree to `data.json` |
| `Owner.load_from_json(path)` | Reads and reconstructs an `Owner` from `data.json` |

### Design tradeoffs

**Greedy vs. optimal packing:** the scheduler uses a greedy algorithm rather than 0/1 knapsack. This guarantees the most critical tasks always run first — a `HIGH` priority medication should never be dropped to fit two `LOW` tasks. Predictability matters more than theoretical optimality in pet care.

**Weighted scoring vs. fixed priority:** the standard greedy mode uses fixed enum labels, which is simple and transparent. The weighted mode adds urgency as a second signal, allowing due-date proximity to override labels when it genuinely matters. The toggle lets the owner choose which behaviour they want rather than forcing one model on all use cases.

---

## Running Tests

```bash
python -m pytest tests/test_pawpal.py -v
```

The test suite covers:

- Task completion and status changes
- Adding tasks to a pet
- Sort order correctness
- Daily and weekly recurrence date calculation
- `"as needed"` tasks completing without recurrence
- Conflict detection for overlapping and same-start-time tasks
- No false positives on sequential (non-overlapping) tasks
- Empty pet producing an empty plan
- Task exactly filling the time budget (boundary condition)
- Task exceeding the time budget being skipped

---

## How Agent Mode Was Used

This project was built using **Claude Code (Agent Mode)** — an AI-powered CLI assistant that operates directly on the codebase. Rather than just answering questions, Agent Mode reads, writes, and edits files, runs terminal commands, and iterates across multiple steps autonomously. Below is a record of how it was applied at each stage of this project.

---

### 1. Initial Design — UML and Class Skeleton

**Prompt given:** Identify three core user actions and design the initial class structure.

Agent Mode analysed the project scenario, proposed `Task`, `Pet`, `Owner`, `Scheduler`, and `Plan` as the five core classes, and generated a **Mermaid.js class diagram** showing their relationships (composition, dependency). It then scaffolded the full class skeleton in `pawpal_system.py` using Python `@dataclass` for data-holding classes and a plain class for `Scheduler`.

**Key decision suggested by Agent Mode:** replace a plain string `priority` field with a `Priority(Enum)` so that comparisons and sorting would be type-safe and reliable — a design tradeoff that informed every later algorithm.

---

### 2. Core Logic Implementation

**Prompts given:** Flesh out Task, Pet, Owner, and Scheduler; add docstrings; create `main.py` demo.

Agent Mode implemented:
- `Task.mark_complete()`, `Task.next_occurrence()` — including `timedelta` arithmetic for `"daily"` / `"weekly"` recurrence
- `Pet.add_task()`, `Pet.pending_tasks()`
- `Owner.all_tasks()`, `Owner.all_pending_tasks()` — aggregating across multiple pets
- `Scheduler.generate_plan()` — greedy algorithm sorted by `Priority.value` descending
- `Plan.explain()` — human-readable schedule summary
- `main.py` — end-to-end terminal demo with two pets and deliberate time conflicts

Agent Mode also identified a potential logic bottleneck in the original skeleton: `Owner` held a single `Pet` reference instead of `list[Pet]`, which would have broken multi-pet support. It flagged this and updated the design before any logic was written.

---

### 3. Smarter Scheduling Algorithms

**Prompts given:** Add sorting, filtering, recurring tasks, and conflict detection.

Agent Mode added four algorithmic improvements in sequence:

| Algorithm | Implementation detail |
|---|---|
| `sort_by_time()` | Lambda key on `"HH:MM"` string — works because zero-padded strings sort lexicographically |
| `sort_by_priority_then_time()` | Tuple key `(-priority.value, time)` — negative value reverses sort direction without a custom comparator |
| `filter_tasks()` | Accepts `completed` and `pet_name` keyword arguments; builds a title→pet lookup dict internally |
| `detect_conflicts()` | Interval overlap test: `a_start < b_end AND b_start < a_end` — flags but does not block, preserving owner control |
| `mark_task_complete()` | Calls `Task.next_occurrence()` only for `"daily"` / `"weekly"`; returns `None` for `"as needed"` |

After each addition, Agent Mode explained the tradeoff — for example, why a greedy algorithm is preferable to 0/1 knapsack for pet care (predictability and transparency over theoretical optimality).

---

### 4. Streamlit UI Integration

**Prompts given:** Connect `pawpal_system.py` to `app.py`; reflect all algorithms in the UI.

Agent Mode wired each logic method to a UI component:
- `st.session_state` was introduced to persist the `Owner` object across Streamlit reruns — Agent Mode explained *why* this is necessary (Streamlit re-executes the entire script on every interaction)
- The task table was updated to call `scheduler.sort_by_priority_then_time()` and render emoji-coded priority labels (`🔴 🟡 🟢`)
- Conflict warnings from `detect_conflicts()` were surfaced in two places: immediately after the task table and again at schedule generation time
- `st.metric()` cards, `st.progress()`, and `st.dataframe()` replaced plain `st.table()` calls for a more professional dashboard feel

---

### 5. Testing

**Prompt given:** Write pytest tests for all core behaviours and edge cases.

Agent Mode designed 13 tests across five groups:

| Group | Tests |
|---|---|
| Basics | `mark_complete()` flips flag; `add_task()` increments count |
| Sorting | Three tasks added out-of-order → correct chronological output; single-task list unchanged |
| Recurrence | Daily task → next due tomorrow; weekly → 7 days later; `"as needed"` → no new task, `None` returned |
| Conflict detection | Overlapping windows → 1 warning; same start time → 1 warning; sequential tasks → no warning |
| Scheduling edge cases | Empty pet → empty plan; task exactly filling budget → scheduled; task exceeding budget → skipped |

Agent Mode also caught a test design error: an early draft of `test_as_needed_task` expected a `ValueError` to be raised, but the actual implementation returns `None` rather than raising. Agent Mode corrected both the test logic and removed the now-unused `import pytest`.

---

### 6. Extensions (Challenges)

**Prompts given:** Add data persistence, advanced UI formatting, and weighted scheduling.

| Challenge | What Agent Mode did |
|---|---|
| **Data persistence** | Added `to_dict()` / `from_dict()` classmethods to `Task`, `Pet`, and `Owner`; added `save_to_json()` and `load_from_json()` to `Owner`; updated `app.py` startup to auto-load `data.json` and save after every mutation |
| **Professional UI** | Added `task_icon()` keyword matcher for contextual emojis (`🐕 🍽️ 💊 ✂️ 🏥 🎾`); switched tables to `st.dataframe()`; added `st.metric()` dashboard cards and `st.progress()` time-budget bar; added `tabulate` formatted tables to `main.py` |
| **Weighted scheduling** | Designed and implemented `_urgency_multiplier()` and `task_score()` on `Scheduler`; added `generate_weighted_plan()` that ranks tasks by `priority.value × urgency_multiplier` rather than priority alone; added a live Score column and an algorithm toggle in the UI |

---

### Reflection

Agent Mode acted as a **pair programmer** throughout — not just generating code, but:

- Catching design issues before they became bugs (single-pet → multi-pet, test logic error)
- Explaining *why* each algorithmic choice was made, not just *what* to write
- Iterating across the full stack (logic → UI → tests → CLI) within a single conversation
- Diagnosing a runtime environment bug (`AttributeError` caused by two Python installations sharing a stale `.pyc` cache) by systematically eliminating candidates

The most valuable use of Agent Mode was in **algorithm design**: the weighted priority scorer, conflict detection interval logic, and recurrence `timedelta` arithmetic were all proposed, justified, and implemented by the agent in direct response to high-level feature requests.
