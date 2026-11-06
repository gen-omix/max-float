"""The web service: the page and the JSON API, with no logic of their own."""

import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from max_float import config, core
from max_float.graph import subgraph as sg

PAGE = Path(__file__).parent / "ui" / "index.html"

FlowSteps = Annotated[
    set[Annotated[int, Field(ge=0, lt=len(config.FLOW_CATEGORIES))]],
    Field(min_length=1),
]
TemperatureSteps = Annotated[
    set[Annotated[int, Field(ge=0, lt=len(config.TEMPERATURE_CATEGORIES))]],
    Field(min_length=1),
]
Priority = Annotated[int, Field(ge=0, le=10)]


class River(BaseModel):
    """A river to consider, with any preferences of its own."""

    days: Annotated[int, Field(ge=1, le=30)] | None = None
    flow: FlowSteps | None = None
    temperature: TemperatureSteps | None = None
    priority: Priority | None = None


class PlanRequest(BaseModel):
    """What the page sends for a plan: one applicant's preferences and days away."""

    flow: FlowSteps
    temperature: TemperatureSteps
    priority: Priority
    rivers: dict[str, River]
    away: list[datetime.date] = []


app = FastAPI(title="max-float")


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    """The page."""
    return PAGE.read_text()


@app.get("/api/rivers")
def rivers() -> dict[str, object]:
    """The rivers, the categories on each scale, and where preferences start."""
    return {
        "rivers": core.rivers(),
        "flow": config.FLOW_CATEGORIES,
        "temperature": config.TEMPERATURE_CATEGORIES,
        "preferences": {
            "flow": config.START_FLOW,
            "temperature": config.START_TEMPERATURE,
            "priority": config.START_PRIORITY,
        },
    }


@app.post("/api/plan")
def plan(request: PlanRequest) -> dict[str, object]:
    """Every launch left for one applicant, with each river's best first."""
    return core.plan(
        sg.Party(
            sg.Preferences(
                frozenset(request.flow),
                frozenset(request.temperature),
                request.priority,
            ),
            {
                name: sg.Considered(
                    river.days,
                    None if river.flow is None else frozenset(river.flow),
                    None if river.temperature is None else frozenset(river.temperature),
                    river.priority,
                )
                for name, river in request.rivers.items()
            },
            1,
            {"applicant": request.away},
        )
    )
