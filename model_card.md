# Model Card — PawPal+ AI Pet Care Advisor

> This model card covers the AI advisory component of **PawPal+**, which extends the base **PawPal** scheduling app with a Retrieval-Augmented Generation (RAG) pipeline powered by Google Gemini. It answers the reflection prompts for AI collaboration, system biases, evaluation results, and ethical considerations.

---

## Table of Contents

1. [Model Overview](#model-overview)
2. [Base Project](#base-project)
3. [Intended Use](#intended-use)
4. [How the AI Works](#how-the-ai-works)
5. [Testing and Evaluation Results](#testing-and-evaluation-results)
6. [Limitations and Biases](#limitations-and-biases)
7. [Ethical Considerations and Misuse](#ethical-considerations-and-misuse)
8. [AI Collaboration — Helpful and Flawed Moments](#ai-collaboration--helpful-and-flawed-moments)
9. [Reflection](#reflection)

---

## Model Overview

| Field | Detail |
|---|---|
| **Model name** | PawPal+ AI Pet Care Advisor |
| **Model type** | RAG pipeline + agentic 3-step workflow |
| **LLM backend** | Google Gemini (via `google-genai` SDK) |
| **Retriever** | Local keyword-weighted scorer (`PetCareRetriever`) |
| **Knowledge base** | 13 hand-authored chunks across `dog_care.json`, `cat_care.json`, `general_care.json` |
| **Fallback** | Rule-based task generation (0 LLM tokens) when API is unavailable |
| **Output** | One structured task suggestion per call: title, duration, priority, frequency, time, reason, quality score |
| **Human in the loop** | Yes — suggestions are never added automatically |

---

## Base Project

**PawPal** is the base project this AI layer was built on top of. It is a Python scheduling assistant for pet owners that:

- Lets owners register multiple pets and add care tasks with priorities, durations, and preferred start times
- Runs a greedy scheduling algorithm that fills a daily time budget with the highest-priority tasks first, detecting and surfacing time conflicts
- Supports priority/urgency-weighted scoring, recurring task generation (daily and weekly), and full data persistence via `data.json`
- Provides a Streamlit UI and a terminal demo (`main.py`)

The original system handled the full scheduling lifecycle but provided no guidance on *what* tasks to add. The AI advisory layer was built to answer exactly that question: *"What am I forgetting?"*

---

## Intended Use

**This system is designed for:** Personal, non-commercial use by individual pet owners who want help identifying gaps in their pet's daily care routine.

**This system is not designed for:** Veterinary diagnosis, medication guidance, emergency care advice, or any context where an incorrect suggestion could cause physical harm. It is a scheduling prompt, not medical counsel.

---

## How the AI Works

The advisor runs a 3-step agentic pipeline on every request:

| Step | Method | Tokens used |
|---|---|---|
| 1. Gap Detection | Keyword-match existing task titles against category dictionaries | **0** |
| 2. KB Retrieval + LLM Suggestion | Retrieve top KB chunk → build minimal prompt → call Gemini | **~60** |
| 3. Budget Trim | Greedy sort by priority, drop what doesn't fit in remaining time | **0** |

If Step 2's API call fails for any reason (rate limit, network error, invalid key), the system falls back to `_rule_based_suggest()`, which generates a task directly from the retrieved KB chunk using a pre-defined template. The UI labels which path was taken.

---

## Testing and Evaluation Results

### Automated Tests — 29 / 29 passed

Two test files run with `pytest` in 0.65 seconds, covering the scheduling engine and the AI advisory pure functions:

**`tests/test_pawpal.py` — 13 tests — Core scheduling engine**

| Group | What is verified |
|---|---|
| Task basics | `mark_complete()` flips flag; `add_task()` increments count |
| Sorting | Three tasks added out-of-order → correct priority-then-time output |
| Recurrence | Daily → due tomorrow; weekly → 7 days later; `"as needed"` → no follow-up |
| Conflict detection | Overlapping windows → 1 warning; same start → 1 warning; sequential → 0 |
| Scheduling edge cases | Empty pet → empty plan; exact budget → scheduled; overflow → skipped |

**`tests/test_advisor.py` — 16 tests — AI advisory layer (no API key required)**

| Group | What is verified |
|---|---|
| `_parse_json_response` (5) | Plain array; markdown fences stripped; `{"tasks":[...]}` unwrapped; plain dict wrapped in list; invalid JSON → `None` |
| `_validate_task` (5) | Valid input accepted; bad priority → `MEDIUM`; missing field → `None`; duration clamped at 240; bad time → `09:00` |
| `_quality_score` (3) | Complete suggestion → 1.0; minimal suggestion < 0.5; unreasonable duration reduces score |
| `_detect_gaps` (3) | No tasks → `exercise` flagged; walk task → `exercise` covered; feed task → `feeding` covered |

```
$ python3 -m pytest tests/ -v
...
29 passed in 0.65s
```

### Confidence Scoring

Every suggestion includes a `quality_score` (0.0–1.0) computed by `_quality_score()` using three signals:

| Signal | Weight | Criteria |
|---|---|---|
| Reason length | 0.4 | ≥ 50 chars = full; 20–49 chars = half |
| Title length | 0.3 | ≥ 10 chars = full; 5–9 chars = half |
| Duration range | 0.3 | 5–120 min = full; outside = 0 |

Observed during development:
- **LLM suggestions**: averaged **1.0** — Gemini reliably produces descriptive titles and multi-sentence reasons.
- **Rule-based fallback suggestions**: averaged **0.80** — KB-derived reasons are typically 40–48 characters, just under the 50-character threshold for full credit.

### Logging

Every API interaction is written to `ai_advisor.log`:
- Token counts (input + output) per call
- Elapsed time per LLM call
- Rate-limit events and fallback triggers
- Validation failures (which field, which task)
- Gap detection results (covered and missing categories)

Sample log output:
```
2026-04-28 10:14:03  INFO  advisor — PetCareAdvisor initialised (model=gemini-2.0-flash)
2026-04-28 10:14:03  INFO  advisor — [Step1-code] Covered: ['feeding'] | Gaps: ['exercise', 'grooming', 'health', 'enrichment']
2026-04-28 10:14:04  INFO  advisor — [Step2-Suggest] Gemini responded in 1.23s | in=58 out=47 tokens
2026-04-28 10:14:04  INFO  advisor — [Step2] 1/1 LLM suggestions validated
2026-04-28 10:14:04  INFO  advisor — === Done: 1 suggestions, avg_confidence=1.00, llm=True, pet=Buddy ===
```

### What Testing Revealed

**29 out of 29 tests passed.** Confidence scores averaged 1.0 for LLM suggestions and 0.80 for rule-based fallback suggestions. Accuracy of suggestion structure improved to 100% after adding `_validate_task` sanitisation and fixing the JSON parsing bug described below.

**What was harder to test:**
- The Streamlit UI cannot be unit tested with pytest — every UI change required manual walkthrough.
- Rate-limit behaviour could only be observed through live API calls, not simulated in tests.

---

## Limitations and Biases

### The knowledge base reflects whoever wrote it

The 13 KB chunks were authored by the developer, not sourced from a veterinary authority. They encode assumptions — 30 minutes of exercise per day for a dog, weekly grooming — that are reasonable averages but wrong for specific cases. A senior dog with arthritis should not exercise the same way as a healthy two-year-old; a Poodle requires more grooming than a Labrador. The system has no way to account for breed, age, weight, or health history. An owner who follows suggestions without their own judgement is over-trusting the system.

### Keyword gap detection is brittle

The gap detector checks task titles for exact keyword matches. A task titled "Puppy Playtime" does not trigger the `exercise` category because "puppy" and "playtime" are not in the keyword set `{"walk", "run", "jog", "exercise", "play", "fetch", "outdoor"}`. "Outdoor adventure" catches it; "Backyard time" does not. The system can flag a gap the owner has already covered and suggest a redundant task. The correct fix — a semantic similarity check using embeddings — was not implemented because it would add a second API dependency and more token cost.

### Only two species are supported

The knowledge base covers dogs and cats. Owners with rabbits, birds, guinea pigs, or reptiles receive only the thin `general_care.json` fallback (dental, hydration, daily observation). The suggestion quality for unsupported species is significantly lower.

### LLM suggestions carry cultural bias

Gemini's training data skews toward Western, urban, indoor-pet care norms. Suggested exercise durations, feeding schedules, and grooming routines reflect US expectations and may be inappropriate for working dogs, outdoor cats, or owners in different climates and living situations.

---

## Ethical Considerations and Misuse

### The realistic misuse risk is medical over-reliance

The system can suggest a `health` task such as "flea medication" or "weekly health check". An owner who reads this as authoritative advice — rather than as a scheduling prompt — could give incorrect medication, miss a health problem the system's categories can't detect, or delay professional care.

### Three design choices limit this risk

1. **Human-in-the-loop.** No suggestion is ever added automatically. The owner reads the suggestion, the reason, and the source KB snippet before clicking "Add". The friction is intentional.
2. **Transparency of source.** Every suggestion card shows the retrieved KB chunk it was based on. The owner can see exactly what fact the AI used and judge whether it applies to their specific pet.
3. **No dosage or diagnosis.** The knowledge base contains care routines, not treatment protocols. The advisor can suggest *that* a pet needs a health check — not *what* medication to give or at what dose.

### Future improvement

Explicitly label any `health`-category suggestion with a disclaimer ("Consult your vet before adding medication tasks") and gate the health category behind a one-time user acknowledgement. This was not implemented in the current version.

---

## AI Collaboration — Helpful and Flawed Moments

### Helpful — catching a multi-pet data loss bug before any user testing

When building the Owner & Pet Setup section, the AI assistant (Claude Code) identified that the line:

```python
st.session_state.owner = Owner(name=owner_name, pets=[new_pet])
```

would silently overwrite all existing pets every time the "Save" button was clicked. A second pet would replace the first rather than join it. The fix — checking whether an owner with that name already exists and calling `add_pet()` instead — was suggested and implemented before any user testing had revealed the problem. This was a non-obvious Streamlit session state bug that would have been difficult to debug after the fact.

### Flawed — the initial architecture used too many tokens

The AI's first design for the advisory pipeline was a three-step agentic workflow with a separate Gemini API call at each step: one call to identify gaps, one to generate suggestions, and one to validate and trim them. The architecture was technically clean and the code was correct — but it used approximately 1,700 tokens per request.

On Gemini's free tier (15 requests per minute, tight daily limits), this triggered rate limits almost immediately during development. The AI had optimised for architectural correctness, not for the operational constraints of a student project on a free API key. Multiple rounds of simplification were required — collapsing three calls into one, replacing two of three steps with pure code — to reach a practical design.

**The lesson:** AI assistants optimise for correctness, not for deployment constraints. Those constraints are the developer's responsibility to specify upfront.

### A testing surprise worth noting

The most significant surprise during reliability testing was that the LLM had been silently bypassed for an extended period. The `_parse_json_response` function returned `None` for a plain JSON object — the exact shape Gemini produces with the ultra-short prompt — so the fallback ran on every call while the UI appeared completely normal. Suggestions appeared, were well-formed, and could be added to the schedule. Nothing in the UI indicated the LLM was never being called. Only writing a targeted unit test for `_parse_json_response` revealed the bug. A system can appear to work correctly while a core feature is entirely broken.

---

## Reflection

### What this project taught me about AI

**Rate limits are a real engineering constraint, not an edge case.** The first instinct was to write a three-step pipeline with one LLM call per step. Hitting quota limits immediately forced a complete rethink — first combining steps, then replacing LLM calls with pure code wherever possible, finally implementing a fallback that makes the feature work even when the API is unavailable. The journey from ~1,700 tokens per request to ~60 tokens (or zero via fallback) was itself a design problem, not just an optimisation.

**RAG quality depends on retrieval quality, not just generation quality.** A sophisticated LLM producing an answer from a poor knowledge chunk is worse than a simple rule applied to a good one. Getting the keyword scorer right — weighting category keywords at 2.0×, title matches at 1.5×, body text at 1.0×, filtering by species — mattered more than prompt engineering.

**Agentic does not mean more LLM calls.** Steps 1 and 3 of the advisor are "agentic" in the sense that they are distinct reasoning stages with their own inputs and outputs — but they use zero tokens because they are implemented in code. An agentic workflow is a design pattern for decomposing a problem, not a mandate to call a language model at every step.

### What this project taught me about problem-solving

**Progressive simplification beats speculative optimisation.** The advisor started over-engineered and was simplified in response to real observed failures. Each simplification made the system more reliable without making it less capable.

**Persistence and error messages are features.** The first version of the app lost all data on page refresh. Replacing a generic "AI Advisor error" with a specific message ("your key belongs to a project with billing enabled — create a new key at aistudio.google.com") reduced debugging time more than any code change.

**Human-in-the-loop is not a limitation — it is the design.** The AI advisor never adds tasks automatically. That single choice makes the system safe to use with zero risk of polluting a real schedule with hallucinated or inappropriate suggestions. Keeping the human in the decision loop is not a concession to the AI's limitations — it is the correct architecture for a tool that affects real daily behaviour.
