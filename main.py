from datetime import date
from pawpal_system import Owner, Pet, Task, Priority, Scheduler

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
print("=== Conflict Detection ===")
conflicts = scheduler.detect_conflicts()
if conflicts:
    for warning in conflicts:
        print(warning)
else:
    print("No conflicts detected.")
print()

all_tasks = jordan.all_tasks()

# --- Sorting Demo ---
print("=== All Tasks Sorted by Time ===")
for t in scheduler.sort_by_time(all_tasks):
    status = "done" if t.completed else "pending"
    print(f"  {t.time}  {t.title} [{t.priority.name}] ({status})")

# --- Filtering Demo: pending only ---
print("\n=== Pending Tasks Only ===")
for t in scheduler.filter_tasks(all_tasks, completed=False):
    print(f"  {t.title} [{t.priority.name}]")

# --- Filtering Demo: Mochi's tasks only ---
print("\n=== Mochi's Tasks Only ===")
for t in scheduler.filter_tasks(all_tasks, pet_name="Mochi"):
    print(f"  {t.title} [{t.priority.name}]")

# --- Recurring Task Demo ---
print("\n=== Recurring Task Demo ===")
today = date.today()
morning_walk = mochi.tasks[1]   # Morning walk — frequency="daily"
morning_walk.due_date = today
print(f"Before: '{morning_walk.title}' due {morning_walk.due_date}, completed={morning_walk.completed}")

next_task = scheduler.mark_task_complete(mochi, morning_walk)
print(f"After:  '{morning_walk.title}' completed={morning_walk.completed}")
print(f"Auto-created: '{next_task.title}' due {next_task.due_date}, completed={next_task.completed}")

# --- Schedule ---
print("\n=== Today's Schedule for Jordan ===")
plan = scheduler.generate_plan()
print(plan.explain())
print(f"\nTotal time used: {sum(t.duration_minutes for t in plan.scheduled_tasks)} / {jordan.available_minutes_per_day} min")
