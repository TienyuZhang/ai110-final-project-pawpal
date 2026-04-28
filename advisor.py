"""
AI Pet Care Advisor for PawPal+.

Implements a 3-step agentic workflow powered by the Google Gemini API
(free tier — no billing required, get a key at aistudio.google.com):

  Step 1 — Analyze   : Gemini identifies which care categories are missing
                        from the pet's current task list.
  Step 2 — Suggest   : Retrieved KB chunks for those gaps are fed to Gemini,
                        which generates specific, structured task suggestions.
  Step 3 — Validate  : Code checks whether suggestions fit the remaining time
                        budget. If they overflow, a third Gemini call trims and
                        re-prioritizes so the final plan is always actionable.

Every call is logged (timestamp, tokens used, retrieved chunks, outcomes).
All Gemini responses are validated and sanitized before reaching the UI.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

from google import genai

from retriever import PetCareRetriever

# ── Logging setup ─────────────────────────────────────────────────────────────

LOG_FILE = Path(__file__).parent / "ai_advisor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),       # also echo to console / Streamlit terminal
    ],
)
logger = logging.getLogger("advisor")

# ── Constants ─────────────────────────────────────────────────────────────────

# Ordered preference list — first available model wins at runtime
PREFERRED_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-flash-latest",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-lite-001",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
]
MAX_TOKENS     = 1024
VALID_PRIORITIES  = {"HIGH", "MEDIUM", "LOW"}
VALID_FREQUENCIES = {"daily", "weekly", "as needed"}
TIME_RE        = re.compile(r"^\d{2}:\d{2}$")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_json_response(raw: str, context: str) -> list[dict] | None:
    """
    Safely extract a JSON array from the model's response.
    Strips optional markdown code fences, then handles three shapes:
      - list of dicts  → returned as-is
      - {"tasks": [...]} wrapper → unwrapped
      - plain single dict → wrapped in a list
    Returns None on parse failure (caller decides how to handle).
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("tasks") or [data]   # unwrap or wrap
        logger.warning("[%s] Unexpected JSON shape: %s", context, type(data))
        return None
    except json.JSONDecodeError as exc:
        logger.error("[%s] JSON parse error: %s | raw: %s", context, exc, raw[:200])
        return None


def _quality_score(task: dict) -> float:
    """
    Return a 0.0–1.0 quality score for a validated task suggestion.
    Three signals: reason length (0.4), title length (0.3), duration range (0.3).
    """
    score = 0.0
    reason_len = len(task.get("reason", ""))
    if reason_len >= 50:
        score += 0.4
    elif reason_len >= 20:
        score += 0.2
    title_len = len(task.get("title", ""))
    if title_len >= 10:
        score += 0.3
    elif title_len >= 5:
        score += 0.15
    duration = task.get("duration_minutes", 0)
    if 5 <= duration <= 120:
        score += 0.3
    return round(min(score, 1.0), 2)


def _validate_task(raw: dict) -> dict | None:
    """
    Validate and sanitize a single task dict produced by Claude.
    Returns a clean dict or None if the task is structurally invalid.
    """
    required = {"title", "duration_minutes", "priority", "frequency", "time", "reason"}
    if not required.issubset(raw.keys()):
        missing = required - raw.keys()
        logger.warning("Task missing fields %s: %s", missing, raw.get("title", "?"))
        return None

    priority = str(raw["priority"]).strip().upper()
    if priority not in VALID_PRIORITIES:
        priority = "MEDIUM"

    frequency = str(raw["frequency"]).strip().lower()
    if frequency not in VALID_FREQUENCIES:
        frequency = "daily"

    time_str = str(raw["time"]).strip()
    if not TIME_RE.match(time_str):
        time_str = "09:00"

    try:
        duration = max(1, min(240, int(raw["duration_minutes"])))
    except (ValueError, TypeError):
        duration = 15

    return {
        "title":            str(raw["title"]).strip()[:80],
        "duration_minutes": duration,
        "priority":         priority,
        "frequency":        frequency,
        "time":             time_str,
        "reason":           str(raw.get("reason", "")).strip()[:200],
    }


# ── Main advisor class ────────────────────────────────────────────────────────

class PetCareAdvisor:
    """
    Orchestrates the 3-step agentic RAG workflow for generating pet care
    task recommendations.
    """

    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            raise ValueError(
                "GOOGLE_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com and add it to your .env file."
            )
        self.client    = genai.Client(api_key=key)
        self.model     = self._discover_model()
        self.retriever = PetCareRetriever()
        logger.info("PetCareAdvisor initialised (model=%s)", self.model)

    def _discover_model(self) -> str:
        """
        List models available to this API key and return the best match from
        PREFERRED_MODELS. Falls back to the first generateContent-capable model
        if none of the preferred names are available.
        """
        try:
            available: dict[str, object] = {}
            for m in self.client.models.list():
                name = m.name.replace("models/", "")
                methods = getattr(m, "supported_generation_methods", None) or []
                if not methods or "generateContent" in methods:
                    available[name] = m

            logger.info("Models available on this key: %s", sorted(available))

            for preferred in PREFERRED_MODELS:
                if preferred in available:
                    logger.info("Selected model: %s", preferred)
                    return preferred

            # No preferred model found — pick any flash model, then any model
            for name in sorted(available):
                if "flash" in name:
                    logger.warning("Preferred model unavailable; using %s", name)
                    return name
            if available:
                fallback = sorted(available)[0]
                logger.warning("No flash model found; using %s", fallback)
                return fallback

        except Exception as exc:
            logger.warning("Model discovery failed (%s); using default.", exc)

        return PREFERRED_MODELS[0]  # last-resort guess

    # ── Internal LLM call ────────────────────────────────────────────────────

    def _call_llm(self, prompt: str, step_label: str) -> str:
        """
        Send a single-turn message to Gemini and return the text response.
        Raises on any error so the caller can fall back gracefully.
        Logs token usage and elapsed time.
        """
        t0 = time.time()
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            elapsed = round(time.time() - t0, 2)
            text    = response.text or ""
            meta    = response.usage_metadata
            logger.info(
                "[%s] Gemini responded in %.2fs | in=%d out=%d tokens",
                step_label, elapsed,
                meta.prompt_token_count, meta.candidates_token_count,
            )
            return text
        except Exception as exc:
            logger.error("[%s] Gemini API error: %s", step_label, exc)
            raise

    # ── Step 1: Detect care gaps in code (zero tokens) ────────────────────────

    # Keywords that signal a task covers a given care category
    _CATEGORY_KEYWORDS: dict[str, set[str]] = {
        "exercise":   {"walk", "run", "jog", "exercise", "play", "fetch", "outdoor"},
        "feeding":    {"feed", "food", "meal", "treat", "water", "kibble"},
        "grooming":   {"brush", "groom", "bath", "wash", "nail", "trim", "coat"},
        "health":     {"medication", "medicine", "pill", "supplement", "vet", "doctor", "flea"},
        "enrichment": {"train", "training", "session", "enrichment", "puzzle", "toy"},
        "hygiene":    {"litter", "scoop", "clean", "toilet"},
    }

    def _detect_gaps(self, current_tasks, species: str) -> list[str]:
        """
        Pure-code gap detection — no LLM call, zero tokens.
        Checks each existing task title against keyword sets and returns
        categories that have no matching task.
        """
        all_cats = self.retriever.all_categories(species=species)
        covered: set[str] = set()
        for task in current_tasks:
            words = set(task.title.lower().split())
            for cat, keywords in self._CATEGORY_KEYWORDS.items():
                if words & keywords:
                    covered.add(cat)
        gaps = [c for c in all_cats if c not in covered]
        logger.info("[Step1-code] Covered: %s | Gaps: %s", sorted(covered), gaps)
        return gaps

    # ── Step 2: LLM suggestion with rule-based fallback ───────────────────────

    # Default task shape for each care category used when LLM is unavailable
    _CATEGORY_TEMPLATES: dict[str, dict] = {
        "exercise":   {"duration_minutes": 30, "priority": "HIGH",   "frequency": "daily",    "time": "08:00"},
        "feeding":    {"duration_minutes": 15, "priority": "HIGH",   "frequency": "daily",    "time": "07:00"},
        "grooming":   {"duration_minutes": 20, "priority": "MEDIUM", "frequency": "weekly",   "time": "10:00"},
        "health":     {"duration_minutes": 10, "priority": "HIGH",   "frequency": "weekly",   "time": "09:00"},
        "enrichment": {"duration_minutes": 20, "priority": "MEDIUM", "frequency": "daily",    "time": "17:00"},
        "hygiene":    {"duration_minutes": 10, "priority": "MEDIUM", "frequency": "daily",    "time": "08:00"},
        "play":       {"duration_minutes": 20, "priority": "MEDIUM", "frequency": "daily",    "time": "16:00"},
        "litter":     {"duration_minutes": 10, "priority": "HIGH",   "frequency": "daily",    "time": "08:00"},
    }

    def _rule_based_suggest(
        self, species: str, gap_categories: list[str], chunks: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Generate one task from KB chunk + template — zero LLM tokens."""
        gap  = gap_categories[0]
        tmpl = self._CATEGORY_TEMPLATES.get(
            gap, {"duration_minutes": 15, "priority": "MEDIUM", "frequency": "daily", "time": "09:00"}
        )
        reason = ""
        if chunks:
            reason = chunks[0]["content"].split(".")[0].strip()[:200]
        task = {
            "title":  f"{gap.capitalize()} session",
            **tmpl,
            "reason": reason or f"Regular {gap} supports your {species}'s wellbeing.",
        }
        logger.info("[Fallback] Rule-based task generated for gap=%s species=%s", gap, species)
        return [task], chunks, False   # (suggestions, chunks, llm_used)

    def _suggest_tasks(
        self,
        species: str,
        gap_categories: list[str],
    ) -> tuple[list[dict], list[dict], bool]:
        """
        RAG-grounded suggestion: retrieves one KB chunk, tries a single LLM
        call to generate a task, and falls back to rule-based generation if
        the API is unavailable or rate-limited (zero extra tokens).
        Returns (suggestions, chunks, llm_used).
        """
        query  = " ".join(gap_categories[:2]) + f" {species}"
        chunks = self.retriever.retrieve(query, species=species, top_k=1)

        kb_tip = ""
        if chunks:
            snippet = chunks[0]["content"][:80].rsplit(" ", 1)[0]
            kb_tip  = snippet + "."

        gap = gap_categories[0]

        prompt = (
            f"Suggest one {gap} task for a {species}. "
            f"Fact: {kb_tip} "
            f'JSON only: {{"title":"...","duration_minutes":10,'
            f'"priority":"HIGH","frequency":"daily","time":"08:00","reason":"..."}}'
        )

        try:
            raw       = self._call_llm(prompt, step_label="Step2-Suggest")
            raw_tasks = _parse_json_response(raw, "suggest_tasks") or []
            validated = [v for t in raw_tasks if (v := _validate_task(t)) is not None]
            if validated:
                logger.info("[Step2] %d/%d LLM suggestions validated", len(validated), len(raw_tasks))
                return validated, chunks, True
            logger.warning("[Step2] LLM returned no valid tasks; using rule-based fallback")
        except Exception as exc:
            logger.warning("[Step2] LLM unavailable (%s); using rule-based fallback", exc)

        return self._rule_based_suggest(species, gap_categories, chunks)

    # ── Step 3: Budget trim in code (zero tokens) ─────────────────────────────

    def _trim_to_budget(self, suggestions: list[dict], budget_remaining: int) -> list[dict]:
        """
        Pure-code greedy trim — no LLM call, zero tokens.
        Keeps HIGH-priority tasks first, drops whatever doesn't fit.
        """
        total = sum(s["duration_minutes"] for s in suggestions)
        if total <= budget_remaining:
            logger.info("[Step3-code] All suggestions fit (%d/%d min)", total, budget_remaining)
            return suggestions
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        sorted_s = sorted(suggestions, key=lambda s: priority_order.get(s["priority"], 1))
        result, used = [], 0
        for s in sorted_s:
            if used + s["duration_minutes"] <= budget_remaining:
                result.append(s)
                used += s["duration_minutes"]
        logger.info("[Step3-code] Trimmed to %d tasks, %d min", len(result), used)
        return result

    # ── Public entry points ───────────────────────────────────────────────────

    def recommend_tasks(
        self,
        pet_name: str,
        species: str,
        current_tasks,
        budget_minutes: int,
    ) -> dict:
        """
        Full 3-step agentic workflow: analyze → retrieve & suggest → validate.

        Returns a dict:
          {
            "suggestions":      list[dict],   # final validated task suggestions
            "retrieved_chunks": list[dict],   # KB chunks used (for UI transparency)
            "gap_categories":   list[str],    # care gaps Claude identified
            "steps_taken":      int,          # how many LLM calls were made
            "timestamp":        str,
          }
        """
        logger.info("=== recommend_tasks: pet=%s species=%s budget=%d ===", pet_name, species, budget_minutes)
        timestamp = datetime.now().isoformat(timespec="seconds")
        steps = 0

        # ── Steps 1+2: Analyze gaps and suggest tasks in one LLM call ───────────
        already_used = sum(t.duration_minutes for t in current_tasks)
        budget_remaining = max(0, budget_minutes - already_used)

        # ── Step 1: detect gaps in code (0 tokens) ───────────────────────────
        gap_categories = self._detect_gaps(current_tasks, species)
        steps += 1

        if not gap_categories:
            logger.info("No care gaps found for %s", pet_name)
            return {
                "suggestions":      [],
                "retrieved_chunks": [],
                "gap_categories":   [],
                "steps_taken":      steps,
                "timestamp":        timestamp,
                "message":          f"Great job! {pet_name}'s schedule already covers all care categories.",
            }

        # ── Step 2: one lean LLM call grounded in retrieved KB chunk ─────────
        suggestions, retrieved_chunks, llm_used = self._suggest_tasks(species, gap_categories)
        steps += 1

        # ── Step 3: trim to budget in code (0 tokens) ────────────────────────
        suggestions = self._trim_to_budget(suggestions, budget_remaining)

        # Attach a quality score (0.0–1.0) to each suggestion
        for s in suggestions:
            s["quality_score"] = _quality_score(s)
        avg_confidence = (
            round(sum(s["quality_score"] for s in suggestions) / len(suggestions), 2)
            if suggestions else 0.0
        )

        logger.info(
            "=== Done: %d suggestions, avg_confidence=%.2f, llm=%s, pet=%s ===",
            len(suggestions), avg_confidence, llm_used, pet_name,
        )
        return {
            "suggestions":      suggestions,
            "retrieved_chunks": retrieved_chunks,
            "gap_categories":   gap_categories,
            "steps_taken":      steps,
            "llm_used":         llm_used,
            "avg_confidence":   avg_confidence,
            "timestamp":        timestamp,
            "message":          None,
        }
