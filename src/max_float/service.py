"""The web service: the page and the JSON API, with no logic of their own."""

import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator

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
Slices = Annotated[int, Field(ge=0, le=config.SLICES)]


class Priority(BaseModel):
    """How many slices go to odds, to flow and to temperature."""

    odds: Slices
    flow: Slices
    temperature: Slices

    @model_validator(mode="after")
    def every_slice(self) -> "Priority":
        """Every slice goes somewhere."""
        if self.odds + self.flow + self.temperature != config.SLICES:
            raise ValueError(f"the slices must add up to {config.SLICES}")
        return self

    def slices(self) -> sg.Priority:
        """The priority as the plan takes it."""
        return sg.Priority(self.odds, self.flow, self.temperature)


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
    """The rivers with their launch dates, the categories on each scale, and where
    preferences start."""
    return {
        "rivers": [
            river | {"launches": core.dates(river["name"])} for river in core.rivers()
        ],
        "flow": config.FLOW_CATEGORIES,
        "temperature": config.TEMPERATURE_CATEGORIES,
        "preferences": {
            "flow": config.START_FLOW,
            "temperature": config.START_TEMPERATURE,
            "priority": sg.Priority(*config.START_PRIORITY)._asdict(),
        },
    }


@app.post("/api/plan")
def plan(request: PlanRequest) -> dict[str, object]:
    """The launches one applicant should apply for, and their odds against the most
    common launches and launches at random."""
    return core.plan(
        sg.Party(
            sg.Preferences(
                frozenset(request.flow),
                frozenset(request.temperature),
                request.priority.slices(),
            ),
            {
                name: sg.Considered(
                    river.days,
                    None if river.flow is None else frozenset(river.flow),
                    None if river.temperature is None else frozenset(river.temperature),
                    None if river.priority is None else river.priority.slices(),
                )
                for name, river in request.rivers.items()
            },
            1,
            {"applicant": request.away},
        )
    )
