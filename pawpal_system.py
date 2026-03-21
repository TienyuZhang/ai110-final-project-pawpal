from dataclasses import dataclass, field
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

    def mark_complete(self):
        """Mark this task as completed."""
        self.completed = True

    def reset(self):
        """Reset this task to incomplete."""
        self.completed = False


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
