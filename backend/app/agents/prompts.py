"""Loader for prompts.yaml — YAML for storage, Jinja2 for variables."""

from functools import lru_cache
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

_PROMPTS_FILE = Path(__file__).with_name("prompts.yaml")

# StrictUndefined: a missing variable is a bug — fail loudly, never send a
# prompt with silent blanks to the model.
_env = Environment(undefined=StrictUndefined)


@lru_cache(maxsize=1)
def _load() -> dict[str, str]:
    return yaml.safe_load(_PROMPTS_FILE.read_text(encoding="utf-8"))


def render_prompt(name: str, **variables) -> str:
    prompts = _load()
    # The style guide needs `language`, which the analysis prompt doesn't have
    # (it *produces* the language) — so only render it where it's referenced.
    if "{{ style_guide }}" in prompts[name]:
        variables["style_guide"] = _env.from_string(prompts["_style_guide"]).render(
            **variables
        )
    return _env.from_string(prompts[name]).render(**variables)
