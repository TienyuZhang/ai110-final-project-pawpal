from pawpal_system import Owner, Pet, Task, Priority, Scheduler

# --- Setup ---
mochi = Pet(name="Mochi", species="dog")
luna = Pet(name="Luna", species="cat")

mochi.add_task(Task("Morning walk",     duration_minutes=30, priority=Priority.HIGH))
mochi.add_task(Task("Feeding",          duration_minutes=10, priority=Priority.HIGH))
mochi.add_task(Task("Training session", duration_minutes=20, priority=Priority.MEDIUM))

luna.add_task(Task("Medication",        duration_minutes=5,  priority=Priority.HIGH))
luna.add_task(Task("Brush coat",        duration_minutes=15, priority=Priority.LOW))

jordan = Owner(name="Jordan", available_minutes_per_day=60, pets=[mochi, luna])

# --- Schedule ---
scheduler = Scheduler(owner=jordan)
plan = scheduler.generate_plan()

# --- Output ---
print(f"=== Today's Schedule for {jordan.name} ===")
print(plan.explain())
print(f"\nTotal time used: {sum(t.duration_minutes for t in plan.scheduled_tasks)} / {jordan.available_minutes_per_day} min")
