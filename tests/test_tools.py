import asyncio
import datetime
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from max_float import core, service, tools

D = datetime.date(2027, 6, 1)


def run(coroutine):
    return asyncio.run(coroutine)


def test_the_three_tools_take_what_the_api_takes():
    found = {tool.name: tool for tool in run(tools.server.list_tools())}
    assert set(found) == {"rivers", "launches", "plan"}
    assert found["rivers"].input_schema["properties"] == {}
    assert set(found["launches"].input_schema["properties"]) == {
        "river",
        "start",
        "end",
    }
    assert found["launches"].input_schema.get("required", []) == []
    assert found["plan"].input_schema["required"] == ["key"]
    assert "applicant" in found["plan"].input_schema["properties"]
    assert "odds" in found["launches"].description


def test_rivers_and_launches_tools_give_what_core_gives(monkeypatch):
    monkeypatch.setattr(core, "rivers_view", lambda: {"rivers": [{"name": "Salt"}]})
    monkeypatch.setattr(
        core,
        "launch_rows",
        lambda river, start, end: [{"river": river, "date": start, "odds": 0.1}],
    )
    rivers = run(tools.server.call_tool("rivers", {}))
    assert not rivers.is_error
    assert json.loads(rivers.content[0].text)["rivers"] == [{"name": "Salt"}]
    launches = run(
        tools.server.call_tool("launches", {"river": "Salt", "start": "2027-06-01"})
    )
    assert [json.loads(item.text) for item in launches.content] == [
        {"river": "Salt", "date": "2027-06-01", "odds": 0.1}
    ]


def test_plan_tool_passes_the_key_and_applicant_and_errs_on_an_unknown_key(
    monkeypatch,
):
    calls = []

    def party_plan(key, applicant=None):
        calls.append((key, applicant))
        return {"launches": []} if key == "a-good-key-here" else None

    monkeypatch.setattr(core, "party_plan", party_plan)
    found = run(
        tools.server.call_tool("plan", {"key": "a-good-key-here", "applicant": "Gen"})
    )
    assert not found.is_error
    assert json.loads(found.content[0].text) == {"launches": []}
    assert calls == [("a-good-key-here", "Gen")]
    with pytest.raises(ToolError, match="no party"):
        run(tools.server.call_tool("plan", {"key": "some-other-key-words"}))


def test_the_server_answers_at_mcp_for_the_service_hosts():
    found = [
        route for route in service.app.routes if getattr(route, "path", "") == "/mcp"
    ]
    assert len(found) == 1
    assert found[0].endpoint.inner is service.MCP
    assert {"GET", "POST", "DELETE"} <= set(found[0].methods)
    assert "maxfloat.gen-omix.com" in tools.config.SERVICE_HOSTS
