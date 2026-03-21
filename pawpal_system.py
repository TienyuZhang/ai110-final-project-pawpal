from dataclasses import dataclass


@dataclass
class Pet:
    name: str
    species: str  # e.g. "dog", "cat", "other"


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: str  # "low", "medium", or "high"


@dataclass
class Owner:
    name: str
    available_minutes_per_day: int
    pet: Pet


class Plan:
    def __init__(self, scheduled_tasks: list[Task], skipped_tasks: list[Task]):
        self.scheduled_tasks = scheduled_tasks
        self.skipped_tasks = skipped_tasks

    def explain(self) -> str:
        pass


class Scheduler:
    def __init__(self, owner: Owner, tasks: list[Task]):
        self.owner = owner
        self.tasks = tasks

    def generate_plan(self) -> Plan:
        pass
