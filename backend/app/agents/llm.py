"""Thin LangChain layer over OpenRouter.

One ChatOpenAI with a base_url override reaches every model; which model is
used per stage is pure config (settings.analysis_model / writing_model).
LangChain is kept to exactly two jobs: the API call and structured output —
all orchestration stays in plain Python (doc_generator.py).
"""

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import settings
from app.observability import get_langfuse


class LLMNotConfiguredError(RuntimeError):
    pass


def _chat(model: str) -> ChatOpenAI:
    if not settings.openrouter_api_key:
        raise LLMNotConfiguredError(
            "OPENROUTER_API_KEY is missing in .env — document generation needs it."
        )
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0.4,
        timeout=180,
        max_retries=2,  # transport-level retries (network, 5xx, rate limits)
    )


def _callbacks() -> list:
    if get_langfuse() is None:
        return []
    from langfuse.langchain import CallbackHandler

    return [CallbackHandler()]


def _wire_schema(schema: type[BaseModel]) -> dict:
    """JSON schema as sent to the provider, cleaned for cross-provider use:

    - $refs inlined ($defs indirection degrades nested-object compliance on
      some providers, e.g. Gemini returning strings instead of objects)
    - minItems/maxItems removed (Anthropic's structured-output API rejects
      values other than 0/1)

    The dropped constraints still hold — schema.model_validate() enforces
    them locally on the way back."""
    raw = schema.model_json_schema()
    defs = raw.get("$defs", {})

    def clean(node):
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].rsplit("/", 1)[-1]
                return clean(defs[name])
            return {
                k: clean(v)
                for k, v in node.items()
                if k not in ("minItems", "maxItems", "$defs")
            }
        if isinstance(node, list):
            return [clean(n) for n in node]
        return node

    return clean(raw)


def generate_structured[T: BaseModel](
    prompt: str, schema: type[T], model: str, trace_name: str
) -> T:
    """One prompt -> one validated schema instance.

    Preferred mode is json_schema (OpenRouter structured outputs): the model
    emits constrained JSON directly, which sidesteps the tool-call
    translation layer — observed with Claude via OpenRouter to mangle
    list-of-string arguments (items collapsed or replaced by '<UNKNOWN>').
    function_calling stays as the fallback for providers without json_schema
    support, with one final validation-feedback retry. No V1-style edit
    loops beyond that.
    """
    llm = _chat(model)
    config = {"callbacks": _callbacks(), "run_name": trace_name}
    wire = _wire_schema(schema)
    last_error: Exception | None = None
    for method in ("json_schema", "function_calling"):
        try:
            raw = llm.with_structured_output(wire, method=method).invoke(
                [HumanMessage(prompt)], config=config
            )
            return schema.model_validate(raw)
        except Exception as exc:  # unsupported method, mangled output, ...
            last_error = exc
    retry_prompt = (
        f"{prompt}\n\nYour previous attempt failed validation with:\n"
        f"{last_error}\nProduce a valid response this time."
    )
    raw = llm.with_structured_output(wire, method="function_calling").invoke(
        [HumanMessage(retry_prompt)], config=config
    )
    return schema.model_validate(raw)
