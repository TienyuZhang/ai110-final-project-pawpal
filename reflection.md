# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

A user should be able to do the following actions:
- Add/manage pet tasks — enter a task (e.g., "Morning walk"), its duration, and priority level
- Generate a daily schedule — trigger the scheduler to produce an ordered plan based on available time and task priorities
- View the plan with reasoning — see which tasks were chosen, when they happen, and why

It will have the following classes: 
1) Owner
Attributes: name, available_minutes_per_day
Responsibility: Represents the human user and their time constraints

2) Pet
Attributes: name, species
Responsibility: Represents the pet being cared for; could later hold species-specific needs

3) Task
Attributes: title, duration_minutes, priority (low/medium/high)
Responsibility: Encapsulates a single care activity and its scheduling weight

4) Scheduler
Attributes: owner, pet, tasks: list[Task]
Methods: generate_plan() → Plan
Responsibility: Core logic — selects and orders tasks that fit within the owner's available time, prioritizing high-priority tasks first

5) Plan
Attributes: scheduled_tasks: list[Task], skipped_tasks: list[Task]
Methods: explain() → str
Responsibility: Holds the output of a scheduling run and can produce a human-readable explanation of decisions made

Relationships between the above classes:
Owner has one Pet
Scheduler takes an Owner, a Pet, and a list of Tasks
Scheduler.generate_plan() returns a Plan

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes
1) Originally owner assumes one pet. 
owner.pet: Pet is a single object. If the scope ever grows to multiple pets, this becomes a breaking change. A list[Pet] from the start is safer, so made the change. 

2) Scheduler lost its Pet reference
In the original UML, Scheduler takes owner, pet, and tasks. Currently it only holds owner and tasks. Because Pet is already accessible via owner.pet, this is technically reachable (but it's implicit).

3) Priority originally was an unvalidated string.
Task.priority is typed as str but valid values are "low", "medium", "high". Nothing enforces this. When generate_plan() sorts by priority, a typo like "hig" silently misbehaves. So I Replaced it with an Enum ( LOW = 1, MEDIUM = 2, HIGH = 3) to make comparisons and sorting reliable.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

Constraints my scheduler consider: 
1. Time budget (available_minutes_per_day)
The hard constraint. The scheduler tracks time_used and only adds a task if time_used + task.duration_minutes <= budget. Tasks that don't fit are moved to skipped.
2. Priority (Priority enum)
The ordering constraint. Before fitting tasks into the budget, candidates are sorted by priority.value descending — so HIGH tasks are always considered before MEDIUM or LOW ones.
3. Completion status (completed)
The filter constraint. Only pending_tasks() (where completed == False) are ever passed to the scheduler. Already-done tasks are invisible to it.

How it's decided:
1. Time is the hard wall — it's the only constraint that produces a firm yes/no. A task either fits or it doesn't. Everything else is about ordering within that wall.
2. Priority is the tiebreaker — when you can't fit everything, priority determines what gets sacrificed. A HIGH task (medication, feeding) failing to run has real consequences; a LOW task (enrichment toy) being skipped is acceptable. The Enum integer values make this comparison unambiguous and sortable.
3. Completion status is a pre-filter — there's no point running scheduling logic on tasks already done. Filtering first keeps the scheduler focused on what actually needs deciding.
4. Frequency (daily, weekly) and pet-specific preferences (e.g., species-based needs) are captured in the data model but not yet enforced by the scheduler — they're the natural next constraint to add once the core logic is stable.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

The tradeoff: Conflict detection is separate from scheduling
The scheduler detects conflicts and generates a plan as two independent steps — detect_conflicts() and generate_plan() — rather than blocking or auto-resolving conflicts before scheduling. If two tasks overlap, a warning is printed, but both tasks still enter the candidate pool and can both end up in the plan.
For example, you can see this in the output: "Morning walk" and "Give supplements" are flagged as conflicting, yet both appear in the final schedule.

Why this is reasonable here:
The owner, not the algorithm, should resolve conflicts. Pet care tasks often have legitimate overlap by design — a "give supplements" task during a walk is intentional multitasking, not a mistake. Auto-dropping one task because its start time collides would silently remove something that might be medically important.
Warnings preserve transparency. By surfacing conflicts as messages rather than hard stops, the scheduler gives the owner the information they need to decide: reschedule one task, merge them, or accept the overlap. The scheduler stays predictable and auditable — its behavior doesn't silently change based on conflict state.
The cost of a false block is higher than a false pass. Missing a medication because the scheduler quietly removed it is worse than seeing a warning and ignoring it. A lightweight warning strategy errs on the side of doing too much rather than too little.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
