from pawpal_system import Pet, Task, Priority


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
