import streamlit as st
import pandas as pd
from datetime import date
from pawpal_system import Owner, Pet, Task, Priority, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.markdown("Welcome to **PawPal+** — your pet care planning assistant.")

st.divider()

# --- Session State Initialization ---
if "owner" not in st.session_state:
    try:
        st.session_state.owner = Owner.load_from_json()
    except (FileNotFoundError, KeyError, ValueError):
        st.session_state.owner = None

PRIORITY_MAP = {"low": Priority.LOW, "medium": Priority.MEDIUM, "high": Priority.HIGH}
PRIORITY_EMOJI = {
    "HIGH":   "🔴 High",
    "MEDIUM": "🟡 Medium",
    "LOW":    "🟢 Low",
}


def task_icon(title: str) -> str:
    """Return a contextual emoji based on keywords in the task title."""
    t = title.lower()
    if any(w in t for w in ("walk", "run", "exercise", "jog")):
        return "🐕"
    if any(w in t for w in ("feed", "food", "meal", "treat", "water")):
        return "🍽️"
    if any(w in t for w in ("medication", "medicine", "pill", "supplement", "drop")):
        return "💊"
    if any(w in t for w in ("groom", "brush", "bath", "wash", "coat", "nail")):
        return "✂️"
    if any(w in t for w in ("vet", "doctor", "check", "appointment")):
        return "🏥"
    if any(w in t for w in ("play", "train", "session", "enrichment", "fetch")):
        return "🎾"
    return "🐾"


def urgency_label(task: Task) -> str:
    """Return a human-readable urgency label based on due date."""
    if task.due_date is None:
        return "—"
    days = (task.due_date - date.today()).days
    if days < 0:
        return f"🚨 Overdue ({abs(days)}d ago)"
    if days == 0:
        return "🔥 Due today"
    if days <= 3:
        return f"⚡ {days}d left"
    if days <= 7:
        return f"📅 {days}d left"
    return f"🗓️ {days}d left"


# ── Section 1: Owner & Pet Setup ──────────────────────────────────────────────
st.subheader("1. Owner & Pet Setup")

existing_owner = st.session_state.owner
default_name = existing_owner.name if existing_owner else "Jordan"
default_time = existing_owner.available_minutes_per_day if existing_owner else 60

owner_name = st.text_input("Owner name", value=default_name)
available_time = st.number_input("Available time today (minutes)", min_value=10, max_value=480, value=default_time)

st.markdown("**Add a pet:**")
col_pet1, col_pet2 = st.columns(2)
with col_pet1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col_pet2:
    species = st.selectbox("Species", ["dog", "cat", "other"])

if st.button("Save settings & add pet"):
    if st.session_state.owner is None or st.session_state.owner.name != owner_name:
        # First save or owner name changed — create fresh owner with this pet
        pet = Pet(name=pet_name, species=species)
        st.session_state.owner = Owner(
            name=owner_name,
            available_minutes_per_day=int(available_time),
            pets=[pet],
        )
        st.success(f"Created owner **{owner_name}** with pet **{pet_name}** ({species}), {available_time} min/day.")
    else:
        # Existing owner — update time budget and add pet if new
        owner = st.session_state.owner
        owner.available_minutes_per_day = int(available_time)
        existing_pet_names = [p.name for p in owner.pets]
        if pet_name in existing_pet_names:
            st.info(f"**{pet_name}** is already in your pet list. Settings updated.")
        else:
            owner.add_pet(Pet(name=pet_name, species=species))
            st.success(f"Added **{pet_name}** ({species}) to {owner_name}'s pets. {available_time} min/day.")
    st.session_state.owner.save_to_json()

# Show current pets
if st.session_state.owner and st.session_state.owner.pets:
    pet_list = ", ".join(
        f"**{p.name}** ({p.species})" for p in st.session_state.owner.pets
    )
    st.markdown(f"Current pets: {pet_list}")

st.divider()

# ── Section 2: Add Tasks ───────────────────────────────────────────────────────
st.subheader("2. Add Tasks")

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    task_pet_names = [p.name for p in st.session_state.owner.pets] if st.session_state.owner else []
    task_pet = st.selectbox("For pet", task_pet_names if task_pet_names else ["—"])
with col2:
    task_title = st.text_input("Task title", value="Morning walk")
with col3:
    duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
with col4:
    priority_str = st.selectbox("Priority", ["low", "medium", "high"], index=2)
with col5:
    task_time = st.text_input("Start time (HH:MM)", value="07:00")
with col6:
    due_date_input = st.date_input("Due date (optional)", value=None)

if st.button("Add task"):
    if st.session_state.owner is None or not st.session_state.owner.pets:
        st.warning("Please save an owner & pet first.")
    else:
        target_pet = next((p for p in st.session_state.owner.pets if p.name == task_pet), None)
        if target_pet is None:
            st.warning("Selected pet not found. Please save a pet first.")
        else:
            task = Task(
                title=task_title,
                duration_minutes=int(duration),
                priority=PRIORITY_MAP[priority_str],
                time=task_time,
                due_date=due_date_input if due_date_input else None,
            )
            target_pet.add_task(task)
            st.session_state.owner.save_to_json()
            st.success(f"Added: {task_icon(task_title)} **{task_title}** for **{task_pet}** at {task_time} ({duration} min, {PRIORITY_EMOJI[priority_str.upper()]})")

# Display tasks sorted by priority then time
owner = st.session_state.owner
if owner and owner.all_tasks():
    scheduler = Scheduler(owner=owner)

    # At-a-glance metrics
    all_tasks = owner.all_tasks()
    pending = owner.all_pending_tasks()
    m1, m2, m3 = st.columns(3)
    m1.metric("Total tasks", len(all_tasks))
    m2.metric("Pending", len(pending))
    m3.metric("Completed", len(all_tasks) - len(pending))

    # Keep a stable (pet, task) order that matches the editor rows
    task_rows = [
        (pet, t)
        for pet in owner.pets
        for t in scheduler.sort_by_priority_then_time(pet.tasks)
    ]

    st.markdown("**Current tasks** — edit cells directly, then click **Save task edits**:")
    edited_df = st.data_editor(
        [
            {
                "Pet":            pet.name,
                "Task":           t.title,
                "Start":          t.time,
                "Duration (min)": t.duration_minutes,
                "Priority":       t.priority.name.capitalize(),
                "Due Date":       t.due_date,
                "Score":          round(scheduler.task_score(t), 1),
                "Done":           t.completed,
            }
            for pet, t in task_rows
        ],
        column_config={
            "Pet":            st.column_config.TextColumn(disabled=True),
            "Task":           st.column_config.TextColumn("Task"),
            "Start":          st.column_config.TextColumn("Start (HH:MM)"),
            "Duration (min)": st.column_config.NumberColumn(min_value=1, max_value=240, step=1),
            "Priority":       st.column_config.SelectboxColumn(
                                  "Priority", options=["Low", "Medium", "High"]
                              ),
            "Due Date":       st.column_config.DateColumn("Due Date"),
            "Score":          st.column_config.NumberColumn("Score", disabled=True, format="%.1f"),
            "Done":           st.column_config.CheckboxColumn("Done"),
        },
        hide_index=True,
        use_container_width=True,
        key="task_editor",
    )
    st.caption("💡 **Score** = priority value (1–3) × urgency multiplier (1.0–3.0). Higher score → scheduled first in weighted mode.")

    if st.button("Save task edits"):
        edited_rows = edited_df if isinstance(edited_df, list) else edited_df.to_dict("records")
        for i, (pet, task) in enumerate(task_rows):
            row = edited_rows[i]
            task.title           = str(row["Task"]) if row["Task"] else task.title
            task.time            = str(row["Start"]) if row["Start"] else task.time
            task.duration_minutes = int(row["Duration (min)"]) if row["Duration (min)"] else task.duration_minutes
            task.priority        = Priority[str(row["Priority"]).upper()] if row["Priority"] else task.priority
            due = row.get("Due Date")
            if due is None or pd.isna(due):
                task.due_date = None
            elif isinstance(due, date):
                task.due_date = due
            else:
                task.due_date = pd.Timestamp(due).date()
            task.completed = bool(row["Done"]) if row["Done"] is not None else task.completed
        owner.save_to_json()
        st.success("Tasks updated and saved!")
        st.rerun()

    # Surface conflict warnings immediately after the task table
    conflicts = scheduler.detect_conflicts()
    if conflicts:
        st.markdown("**Scheduling conflicts detected:**")
        for warning in conflicts:
            message = warning.replace("WARNING ", "")
            st.warning(f"⚠️ {message}")
    else:
        st.success("No scheduling conflicts.")
else:
    st.info("No tasks yet. Save an owner & pet, then add tasks above.")

st.divider()

# ── Section 3: Generate Schedule ──────────────────────────────────────────────
st.subheader("3. Generate Schedule")

use_weighted = st.toggle(
    "Use weighted scoring (priority × urgency)",
    value=False,
    help="When ON, tasks due soon receive a score boost and may be scheduled ahead of higher-priority tasks with no due date.",
)
if use_weighted:
    st.info("**Weighted mode:** score = priority value × urgency multiplier. A 🟢 Low task due *today* (score 3.0) beats a 🟡 Medium task with no due date (score 2.0).")

use_shared = st.toggle(
    "Count shared tasks once for same-species pets",
    value=False,
    help="When ON, tasks with the same name across pets of the same species (e.g., two dogs both have 'Morning walk') are counted as one time slot — the owner does them together.",
)
if use_shared:
    same_species_groups = {}
    if st.session_state.owner:
        for pet in st.session_state.owner.pets:
            same_species_groups.setdefault(pet.species, []).append(pet.name)
    shared_groups = [names for names in same_species_groups.values() if len(names) > 1]
    if shared_groups:
        group_str = ", ".join(" + ".join(names) for names in shared_groups)
        st.info(f"**Shared mode:** same-named tasks for [{group_str}] will be counted once in the time budget.")
    else:
        st.warning("No same-species pet groups found — add more pets of the same species for this option to take effect.")

if st.button("Generate schedule"):
    if st.session_state.owner is None:
        st.warning("Please save an owner & pet first.")
    elif not st.session_state.owner.all_pending_tasks():
        st.warning("No pending tasks to schedule. Add some tasks first.")
    else:
        scheduler = Scheduler(owner=st.session_state.owner)

        # Re-surface conflicts at schedule time so they aren't missed
        conflicts = scheduler.detect_conflicts()
        if conflicts:
            st.markdown("**Resolve these conflicts before finalising your plan:**")
            for warning in conflicts:
                message = warning.replace("WARNING ", "")
                st.warning(f"⚠️ {message}")

        plan = (
            scheduler.generate_weighted_plan(shared_species=use_shared)
            if use_weighted
            else scheduler.generate_plan(shared_species=use_shared)
        )

        # Summary metrics
        time_used = sum(t.duration_minutes for t in plan.scheduled_tasks)
        budget = owner.available_minutes_per_day
        s1, s2, s3 = st.columns(3)
        s1.metric("Scheduled", len(plan.scheduled_tasks), help="Tasks that fit in your time budget")
        s2.metric("Skipped", len(plan.skipped_tasks), help="Tasks that didn't fit")
        s3.metric("Time used", f"{time_used} / {budget} min")

        # Time budget progress bar
        progress_pct = min(time_used / budget, 1.0)
        st.progress(progress_pct, text=f"Time budget: {time_used} / {budget} min used")

        if plan.scheduled_tasks:
            st.markdown("**Scheduled tasks:**")
            time_elapsed = 0
            rows = []
            for t in plan.scheduled_tasks:
                row = {
                    "Task":        f"{task_icon(t.title)} {t.title}",
                    "Priority":    PRIORITY_EMOJI[t.priority.name],
                    "Start (min)": time_elapsed,
                    "End (min)":   time_elapsed + t.duration_minutes,
                    "Duration":    f"{t.duration_minutes} min",
                }
                if use_weighted:
                    row["Score"] = f"{scheduler.task_score(t):.1f}"
                    row["Due"] = urgency_label(t)
                rows.append(row)
                time_elapsed += t.duration_minutes
            st.dataframe(rows, use_container_width=True, hide_index=True)

        if plan.skipped_tasks:
            st.markdown("**Skipped (not enough time):**")
            for t in plan.skipped_tasks:
                st.warning(f"⏭️ {task_icon(t.title)} **{t.title}** {PRIORITY_EMOJI[t.priority.name]} — needs {t.duration_minutes} min")
