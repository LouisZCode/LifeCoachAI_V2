"""Structured-output schemas for the document pipeline.

These ARE the templates (V2 principle: templates are Pydantic schemas, not
.docx files re-read as tokens). Field descriptions carry V1's proven section
briefs and soft length guidance; hard formatting is applied later by the
renderer, so the model only ever writes content.

All prose fields are plain text — no markdown, no JSON nesting inside strings.
"""

import re
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def _coerce_str_list(value):
    """Repair the ways models mangle list-of-string fields under function
    calling — observed with Claude via OpenRouter: items joined into one
    newline/bullet string, or tool-call XML leaking into values
    ('<parameter name="item">...</parameter>'). Normalize everything to one
    string, split on tags/newlines, strip bullet markers."""
    if isinstance(value, list):
        value = "\n".join(str(v) for v in value)
    if not isinstance(value, str):
        return value
    parts = re.split(r"</?parameter[^>]*>|\n", value)
    items = [re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", p).strip() for p in parts]
    return [item for item in items if item]


StrList = Annotated[list[str], BeforeValidator(_coerce_str_list)]


def _coerce_theme_pair(body_field: str):
    """Safety net for {theme, <body>} objects that some models emit as one
    plain string: split 'Theme — body' / 'Theme: body' when the prefix looks
    like a heading, else keep everything as the body with an empty theme."""

    def coerce(value):
        if not isinstance(value, str):
            return value
        for sep in (" — ", ": ", " - "):
            head, _, rest = value.partition(sep)
            if rest and len(head) <= 60:
                return {"theme": head.strip(), body_field: rest.strip()}
        return {"theme": "", body_field: value.strip()}

    return BeforeValidator(coerce)


# --- Stage 1: analysis (the only stage that sees the transcript) ---


class KeyMoment(BaseModel):
    theme: str = Field(description="Short theme of this moment, 2-5 words.")
    detail: str = Field(
        description="What happened / what was discovered, 1-3 sentences, factual."
    )
    client_quote: str = Field(
        default="",
        description="Short verbatim quote from the client for this moment, if a "
        "strong one exists. Empty string if none.",
    )


class SessionAnalysis(BaseModel):
    """Faithful extraction of what actually happened in the session."""

    session_language: str = Field(
        description="Language the client mostly speaks in the session, e.g. "
        "'German' or 'English'. All client-facing documents will be written "
        "in this language."
    )
    emotional_tone: str = Field(
        description="How the client showed up today (energy, mood, openness), "
        "1-2 sentences."
    )
    key_moments: list[Annotated[KeyMoment, _coerce_theme_pair("detail")]] = Field(
        description="3-6 most important moments: insights, breakthroughs, "
        "recurring patterns, decisions."
    )
    tools_used: StrList = Field(
        description="Coaching tools/frameworks/exercises the coach actually used "
        "in this session (e.g. breathing exercise, values mapping, belief work). "
        "Name + a few words of context each. Empty list if none."
    )
    achievements: StrList = Field(
        description="Concrete progress and wins the client reported or showed, "
        "since last session or during this one. One short sentence each."
    )
    agreed_homework: str = Field(
        description="The homework/practice that coach and client agreed on for "
        "the coming period, as concretely as it was discussed. If nothing was "
        "agreed, say what would naturally follow from the session."
    )
    open_threads: StrList = Field(
        description="Topics that were opened but not finished, or that the "
        "client said they want to talk about later."
    )
    previous_homework: str = Field(
        default="",
        description="What the previous homework was and how the client engaged "
        "with it, if it was discussed. Empty string if not mentioned."
    )


# --- Stage 2: client-facing documents (written from the analysis) ---


class Takeaway(BaseModel):
    theme: str = Field(description="Takeaway header, 2-6 words.")
    insight: str = Field(
        description="1-2 sentences on this insight from THIS session, using the "
        "client's own words where possible."
    )


class SessionSummary(BaseModel):
    """Post-session summary the client receives. Warm, personal, specific."""

    title: str = Field(
        description="Session theme in 3-6 words, like a chapter title. "
        "Example: 'Reconnecting With Your Why'."
    )
    warm_opening: str = Field(
        description="2-3 sentences acknowledging how the client showed up today. "
        "Address them by first name. Warm and personal, about 100-200 characters."
    )
    main_takeaways: list[Annotated[Takeaway, _coerce_theme_pair("insight")]] = Field(
        min_length=3,
        max_length=3,
        description="Exactly 3 key insights from this session."
    )
    tools: StrList = Field(
        min_length=2,
        max_length=4,
        description="2-3 frameworks/exercises used in the session, a few words "
        "each, so the client remembers what you did together."
    )
    achievements: StrList = Field(
        min_length=2,
        max_length=6,
        description="3-5 short bullets celebrating concrete progress. "
        "Specific to this client, never generic."
    )
    achievements_acknowledgment: str = Field(
        description="One warm closing sentence acknowledging the progress above."
    )
    next_steps: StrList = Field(
        min_length=1,
        max_length=4,
        description="1-3 bullets about what is coming next (homework, focus, "
        "next session)."
    )


class Homework(BaseModel):
    """The homework sheet for the coming period."""

    theme: str = Field(
        description="Homework theme, 2-6 words. Example: 'Identifying Blockages "
        "& Next Steps'. Rendered as 'Homework: <theme>'."
    )
    goal: str = Field(
        description="One sentence capturing the purpose of this reflection, "
        "about 80-200 characters."
    )
    time_needed: str = Field(
        description="Realistic time estimate, e.g. '15-20 minutes'."
    )
    instructions: str = Field(
        description="Brief context: what the task is about and how it supports "
        "their journey. Warm and personal, use the client's exact words for "
        "their goals, about 150-350 characters."
    )
    before_you_begin: StrList = Field(
        min_length=3,
        max_length=5,
        description="3-4 short grounding bullets (quiet space, slow breaths, "
        "honesty and self-compassion, notice resistance with kindness — adapt "
        "to this client)."
    )
    prompt_questions: StrList = Field(
        min_length=3,
        max_length=6,
        description="3-5 reflection questions matching the homework that was "
        "agreed in the session. Personal and actionable, not generic."
    )
    closing: str = Field(
        default="",
        description="Optional brief encouragement, one sentence. Empty string "
        "to omit."
    )


class NextSessionPrep(BaseModel):
    """Dynamic parts of Maria's next-session preparation sheet. The static
    session flow (greeting, breathing check-in, wrap-up...) lives in the
    renderer — the model only fills what is client-specific."""

    previous_homework: str = Field(
        description="The homework that was just assigned, so the coach can "
        "assess it next time. About 100-200 characters."
    )
    suggested_concept: str = Field(
        description="A concept worth introducing next session given where the "
        "client is (belief systems, self-sabotage, values/identity, "
        "fear/resistance, locus of control...). Name it and say why, about "
        "150-300 characters."
    )
    suggested_exercises: str = Field(
        description="1-2 practical exercises for next session, tailored to this "
        "client (limiting beliefs, values mapping, SMART refinement, "
        "visualization...). About 150-300 characters."
    )
    client_topics: str = Field(
        description="Topics the client mentioned wanting to discuss, from the "
        "open threads. About 100-200 characters."
    )
    next_steps: str = Field(
        description="The agreed pathway forward, keeping their Point A to "
        "Point B journey in mind. About 150-300 characters."
    )
    suggested_homework: str = Field(
        description="A homework idea to assign at the END of the next session, "
        "building on the current one. About 100-200 characters."
    )
