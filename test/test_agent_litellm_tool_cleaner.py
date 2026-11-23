"""Tests for LiteLLM tool sanitization (services/agent/litellm_tool_cleaner.py)."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from services.agent import litellm_tool_cleaner


def test_clean_tool_dict_strips_internal_fields():
    dirty_tool = {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Place an order",
            "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}},
            "strict": True,
            "requires_confirmation": True,
            "external_execution": False,
            "approval_type": "standard",
        },
    }
    dirty_copy = copy.deepcopy(dirty_tool)
    cleaned = litellm_tool_cleaner.clean_tool_dict(dirty_tool)

    # Input dictionary must not be mutated
    assert dirty_tool == dirty_copy

    # Output dictionary must only have valid OpenAI fields
    assert cleaned["type"] == "function"
    assert cleaned["function"]["name"] == "place_order"
    assert cleaned["function"]["description"] == "Place an order"
    assert cleaned["function"]["parameters"] == {"type": "object", "properties": {"symbol": {"type": "string"}}}
    assert cleaned["function"]["strict"] is True

    # Internal fields must be removed
    assert "requires_confirmation" not in cleaned["function"]
    assert "external_execution" not in cleaned["function"]
    assert "approval_type" not in cleaned["function"]


def test_clean_tools_leaves_clean_tools_unchanged():
    clean_tool = {
        "type": "function",
        "function": {
            "name": "get_quote",
            "description": "Get market quote",
            "parameters": {"type": "object"},
        },
    }
    tools = [clean_tool]
    result = litellm_tool_cleaner.clean_tools(tools)
    assert result == tools


def test_clean_tools_handles_non_dict_elements():
    assert litellm_tool_cleaner.clean_tools(None) is None
    assert litellm_tool_cleaner.clean_tools("not a list") == "not a list"
    assert litellm_tool_cleaner.clean_tools([123, "abc"]) == [123, "abc"]


def test_patch_litellm_completion_cleans_tools():
    class DummyLiteLLM:
        def __init__(self):
            self.last_kwargs = None

        def completion(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.last_kwargs = kwargs
            return {"status": "ok"}

        async def acompletion(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.last_kwargs = kwargs
            return {"status": "ok"}

    dummy = DummyLiteLLM()
    litellm_tool_cleaner._patch_litellm_completion(dummy)

    dirty_tools = [
        {
            "type": "function",
            "function": {
                "name": "cancel_order",
                "parameters": {},
                "requires_confirmation": True,
            },
        }
    ]

    dummy.completion(model="test", tools=dirty_tools)
    assert dummy.last_kwargs is not None
    assert "tools" in dummy.last_kwargs
    assert "requires_confirmation" not in dummy.last_kwargs["tools"][0]["function"]


def test_patched_parse_tool_calls_recovers_concatenated_json():
    import json
    from agno.models.litellm import LiteLLM

    litellm_tool_cleaner._patch_agno_litellm()

    concatenated_args = (
        '{"last_n":15,"interval":"D","symbol":"RELIANCE","indicators":["ema"],"exchange":"NSE"}'
        '{"interval":"D","symbol":"RELIANCE","indicators":["ema:20","ema:50"],"exchange":"NSE"}'
    )
    raw_tc = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "plot_price_chart", "arguments": concatenated_args},
        }
    ]

    parsed = LiteLLM.parse_tool_calls(raw_tc)
    assert len(parsed) == 1
    args_str = parsed[0]["function"]["arguments"]
    args_dict = json.loads(args_str)
    assert "text" not in args_dict
    assert args_dict["symbol"] == "RELIANCE"
    assert args_dict["exchange"] == "NSE"

