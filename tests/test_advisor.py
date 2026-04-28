"""
Unit tests for the AI advisory layer.
All tests run without an API key — LLM-dependent methods are either
pure functions or are tested with a mocked genai.Client.
"""

from unittest.mock import MagicMock, patch

import pytest

from advisor import PetCareAdvisor, _parse_json_response, _quality_score, _validate_task
from pawpal_system import Priority, Task


# ── Fixture: advisor with mocked Gemini client ────────────────────────────────

@pytest.fixture
def advisor():
    """
    Return a PetCareAdvisor whose Gemini client is fully mocked.
    models.list() returns [] so _discover_model() falls back to PREFERRED_MODELS[0].
    """
    with patch("advisor.genai.Client") as MockClient:
        MockClient.return_value.models.list.return_value = []
        return PetCareAdvisor(api_key="test-key-for-unit-testing")


# ── _parse_json_response ──────────────────────────────────────────────────────

def test_parse_plain_json_array():
    """A plain JSON array is returned as-is."""
    raw = '[{"title": "Walk", "duration_minutes": 30}]'
    result = _parse_json_response(raw, "test")
    assert result == [{"title": "Walk", "duration_minutes": 30}]


def test_parse_strips_markdown_code_fences():
    """JSON wrapped in ```json ... ``` fences is unwrapped correctly."""
    raw = '```json\n[{"title": "Walk"}]\n```'
    result = _parse_json_response(raw, "test")
    assert result == [{"title": "Walk"}]


def test_parse_dict_with_tasks_key():
    """A {"tasks": [...]} envelope is unwrapped to the inner list."""
    raw = '{"tasks": [{"title": "Walk"}]}'
    result = _parse_json_response(raw, "test")
    assert result == [{"title": "Walk"}]


def test_parse_plain_dict_wrapped_in_list():
    """A plain single-object dict (common LLM response) is wrapped in a list."""
    raw = '{"title": "Walk", "duration_minutes": 30}'
    result = _parse_json_response(raw, "test")
    assert isinstance(result, list)
    assert result[0]["title"] == "Walk"


def test_parse_invalid_json_returns_none():
    """Malformed JSON returns None without raising."""
    result = _parse_json_response("not json at all {{", "test")
    assert result is None


# ── _validate_task ────────────────────────────────────────────────────────────

def test_validate_task_accepts_valid_input():
    """A fully-formed task dict passes validation unchanged."""
    raw = {
        "title": "Morning Walk",
        "duration_minutes": 30,
        "priority": "HIGH",
        "frequency": "daily",
        "time": "08:00",
        "reason": "Dogs need daily exercise.",
    }
    result = _validate_task(raw)
    assert result is not None
    assert result["title"] == "Morning Walk"
    assert result["priority"] == "HIGH"
    assert result["duration_minutes"] == 30


def test_validate_task_sanitizes_invalid_priority():
    """An unrecognised priority value is silently corrected to MEDIUM."""
    raw = {
        "title": "Walk", "duration_minutes": 30,
        "priority": "URGENT", "frequency": "daily",
        "time": "08:00", "reason": "Exercise.",
    }
    result = _validate_task(raw)
    assert result["priority"] == "MEDIUM"


def test_validate_task_returns_none_for_missing_field():
    """A task missing a required field (e.g. 'reason') returns None."""
    raw = {
        "title": "Walk", "duration_minutes": 30,
        "priority": "HIGH", "frequency": "daily",
        "time": "08:00",
        # "reason" is absent
    }
    result = _validate_task(raw)
    assert result is None


def test_validate_task_clamps_duration_above_max():
    """duration_minutes above 240 is clamped to 240."""
    raw = {
        "title": "Walk", "duration_minutes": 999,
        "priority": "HIGH", "frequency": "daily",
        "time": "08:00", "reason": "Exercise.",
    }
    result = _validate_task(raw)
    assert result["duration_minutes"] == 240


def test_validate_task_fixes_bad_time_format():
    """An invalid time string (e.g. '8am') is replaced with the default '09:00'."""
    raw = {
        "title": "Walk", "duration_minutes": 30,
        "priority": "HIGH", "frequency": "daily",
        "time": "8am", "reason": "Exercise.",
    }
    result = _validate_task(raw)
    assert result["time"] == "09:00"


# ── _quality_score ────────────────────────────────────────────────────────────

def test_quality_score_high_for_complete_suggestion():
    """A well-formed suggestion with a long reason and descriptive title scores 1.0."""
    task = {
        "title": "Morning Walk",          # 12 chars → +0.3
        "duration_minutes": 30,            # in 5–120 → +0.3
        "reason": "Dogs need at least 30 minutes of aerobic exercise daily to maintain a healthy weight.",  # >50 chars → +0.4
    }
    assert _quality_score(task) == 1.0


def test_quality_score_low_for_minimal_suggestion():
    """A task with a very short title and missing reason scores below 0.5."""
    task = {
        "title": "Go",       # 2 chars → 0
        "duration_minutes": 30,
        "reason": "Ok.",     # 3 chars → 0
    }
    score = _quality_score(task)
    assert score < 0.5


def test_quality_score_zero_for_unreasonable_duration():
    """A duration outside 5–120 minutes contributes 0 to the score."""
    task = {
        "title": "Marathon Training Session",  # >10 chars → +0.3
        "duration_minutes": 300,               # out of range → 0
        "reason": "Training for a marathon requires many hours of daily preparation.",  # >50 → +0.4
    }
    assert _quality_score(task) == 0.7


# ── _detect_gaps (needs mocked advisor) ──────────────────────────────────────

def test_detect_gaps_returns_exercise_when_no_tasks(advisor):
    """A pet with no tasks should have 'exercise' flagged as a gap (for dogs)."""
    gaps = advisor._detect_gaps([], species="dog")
    assert "exercise" in gaps


def test_detect_gaps_exercise_covered_by_walk_task(advisor):
    """A task titled 'morning walk' should mark 'exercise' as covered."""
    task = Task(
        title="morning walk", duration_minutes=30,
        priority=Priority.HIGH, frequency="daily", time="08:00",
    )
    gaps = advisor._detect_gaps([task], species="dog")
    assert "exercise" not in gaps


def test_detect_gaps_feeding_covered_by_feed_task(advisor):
    """A task titled 'feed buddy' should mark 'feeding' as covered."""
    task = Task(
        title="feed buddy", duration_minutes=10,
        priority=Priority.HIGH, frequency="daily", time="07:00",
    )
    gaps = advisor._detect_gaps([task], species="dog")
    assert "feeding" not in gaps
