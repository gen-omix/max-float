"""The web service: the page and the JSON API, with no logic of their own."""

import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import AfterValidator, BaseModel, Field, model_validator

from max_float import config, core
from max_float.graph import subgraph as sg

PAGE = Path(__file__).parent / "ui" / "index.html"


def spent(counts: list[int]) -> list[int]:
    """Votes with at least one given and no more than a scale has."""
    if not 1 <= sum(counts) <= config.VOTES:
        raise ValueError(f"a scale gives from 1 to {config.VOTES} votes")
    return counts


def scale(categories: int) -> object:
    """The votes for each category on a scale with this many, in step order."""
    return Annotated[
        list[Annotated[int, Field(ge=0, le=config.VOTES)]],
        Field(min_length=categories, max_length=categories),
        AfterValidator(spent),
    ]


FlowVotes = scale(len(config.FLOW_CATEGORIES))
TemperatureVotes = scale(len(config.TEMPERATURE_CATEGORIES))
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
    flow: FlowVotes | None = None
    temperature: TemperatureVotes | None = None
    priority: Priority | None = None


class PlanRequest(BaseModel):
    """What the page sends for a plan: one applicant's preferences and days away."""

    flow: FlowVotes
    temperature: TemperatureVotes
    priority: Priority
    rivers: dict[str, River]
    away: list[datetime.date] = []


app = FastAPI(title="max-float")


def votes(counts: list[int] | None) -> sg.Votes | None:
    """Votes by step, for the categories with any."""
    if counts is None:
        return None
    return {step: count for step, count in enumerate(counts) if count}


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    """The page."""
    return PAGE.read_text()


@app.get("/api/rivers")
def rivers() -> dict[str, object]:
    """The rivers with their launch dates, the categories on each scale, where each
    temperature category after "cold" starts in °F, the votes each scale has, and
    where preferences start."""
    return {
        "rivers": [
            river | {"launches": core.dates(river["name"])} for river in core.rivers()
        ],
        "flow": config.FLOW_CATEGORIES,
        "temperature": config.TEMPERATURE_CATEGORIES,
        "temperature_starts": config.TEMPERATURE_STARTS,
        "votes": config.VOTES,
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
                votes(request.flow),
                votes(request.temperature),
                request.priority.slices(),
            ),
            {
                name: sg.Considered(
                    river.days,
                    votes(river.flow),
                    votes(river.temperature),
                    None if river.priority is None else river.priority.slices(),
                )
                for name, river in request.rivers.items()
            },
            1,
            {"applicant": request.away},
        )
    )
