"""Strip non-standard agno fields from tool declarations and recover malformed arguments.

1. Outgoing Tool Definitions:
   Agno's Function model serializes internal workflow control fields:
   - requires_confirmation
   - external_execution
   - approval_type
   Strict OpenAI-compatible endpoints (like Google Gemini) reject these with HTTP 400.
   This module removes them from outgoing tool schemas sent to upstream APIs.

2. Incoming Tool Call Arguments:
   When streaming tool calls, Gemini or LiteLLM sometimes concatenates multiple JSON
   argument objects into a single string (e.g. `{"symbol":"RELIANCE"...}{"interval":"D"...}`).
   Agno's `LiteLLM.parse_tool_calls` catches `JSONDecodeError` and falls back to
   `{"text": "..."}`, which causes pydantic validation errors ("Missing: symbol. Unexpected: text").
   This module repairs those arguments so valid JSON dictionaries are recovered.
"""

from __future__ import annotations

import functools
import importlib
import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from utils.logging import get_logger
from utils.real_threading import Lock

logger = get_logger(__name__)

NON_STANDARD_TOOL_FUNCTION_FIELDS = frozenset(
    {
        "requires_confirmation",
        "external_execution",
        "approval_type",
    }
)

_MARKER = "_openalgo_tools_cleaned"
_install_lock = Lock()
_installed = False


def clean_tool_dict(tool: Any) -> Any:
    """Return a copy of a tool definition without non-standard internal fields."""
    if not isinstance(tool, Mapping) or tool.get("type") != "function":
        return tool

    fn = tool.get("function")
    if not isinstance(fn, Mapping):
        return tool

    needs_cleaning = any(key in fn for key in NON_STANDARD_TOOL_FUNCTION_FIELDS)
    if not needs_cleaning:
        return tool

    cleaned_fn = dict(fn)
    for key in NON_STANDARD_TOOL_FUNCTION_FIELDS:
        cleaned_fn.pop(key, None)

    return {**tool, "function": cleaned_fn}


def clean_tools(tools: Any) -> Any:
    """Sanitize a list of tool definitions for upstream provider APIs."""
    if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
        return tools
    return [clean_tool_dict(tool) for tool in tools]


def _recover_json_object(raw_str: str) -> dict[str, Any] | None:
    """Extract a valid JSON object from a string with concatenated JSON or extra text."""
    if not isinstance(raw_str, str):
        return None
    s = raw_str.strip()
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    start_idx = s.find("{")
    if start_idx != -1:
        decoder = json.JSONDecoder()
        try:
            obj, _ = decoder.raw_decode(s[start_idx:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    last_idx = s.rfind("{")
    if last_idx != -1 and last_idx != start_idx:
        decoder = json.JSONDecoder()
        try:
            obj, _ = decoder.raw_decode(s[last_idx:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    return None


def _patch_litellm_completion(litellm_module: Any) -> bool:
    """Wrap litellm.completion and litellm.acompletion to sanitize tools."""
    if litellm_module is None:
        return False

    original_completion = getattr(litellm_module, "completion", None)
    if original_completion is not None and not getattr(original_completion, _MARKER, False):

        @functools.wraps(original_completion)
        def patched_completion(*args: Any, **kwargs: Any) -> Any:
            if "tools" in kwargs and kwargs["tools"]:
                kwargs["tools"] = clean_tools(kwargs["tools"])
            return original_completion(*args, **kwargs)

        setattr(patched_completion, _MARKER, True)
        litellm_module.completion = patched_completion

    original_acompletion = getattr(litellm_module, "acompletion", None)
    if original_acompletion is not None and not getattr(original_acompletion, _MARKER, False):

        @functools.wraps(original_acompletion)
        async def patched_acompletion(*args: Any, **kwargs: Any) -> Any:
            if "tools" in kwargs and kwargs["tools"]:
                kwargs["tools"] = clean_tools(kwargs["tools"])
            return await original_acompletion(*args, **kwargs)

        setattr(patched_acompletion, _MARKER, True)
        litellm_module.acompletion = patched_acompletion

    return True


def _patch_agno_litellm() -> bool:
    """Wrap agno.models.litellm.LiteLLM to sanitize outgoing tools and repair incoming arguments."""
    try:
        from agno.models.litellm import LiteLLM

        # 1. Outgoing tool definitions
        original_params = getattr(LiteLLM, "get_request_params", None)
        if original_params is not None and not getattr(original_params, _MARKER, False):

            @functools.wraps(original_params)
            def patched_get_request_params(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
                if "tools" in kwargs and kwargs["tools"]:
                    kwargs["tools"] = clean_tools(kwargs["tools"])
                elif len(args) > 0 and args[0]:
                    args = (clean_tools(args[0]), *args[1:])

                params = original_params(self, *args, **kwargs)
                if isinstance(params, dict) and "tools" in params and params["tools"]:
                    params["tools"] = clean_tools(params["tools"])
                return params

            setattr(patched_get_request_params, _MARKER, True)
            LiteLLM.get_request_params = patched_get_request_params

        # 2. Incoming tool call arguments recovery
        original_parse = getattr(LiteLLM, "parse_tool_calls", None)
        if original_parse is not None and not getattr(original_parse, _MARKER, False):

            @staticmethod
            @functools.wraps(original_parse)
            def patched_parse_tool_calls(tool_calls_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
                result = original_parse(tool_calls_data)
                for tc in result:
                    fn = tc.get("function")
                    if isinstance(fn, dict):
                        raw_args = fn.get("arguments")
                        if isinstance(raw_args, str):
                            try:
                                parsed = json.loads(raw_args)
                                if isinstance(parsed, dict) and list(parsed.keys()) == ["text"] and isinstance(parsed["text"], str):
                                    recovered = _recover_json_object(parsed["text"])
                                    if recovered is not None:
                                        fn["arguments"] = json.dumps(recovered)
                            except Exception:
                                pass
                return result

            setattr(patched_parse_tool_calls, _MARKER, True)
            LiteLLM.parse_tool_calls = patched_parse_tool_calls

        return True
    except Exception:
        logger.debug("agno.models.litellm not available for patch; skipping")
        return False


def install(litellm_mod: Any = None) -> bool:
    """Install tool sanitization and argument recovery into LiteLLM and agno. Idempotent."""
    global _installed
    with _install_lock:
        if _installed:
            return True

        if litellm_mod is None:
            litellm_mod = sys.modules.get("litellm")
        if litellm_mod is None:
            try:
                litellm_mod = importlib.import_module("litellm")
            except Exception:
                logger.debug("litellm is not yet imported; will be patched by litellm_loader")

        if litellm_mod is not None:
            try:
                _patch_litellm_completion(litellm_mod)
            except Exception:
                logger.exception("Could not patch litellm.completion tool sanitization")
                return False

        try:
            _patch_agno_litellm()
        except Exception:
            logger.exception("Could not patch agno.models.litellm tool sanitization")

        _installed = True
        return True
