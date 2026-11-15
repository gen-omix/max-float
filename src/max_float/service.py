"""The web service: the page and the JSON API, with no logic of their own."""

import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
)

from max_float import config, core
from max_float.graph import party
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


Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
]
Days = Annotated[int, Field(ge=1, le=30)] | None


class Own(BaseModel):
    """An applicant's preferences for one river, where they differ from their own."""

    flow: FlowVotes | None = None
    temperature: TemperatureVotes | None = None
    priority: Priority | None = None

    def stored(self) -> party.Own:
        return party.Own(
            self.flow,
            self.temperature,
            None if self.priority is None else list(self.priority.slices()),
        )


class ApplicantBody(BaseModel):
    """One applicant's settings: their votes, priority, any preferences for one
    river, and their days away."""

    flow: FlowVotes
    temperature: TemperatureVotes
    priority: Priority
    rivers: dict[str, Own] = {}
    away: list[datetime.date] = []

    def stored(self) -> party.Applicant:
        return party.Applicant(
            self.flow,
            self.temperature,
            list(self.priority.slices()),
            {river: own.stored() for river, own in self.rivers.items()},
            self.away,
        )


class PartyBody(BaseModel):
    """The team's settings: how many must be free, and the rivers it's
    considering with a trip length for each, None for the river's longest."""

    minimum: Annotated[int, Field(ge=1)] | None = None
    rivers: dict[str, Days]


class NewParty(PartyBody):
    """What makes a party: its settings, and its first applicant by name."""

    name: Name
    applicant: ApplicantBody


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


def valid_key(key: str) -> str:
    """A path that has the shape of a key. Anything else is not found."""
    if not party.is_key(key):
        raise HTTPException(404)
    return key


Key = Annotated[str, Depends(valid_key)]


def client_ip(request: Request) -> str:
    """The address a request came from, through a proxy if there is one."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "")


def existing(ok: bool) -> dict[str, object]:
    """Nothing, for a write that found its party; not found otherwise."""
    if not ok:
        raise HTTPException(404)
    return {}


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
                sg.votes(request.flow),
                sg.votes(request.temperature),
                request.priority.slices(),
            ),
            {
                name: sg.Considered(
                    river.days,
                    sg.votes(river.flow),
                    sg.votes(river.temperature),
                    None if river.priority is None else river.priority.slices(),
                )
                for name, river in request.rivers.items()
            },
            1,
            {"applicant": request.away},
        )
    )


@app.post("/api/party", status_code=201)
def create(body: NewParty, request: Request) -> dict[str, str]:
    """A new party with its first applicant. Returns its key."""
    try:
        key = core.create_party(
            client_ip(request),
            body.minimum,
            body.rivers,
            body.name,
            body.applicant.stored(),
        )
    except party.TooManyParties:
        raise HTTPException(429) from None
    return {"key": key}


@app.get("/api/party/{key}")
def read_party(key: Key) -> dict[str, object]:
    """The party a key opens."""
    found = core.party_view(key)
    if found is None:
        raise HTTPException(404)
    return found


@app.put("/api/party/{key}")
def save_party(key: Key, body: PartyBody) -> dict[str, object]:
    """Save the team's settings."""
    return existing(core.save_party(key, body.minimum, body.rivers))


@app.put("/api/party/{key}/applicants/{name}")
def save_applicant(key: Key, name: Name, body: ApplicantBody) -> dict[str, object]:
    """Save one applicant's settings, adding them if new."""
    return existing(core.save_applicant(key, name, body.stored()))


@app.delete("/api/party/{key}/applicants/{name}")
def remove_applicant(key: Key, name: Name) -> dict[str, object]:
    """Remove an applicant. A team whose dates are locked in is a conflict."""
    try:
        return existing(core.remove_applicant(key, name))
    except core.Locked:
        raise HTTPException(409) from None


@app.post("/api/party/{key}/plan")
def plan_party(key: Key, applicant: str | None = None) -> dict[str, object]:
    """The team's plan, or only the launches one applicant applies for in it."""
    try:
        found = core.party_plan(key, applicant)
    except KeyError:
        raise HTTPException(404) from None
    if found is None:
        raise HTTPException(404)
    return found


@app.post("/api/party/{key}/lock")
def lock(key: Key) -> dict[str, object]:
    """Lock in the team's dates. Returns when. A plan with no launches is a
    conflict."""
    try:
        when = core.lock(key)
    except core.NothingToLock:
        raise HTTPException(409) from None
    if when is None:
        raise HTTPException(404)
    return {"locked": when}


@app.post("/api/party/{key}/unlock")
def unlock(key: Key) -> dict[str, object]:
    """Unlock the team's dates."""
    return existing(core.unlock(key))


@app.get("/{key}", response_class=HTMLResponse)
def page_for(key: Key) -> str:
    """The page, for a party's link."""
    return PAGE.read_text()
