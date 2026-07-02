"""Render structured LLM output into Tiptap documents.

The document STRUCTURE (headings, section order, the static coaching flow of
the next-session sheet) is fixed here in code — the model only ever produced
content fields. This is V1's template layout, minus the char-counting.

Tiptap JSON is ProseMirror's document format: nested nodes with optional
text marks. Only nodes from StarterKit are used (heading, paragraph,
bulletList, orderedList) so the editor can always represent what we store.
"""

from app.agents.doc_schemas import Homework, NextSessionPrep, SessionSummary

# --- node helpers ---


def text(value: str, *marks: str) -> dict:
    node = {"type": "text", "text": value}
    if marks:
        node["marks"] = [{"type": m} for m in marks]
    return node


def heading(level: int, value: str) -> dict:
    return {"type": "heading", "attrs": {"level": level}, "content": [text(value)]}


def paragraph(*inline: dict) -> dict:
    return {"type": "paragraph", "content": list(inline)}


def _list(node_type: str, items: list[list[dict]]) -> dict:
    return {
        "type": node_type,
        "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": inline}]}
            for inline in items
        ],
    }


def bullets(items: list[str]) -> dict:
    return _list("bulletList", [[text(i)] for i in items])


def numbered(items: list[str]) -> dict:
    return _list("orderedList", [[text(i)] for i in items])


def doc(*content: dict) -> dict:
    return {"type": "doc", "content": [c for c in content if c is not None]}


# --- document builders ---


def render_summary(s: SessionSummary) -> dict:
    return doc(
        heading(1, s.title),
        paragraph(text(s.warm_opening)),
        heading(2, "Main Takeaways"),
        _list(
            "bulletList",
            [
                [text(t.theme, "bold"), text(" — " + t.insight)]
                if t.theme
                else [text(t.insight)]
                for t in s.main_takeaways
            ],
        ),
        heading(2, "Tools"),
        bullets(s.tools),
        heading(2, "Most Recent Achievements!"),
        bullets(s.achievements),
        paragraph(text(s.achievements_acknowledgment)),
        heading(2, "Next Steps"),
        bullets(s.next_steps),
    )


def render_homework(h: Homework) -> dict:
    return doc(
        heading(1, f"Homework: {h.theme}"),
        paragraph(text("Goal: ", "bold"), text(h.goal)),
        paragraph(text("Time needed: ", "bold"), text(h.time_needed)),
        heading(2, "Instructions"),
        paragraph(text(h.instructions)),
        heading(2, "Before you begin"),
        bullets(h.before_you_begin),
        heading(2, "Prompt Questions"),
        numbered(h.prompt_questions),
        paragraph(text(h.closing, "italic")) if h.closing else None,
    )


def render_next_session(n: NextSessionPrep, client_first_name: str) -> dict:
    """Static session flow (V1 template, kept verbatim in spirit) with the
    model's client-specific fills marked bold under each step."""

    def dynamic(label: str, value: str) -> dict:
        return paragraph(text(f"{label}: ", "bold"), text(value))

    return doc(
        heading(1, f"Next Session — {client_first_name}"),
        paragraph(text("Regular Session · 50 minutes")),
        heading(2, "1. Greeting / Check-In"),
        bullets(
            [
                "Ask how their day/week has been",
                "Notice emotional tone or energy",
                "Create a grounded, safe atmosphere",
            ]
        ),
        heading(2, "2. Guided Check-In (3 deep breaths)"),
        paragraph(
            text(
                "Guide the client through 3 slow breaths. Record: emotions they "
                "name, tension or relaxation, any topic that surfaces naturally."
            )
        ),
        heading(2, "3. Homework Assessment"),
        paragraph(
            text(
                "Explore their relationship with the previous homework. "
                "Didn't do it → calm neutrality, explore gently why. "
                "Did it → What felt surprising? What came up emotionally? "
                "What felt easy or hard?"
            )
        ),
        dynamic("Previous homework", n.previous_homework),
        heading(2, "4. Main Focus of the Session"),
        paragraph(
            text(
                "Adapt to where they are in the Point A → Point B journey, what "
                "emerged last session, whether they are stuck, emotional, or "
                "needing clarity."
            )
        ),
        dynamic("Concept to introduce (as needed)", n.suggested_concept),
        dynamic("Practical exercise(s)", n.suggested_exercises),
        heading(2, "5. Emerging Topics / Client-Led Exploration"),
        dynamic("Topics the client wants to discuss", n.client_topics),
        heading(2, "6. Wrap-Up & Integration"),
        paragraph(
            text(
                "Summarize the main discoveries, any shifts in clarity, emotion "
                "or direction, and what the client is taking with them."
            )
        ),
        heading(2, "7. Next Steps"),
        dynamic("Agreed pathway forward", n.next_steps),
        heading(2, "8. Homework"),
        dynamic("Suggested homework", n.suggested_homework),
        heading(2, "9. Final Acknowledgment"),
        paragraph(
            text(
                "Close with appreciation for their openness, recognition of "
                "their courage and commitment, and a warm tone that reinforces "
                "safety and progress."
            )
        ),
    )
