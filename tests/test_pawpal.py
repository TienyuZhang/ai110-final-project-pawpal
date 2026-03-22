from datetime import date, timedelta
from pawpal_system import Owner, Pet, Task, Priority, Scheduler


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_owner(*pets, minutes=120):
    """Return an Owner with the given pets and a default time budget."""
    return Owner(name="Jordan", available_minutes_per_day=minutes, pets=list(pets))


def make_pet(*tasks):
    """Return a Pet with the given tasks pre-loaded."""
    pet = Pet(name="Mochi", species="dog")
    for t in tasks:
        pet.add_task(t)
    return pet


# ── Original tests ────────────────────────────────────────────────────────────

def test_mark_complete_changes_status():
    """Verify that mark_complete() flips the task's completed flag to True."""
    task = Task(title="Morning walk", duration_minutes=30, priority=Priority.HIGH)
    assert task.completed is False
    task.mark_complete()
    assert task.completed is True


def test_add_task_increases_pet_task_count():
    """Verify that adding a task to a Pet increments its task list length by one."""
    pet = Pet(name="Mochi", species="dog")
    assert len(pet.tasks) == 0
    pet.add_task(Task(title="Feeding", duration_minutes=10, priority=Priority.HIGH))
    assert len(pet.tasks) == 1


# ── Sorting ───────────────────────────────────────────────────────────────────

def test_sort_by_time_returns_chronological_order():
    """Verify tasks added out of order are sorted correctly by HH:MM start time."""
    t1 = Task("Evening walk",  duration_minutes=30, priority=Priority.LOW,  time="18:00")
    t2 = Task("Morning walk",  duration_minutes=30, priority=Priority.HIGH, time="07:00")
    t3 = Task("Midday feeding",duration_minutes=10, priority=Priority.HIGH, time="12:00")
    pet = make_pet(t1, t2, t3)
    scheduler = Scheduler(make_owner(pet))
    sorted_tasks = scheduler.sort_by_time(pet.tasks)
    assert [t.time for t in sorted_tasks] == ["07:00", "12:00", "18:00"]


def test_sort_by_time_single_task():
    """Sorting a single-task list returns that task unchanged."""
    t = Task("Walk", duration_minutes=20, priority=Priority.MEDIUM, time="09:00")
    pet = make_pet(t)
    scheduler = Scheduler(make_owner(pet))
    assert scheduler.sort_by_time(pet.tasks) == [t]


# ── Recurrence ────────────────────────────────────────────────────────────────

def test_daily_recurrence_creates_next_day_task():
    """Marking a daily task complete should auto-add a new task due tomorrow."""
    today = date.today()
    task = Task("Morning walk", duration_minutes=30, priority=Priority.HIGH,
                frequency="daily", due_date=today)
    pet = make_pet(task)
    scheduler = Scheduler(make_owner(pet))

    scheduler.mark_task_complete(pet, task)

    assert task.completed is True
    assert len(pet.tasks) == 2
    next_task = pet.tasks[1]
    assert next_task.due_date == today + timedelta(days=1)
    assert next_task.completed is False


def test_weekly_recurrence_creates_task_seven_days_later():
    """Marking a weekly task complete should auto-add a new task due in 7 days."""
    today = date.today()
    task = Task("Grooming", duration_minutes=45, priority=Priority.MEDIUM,
                frequency="weekly", due_date=today)
    pet = make_pet(task)
    scheduler = Scheduler(make_owner(pet))

    scheduler.mark_task_complete(pet, task)

    next_task = pet.tasks[1]
    assert next_task.due_date == today + timedelta(days=7)


def test_as_needed_task_completes_without_recurrence():
    """Marking an 'as needed' task complete should not spawn a follow-up task."""
    task = Task("Vet visit", duration_minutes=60, priority=Priority.HIGH, frequency="as needed")
    pet = make_pet(task)
    scheduler = Scheduler(make_owner(pet))
    result = scheduler.mark_task_complete(pet, task)
    assert task.completed is True
    assert result is None          # no next occurrence returned
    assert len(pet.tasks) == 1     # no new task added


# ── Conflict Detection ────────────────────────────────────────────────────────

def test_conflict_detected_for_overlapping_tasks():
    """Two tasks whose time windows overlap should produce a warning."""
    t1 = Task("Morning walk",    duration_minutes=30, priority=Priority.HIGH,   time="07:00")
    t2 = Task("Give supplements",duration_minutes=10, priority=Priority.HIGH,   time="07:15")
    pet = make_pet(t1, t2)
    scheduler = Scheduler(make_owner(pet))
    warnings = scheduler.detect_conflicts()
    assert len(warnings) == 1
    assert "Morning walk" in warnings[0]
    assert "Give supplements" in warnings[0]


def test_conflict_detected_for_same_start_time():
    """Two tasks at the exact same start time should be flagged as a conflict."""
    t1 = Task("Feeding",    duration_minutes=10, priority=Priority.HIGH, time="08:00")
    t2 = Task("Medication", duration_minutes=5,  priority=Priority.HIGH, time="08:00")
    pet = make_pet(t1, t2)
    scheduler = Scheduler(make_owner(pet))
    warnings = scheduler.detect_conflicts()
    assert len(warnings) == 1


def test_no_conflict_for_sequential_tasks():
    """Tasks that end exactly when the next one starts should not conflict."""
    t1 = Task("Walk",    duration_minutes=30, priority=Priority.HIGH, time="07:00")
    t2 = Task("Feeding", duration_minutes=10, priority=Priority.HIGH, time="07:30")
    pet = make_pet(t1, t2)
    scheduler = Scheduler(make_owner(pet))
    assert scheduler.detect_conflicts() == []


# ── Scheduling Edge Cases ─────────────────────────────────────────────────────

def test_pet_with_no_tasks_produces_empty_plan():
    """A pet with no tasks should yield an empty scheduled and skipped list."""
    pet = make_pet()
    scheduler = Scheduler(make_owner(pet))
    plan = scheduler.generate_plan()
    assert plan.scheduled_tasks == []
    assert plan.skipped_tasks == []


def test_task_exactly_filling_budget_is_scheduled():
    """A task whose duration exactly equals the time budget should be scheduled, not skipped."""
    task = Task("Long walk", duration_minutes=60, priority=Priority.HIGH)
    pet = make_pet(task)
    scheduler = Scheduler(make_owner(pet, minutes=60))
    plan = scheduler.generate_plan()
    assert task in plan.scheduled_tasks
    assert plan.skipped_tasks == []


def test_task_exceeding_budget_is_skipped():
    """A task longer than the entire time budget should land in skipped_tasks."""
    task = Task("Long walk", duration_minutes=90, priority=Priority.HIGH)
    pet = make_pet(task)
    scheduler = Scheduler(make_owner(pet, minutes=60))
    plan = scheduler.generate_plan()
    assert plan.scheduled_tasks == []
    assert task in plan.skipped_tasks
