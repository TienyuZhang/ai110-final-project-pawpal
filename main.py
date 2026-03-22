from datetime import date
from tabulate import tabulate
from pawpal_system import Owner, Pet, Task, Priority, Scheduler

TASK_ICON = {
    "walk": "🐕", "run": "🐕", "exercise": "🐕",
    "feed": "🍽️", "food": "🍽️", "meal": "🍽️", "treat": "🍽️",
    "medication": "💊", "medicine": "💊", "pill": "💊", "supplement": "💊", "drop": "💊",
    "groom": "✂️", "brush": "✂️", "bath": "✂️", "coat": "✂️",
    "vet": "🏥", "doctor": "🏥",
    "play": "🎾", "train": "🎾", "session": "🎾",
}

PRIORITY_LABEL = {"HIGH": "🔴 High", "MEDIUM": "🟡 Medium", "LOW": "🟢 Low"}

def task_icon(title: str) -> str:
    t = title.lower()
    return next((icon for kw, icon in TASK_ICON.items() if kw in t), "🐾")

# --- Setup ---
mochi = Pet(name="Mochi", species="dog")
luna = Pet(name="Luna", species="cat")

# Tasks added OUT OF ORDER by time to demonstrate sort_by_time()
mochi.add_task(Task("Evening walk",     duration_minutes=30, priority=Priority.MEDIUM, time="18:00"))
mochi.add_task(Task("Morning walk",     duration_minutes=30, priority=Priority.HIGH,   time="07:00"))
mochi.add_task(Task("Training session", duration_minutes=20, priority=Priority.MEDIUM, time="10:00"))
mochi.add_task(Task("Feeding",          duration_minutes=10, priority=Priority.HIGH,   time="08:00"))
# Conflict: starts at 07:15, but Morning walk runs 07:00–07:30
mochi.add_task(Task("Give supplements", duration_minutes=10, priority=Priority.HIGH,   time="07:15"))

luna.add_task(Task("Medication",        duration_minutes=5,  priority=Priority.HIGH,   time="09:00"))
luna.add_task(Task("Brush coat",        duration_minutes=15, priority=Priority.LOW,    time="11:00"))
# Conflict: starts at 09:03, but Medication runs 09:00–09:05
luna.add_task(Task("Eye drops",         duration_minutes=5,  priority=Priority.HIGH,   time="09:03"))

# Mark one task complete to demonstrate filter_tasks()
mochi.tasks[0].mark_complete()   # Evening walk → completed

jordan = Owner(name="Jordan", available_minutes_per_day=60, pets=[mochi, luna])
scheduler = Scheduler(owner=jordan)

# --- Conflict Detection Demo ---
print("=== ⚠️  Conflict Detection ===")
conflicts = scheduler.detect_conflicts()
if conflicts:
    for warning in conflicts:
        print(f"  {warning}")
else:
    print("  ✅ No conflicts detected.")
print()

all_tasks = jordan.all_tasks()

# --- Sorting Demo ---
print("=== All Tasks Sorted by Priority, then Time ===")
rows = [
    [t.time, f"{task_icon(t.title)} {t.title}", PRIORITY_LABEL[t.priority.name],
     "✓ done" if t.completed else "pending"]
    for t in scheduler.sort_by_priority_then_time(all_tasks)
]
print(tabulate(rows, headers=["Start", "Task", "Priority", "Status"], tablefmt="rounded_outline"))
print()

# --- Filtering Demo: pending only ---
print("=== Pending Tasks Only ===")
pending = scheduler.filter_tasks(all_tasks, completed=False)
rows = [
    [f"{task_icon(t.title)} {t.title}", PRIORITY_LABEL[t.priority.name]]
    for t in pending
]
print(tabulate(rows, headers=["Task", "Priority"], tablefmt="rounded_outline"))
print()

# --- Filtering Demo: Mochi's tasks only ---
print("=== Mochi's Tasks Only ===")
mochi_tasks = scheduler.filter_tasks(all_tasks, pet_name="Mochi")
rows = [
    [t.time, f"{task_icon(t.title)} {t.title}", PRIORITY_LABEL[t.priority.name]]
    for t in mochi_tasks
]
print(tabulate(rows, headers=["Start", "Task", "Priority"], tablefmt="rounded_outline"))
print()

# --- Recurring Task Demo ---
print("=== 🔁 Recurring Task Demo ===")
today = date.today()
morning_walk = mochi.tasks[1]   # Morning walk — frequency="daily"
morning_walk.due_date = today
print(f"  Before: '{morning_walk.title}' due {morning_walk.due_date}, completed={morning_walk.completed}")

next_task = scheduler.mark_task_complete(mochi, morning_walk)
print(f"  After:  '{morning_walk.title}' completed={morning_walk.completed}")
print(f"  Auto-created: '{next_task.title}' due {next_task.due_date}, completed={next_task.completed}")
print()

# --- Schedule ---
print("=== 📅 Today's Schedule for Jordan ===")
plan = scheduler.generate_plan()

if plan.scheduled_tasks:
    time_elapsed = 0
    rows = []
    for t in plan.scheduled_tasks:
        rows.append([
            f"{task_icon(t.title)} {t.title}",
            PRIORITY_LABEL[t.priority.name],
            f"{time_elapsed}–{time_elapsed + t.duration_minutes} min",
            f"{t.duration_minutes} min",
        ])
        time_elapsed += t.duration_minutes
    print(tabulate(rows, headers=["Task", "Priority", "Window", "Duration"], tablefmt="rounded_outline"))
else:
    print("  No tasks were scheduled.")

if plan.skipped_tasks:
    print("\n  ⏭️  Skipped (not enough time):")
    for t in plan.skipped_tasks:
        print(f"    {task_icon(t.title)} {t.title} [{PRIORITY_LABEL[t.priority.name]}] — needs {t.duration_minutes} min")

time_used = sum(t.duration_minutes for t in plan.scheduled_tasks)
bar_filled = int((time_used / jordan.available_minutes_per_day) * 20)
bar = "█" * bar_filled + "░" * (20 - bar_filled)
print(f"\n  Time used: [{bar}] {time_used} / {jordan.available_minutes_per_day} min")
