import json
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

    def to_dict(self) -> dict:
        """Serialize this task to a JSON-compatible dictionary."""
        return {
            "title": self.title,
            "duration_minutes": self.duration_minutes,
            "priority": self.priority.name,
            "frequency": self.frequency,
            "completed": self.completed,
            "time": self.time,
            "due_date": self.due_date.isoformat() if self.due_date else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Reconstruct a Task from a dictionary produced by to_dict()."""
        return cls(
            title=data["title"],
            duration_minutes=data["duration_minutes"],
            priority=Priority[data["priority"]],
            frequency=data["frequency"],
            completed=data["completed"],
            time=data["time"],
            due_date=date.fromisoformat(data["due_date"]) if data["due_date"] else None,
        )

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

    def to_dict(self) -> dict:
        """Serialize this pet to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "species": self.species,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Pet":
        """Reconstruct a Pet from a dictionary produced by to_dict()."""
        pet = cls(name=data["name"], species=data["species"])
        for t in data["tasks"]:
            pet.tasks.append(Task.from_dict(t))
        return pet


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

    def to_dict(self) -> dict:
        """Serialize this owner to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "available_minutes_per_day": self.available_minutes_per_day,
            "pets": [p.to_dict() for p in self.pets],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Owner":
        """Reconstruct an Owner from a dictionary produced by to_dict()."""
        return cls(
            name=data["name"],
            available_minutes_per_day=data["available_minutes_per_day"],
            pets=[Pet.from_dict(p) for p in data["pets"]],
        )

    def save_to_json(self, path: str = "data.json") -> None:
        """Write the owner (and all pets/tasks) to a JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_json(cls, path: str = "data.json") -> "Owner":
        """Load and reconstruct an Owner from a JSON file saved by save_to_json()."""
        with open(path) as f:
            return cls.from_dict(json.load(f))


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

    def _pending_tasks_with_pet(self) -> list[tuple["Pet", Task]]:
        """Return (pet, task) pairs for all pending tasks, preserving pet context."""
        return [(pet, task) for pet in self.owner.pets for task in pet.pending_tasks()]

    def _deduplicate_shared(self, pairs: list[tuple["Pet", Task]]) -> list[Task]:
        """Collapse tasks with identical titles across same-species pets into one instance.

        Lets the scheduler count the time budget once when the owner can do the
        activity with all same-species pets simultaneously (e.g., one walk for two dogs).
        The first encountered task object is kept as the representative.
        """
        seen: set[tuple[str, str]] = set()
        result = []
        for pet, task in pairs:
            key = (task.title.strip().lower(), pet.species)
            if key not in seen:
                seen.add(key)
                result.append(task)
        return result

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

    def sort_by_priority_then_time(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks by priority descending (HIGH first), then by start time ascending."""
        return sorted(tasks, key=lambda t: (-t.priority.value, t.time))

    def filter_tasks(self, tasks: list[Task], completed: bool | None = None, pet_name: str | None = None) -> list[Task]:
        """Filter tasks by completion status and/or pet name."""
        result = tasks
        if completed is not None:
            result = [t for t in result if t.completed == completed]
        if pet_name is not None:
            pet_names = {t.title: pet.name for pet in self.owner.pets for t in pet.tasks}
            result = [t for t in result if pet_names.get(t.title) == pet_name]
        return result

    def _urgency_multiplier(self, task: Task) -> float:
        """Return a multiplier based on how soon a task's due date is.

        Overdue / today → 3.0   (most urgent)
        1–3 days        → 2.0
        4–7 days        → 1.5
        >7 days / none  → 1.0   (no boost)
        """
        if task.due_date is None:
            return 1.0
        days = (task.due_date - date.today()).days
        if days <= 0:
            return 3.0
        if days <= 3:
            return 2.0
        if days <= 7:
            return 1.5
        return 1.0

    def task_score(self, task: Task) -> float:
        """Composite score = priority value × urgency multiplier."""
        return task.priority.value * self._urgency_multiplier(task)

    def generate_weighted_plan(self, shared_species: bool = False) -> Plan:
        """Schedule by composite score (priority × urgency) instead of raw priority.

        A LOW-priority task due today (score=3.0) will be scheduled ahead of a
        MEDIUM-priority task with no due date (score=2.0), reflecting real-world
        pet-care urgency rather than a fixed label hierarchy.
        When shared_species=True, tasks with the same title across same-species pets
        are counted once in the time budget.
        """
        budget = self.owner.available_minutes_per_day
        pool = (
            self._deduplicate_shared(self._pending_tasks_with_pet())
            if shared_species
            else self.get_all_tasks()
        )
        candidates = sorted(
            pool,
            key=lambda t: self.task_score(t),
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

    def generate_plan(self, shared_species: bool = False) -> Plan:
        """Greedily schedule pending tasks by priority until the time budget is exhausted.

        When shared_species=True, tasks with the same title across same-species pets
        are counted once in the time budget.
        """
        budget = self.owner.available_minutes_per_day
        pool = (
            self._deduplicate_shared(self._pending_tasks_with_pet())
            if shared_species
            else self.get_all_tasks()
        )
        candidates = sorted(
            pool,
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
