# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Smarter Scheduling

The scheduler (`Scheduler` in `pawpal_system.py`) goes beyond a basic priority sort with three additional features:

- **Sorting by time** — `sort_by_time()` orders tasks by their preferred start time (`"HH:MM"`) so the day's plan reads chronologically.
- **Filtering** — `filter_tasks()` narrows a task list by completion status, pet name, or both, making it easy to view only what still needs to be done or to focus on one pet at a time.
- **Recurring tasks** — `mark_task_complete()` marks a task done and automatically adds the next occurrence to the pet's task list using `timedelta` (`+1 day` for `"daily"`, `+7 days` for `"weekly"`). Non-recurring tasks (`"as needed"`) are completed without spawning a follow-up.
- **Conflict detection** — `detect_conflicts()` checks every pair of tasks per pet for overlapping time windows and returns human-readable warning messages. Conflicts are flagged but do not block scheduling, leaving the final decision to the owner.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.
