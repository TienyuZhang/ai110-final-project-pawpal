from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum


class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: Priority
    frequency: str = "daily"        # e.g. "daily", "weekly", "as needed"
    completed: bool = False
    time: str = "00:00"             # preferred start time in "HH:MM" format
    due_date: date | None = None    # date this task is due; None means unscheduled

    def mark_complete(self):
        """Mark this task as completed."""
        self.completed = True

    def reset(self):
        """Reset this task to incomplete."""
        self.completed = False

    def next_occurrence(self) -> "Task":
        """Return a fresh copy of this task due on the next recurrence date."""
        RECURRENCE_DAYS = {"daily": 1, "weekly": 7}
        days_ahead = RECURRENCE_DAYS.get(self.frequency)
        if days_ahead is None:
            raise ValueError(f"Task '{self.title}' has no recurrence rule for frequency '{self.frequency}'.")
        base = self.due_date if self.due_date is not None else date.today()
        next_due = base + timedelta(days=days_ahead)
        return Task(
            title=self.title,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            frequency=self.frequency,
            completed=False,
            time=self.time,
            due_date=next_due,
        )


@dataclass
class Pet:
    name: str
    species: str                    # e.g. "dog", "cat", "other"
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task):
        """Add a task to this pet's task list."""
        self.tasks.append(task)

    def remove_task(self, title: str):
        """Remove a task from this pet's list by title."""
        self.tasks = [t for t in self.tasks if t.title != title]

    def pending_tasks(self) -> list[Task]:
        """Return tasks that have not been completed."""
        return [t for t in self.tasks if not t.completed]


@dataclass
class Owner:
    name: str
    available_minutes_per_day: int
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet):
        """Add a pet to this owner's pet list."""
        self.pets.append(pet)

    def all_tasks(self) -> list[Task]:
        """Collect every task across all pets."""
        return [task for pet in self.pets for task in pet.tasks]

    def all_pending_tasks(self) -> list[Task]:
        """Collect only incomplete tasks across all pets."""
        return [task for pet in self.pets for task in pet.pending_tasks()]


class Plan:
    def __init__(self, scheduled_tasks: list[Task], skipped_tasks: list[Task]):
        self.scheduled_tasks = scheduled_tasks
        self.skipped_tasks = skipped_tasks

    def explain(self) -> str:
        """Return a human-readable summary of scheduled and skipped tasks."""
        lines = []

        if self.scheduled_tasks:
            lines.append("Scheduled tasks:")
            time_elapsed = 0
            for task in self.scheduled_tasks:
                start = time_elapsed
                end = start + task.duration_minutes
                lines.append(
                    f"  - {task.title} [{task.priority.name}] "
                    f"@ {start}–{end} min ({task.duration_minutes} min)"
                )
                time_elapsed = end
        else:
            lines.append("No tasks were scheduled.")

        if self.skipped_tasks:
            lines.append("\nSkipped tasks (not enough time):")
            for task in self.skipped_tasks:
                lines.append(
                    f"  - {task.title} [{task.priority.name}] "
                    f"needs {task.duration_minutes} min"
                )

        return "\n".join(lines)


class Scheduler:
    def __init__(self, owner: Owner):
        self.owner = owner

    def get_all_tasks(self) -> list[Task]:
        """Ask the Owner for all pending tasks across its pets."""
        return self.owner.all_pending_tasks()

    def mark_task_complete(self, pet: "Pet", task: Task) -> Task | None:
        """Mark a task complete and auto-schedule the next occurrence for recurring tasks."""
        task.mark_complete()
        if task.frequency in ("daily", "weekly"):
            next_task = task.next_occurrence()
            pet.add_task(next_task)
            return next_task
        return None

    def detect_conflicts(self) -> list[str]:
        """Return warning messages for any tasks whose time windows overlap within each pet."""
        warnings = []
        for pet in self.owner.pets:
            tasks = pet.tasks
            for i, a in enumerate(tasks):
                for b in tasks[i + 1:]:
                    a_start = self._to_minutes(a.time)
                    a_end   = a_start + a.duration_minutes
                    b_start = self._to_minutes(b.time)
                    b_end   = b_start + b.duration_minutes
                    if a_start < b_end and b_start < a_end:
                        warnings.append(
                            f"WARNING [{pet.name}]: '{a.title}' ({a.time}, {a.duration_minutes} min) "
                            f"overlaps with '{b.title}' ({b.time}, {b.duration_minutes} min)"
                        )
        return warnings

    @staticmethod
    def _to_minutes(hhmm: str) -> int:
        """Convert a 'HH:MM' string to total minutes since midnight."""
        hours, minutes = map(int, hhmm.split(":"))
        return hours * 60 + minutes

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks by their preferred start time in ascending HH:MM order."""
        return sorted(tasks, key=lambda t: t.time)

    def filter_tasks(self, tasks: list[Task], completed: bool | None = None, pet_name: str | None = None) -> list[Task]:
        """Filter tasks by completion status and/or pet name."""
        result = tasks
        if completed is not None:
            result = [t for t in result if t.completed == completed]
        if pet_name is not None:
            pet_names = {t.title: pet.name for pet in self.owner.pets for t in pet.tasks}
            result = [t for t in result if pet_names.get(t.title) == pet_name]
        return result

    def generate_plan(self) -> Plan:
        """Greedily schedule pending tasks by priority until the time budget is exhausted."""
        budget = self.owner.available_minutes_per_day
        candidates = sorted(
            self.get_all_tasks(),
            key=lambda t: t.priority.value,
            reverse=True,
        )

        scheduled = []
        skipped = []
        time_used = 0

        for task in candidates:
            if time_used + task.duration_minutes <= budget:
                scheduled.append(task)
                time_used += task.duration_minutes
            else:
                skipped.append(task)

        return Plan(scheduled, skipped)
