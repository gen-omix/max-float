"""The MCP server: `rivers`, `launches` and `plan` as tools, with their schemas
from the same type hints as the JSON API, and no logic of their own."""

import datetime
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from max_float import config, core

server = MCPServer(
    "max-float",
    instructions=(
        "Pick the river permit launch dates a group should apply for. `rivers` lists "
        "the rivers and the scales, `launches` gives each launch's odds and typical "
        "conditions, and `plan` gives a party's plan by the four-word key in its link, "
        "or one applicant's own plan with their name."
    ),
)


@server.tool()
def rivers() -> dict[str, Any]:
    """The rivers, each with its code, longest trip, flow category starts in cfs,
    season and launch dates; the flow and temperature categories; and where a
    new party's votes and priority start."""
    return core.rivers_view()


@server.tool()
def launches(
    river: str | None = None,
    start: datetime.date | None = None,
    end: datetime.date | None = None,
) -> list[dict[str, Any]]:
    """Every launch, or one river's by name, or those from `start` to `end`: its
    odds, expected applications, trip length, and typical flow and temperature."""
    return core.launch_rows(river, start, end)


@server.tool()
def plan(key: str, applicant: str | None = None) -> dict[str, Any]:
    """A party's plan by key: the launches to apply for and who applies for each,
    the odds of at least one permit against the most common and random launches,
    any rivers widened, and any with no launch the party is free for. With an
    applicant's name, that applicant's own plan."""
    found = core.party_plan(key, applicant)
    if found is None:
        raise ToolError("no party opens that key")
    return found


def app() -> Starlette:
    """The server as an ASGI app, to mount at /mcp. Stateless, answering in JSON,
    for the hosts in `config.SERVICE_HOSTS`."""
    return server.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=list(config.SERVICE_HOSTS)
        ),
    )
