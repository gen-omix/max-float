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
)

from max_float import config, core
from max_float.graph import party
from max_float.graph import subgraph as sg

PAGE = Path(__file__).parent / "ui" / "index.html"


Rating = Annotated[int, Field(ge=0, le=len(config.RATINGS) - 1)]


def above_no(ratings: list[int]) -> list[int]:
    """A rated scale has at least one category above No."""
    if not any(ratings):
        raise ValueError("rate at least one category above No")
    return ratings


def ratings(categories: int, blanks: bool) -> object:
    """A rating for each category on a scale with this many, in step order: rows
    not rated yet are None where `blanks` allows, and otherwise at least one is
    above No."""
    if blanks:
        return Annotated[
            list[Rating | None], Field(min_length=categories, max_length=categories)
        ]
    return Annotated[
        list[Rating],
        Field(min_length=categories, max_length=categories),
        AfterValidator(above_no),
    ]


FlowRatings = ratings(len(config.FLOW_CATEGORIES), blanks=True)
TemperatureRatings = ratings(len(config.TEMPERATURE_CATEGORIES), blanks=True)
RatedFlow = ratings(len(config.FLOW_CATEGORIES), blanks=False)
RatedTemperature = ratings(len(config.TEMPERATURE_CATEGORIES), blanks=False)


class Priority(BaseModel):
    """How much odds, flow and temperature each matter: a rating each, None for one
    not rated yet."""

    odds: Rating | None = None
    flow: Rating | None = None
    temperature: Rating | None = None

    def ratings(self) -> list[int | None]:
        """The ratings for odds, flow and temperature, in that order."""
        return [self.odds, self.flow, self.temperature]


class RatedPriority(Priority):
    """A priority with every part rated."""

    odds: Rating
    flow: Rating
    temperature: Rating


def addressable(name: str) -> str:
    """A name ends its tab's address, so it can't hold a slash or be only dots."""
    if "/" in name or set(name) == {"."}:
        raise ValueError("a name can't include a slash or be only dots")
    return name


Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=40),
    AfterValidator(addressable),
]
Days = Annotated[int, Field(ge=1, le=30)] | None


def distinct(slots: list[int]) -> list[int]:
    """No choice is given to a river twice."""
    if len(set(slots)) != len(slots):
        raise ValueError("a choice can't be given twice")
    return sorted(slots)


Slots = Annotated[list[Annotated[int, Field(ge=0, lt=10)]], AfterValidator(distinct)]


class Own(BaseModel):
    """An applicant's ratings for one river, where they differ from their own,
    and which of a shared lottery's choices are for it."""

    flow: RatedFlow | None = None
    temperature: RatedTemperature | None = None
    priority: RatedPriority | None = None
    slots: Slots | None = None

    def stored(self) -> party.Own:
        return party.Own(
            self.flow,
            self.temperature,
            None if self.priority is None else self.priority.ratings(),
            self.slots,
        )


class ApplicantBody(BaseModel):
    """One applicant's settings: their ratings, None for rows not rated yet, any
    ratings for one river, and their days away."""

    flow: FlowRatings
    temperature: TemperatureRatings
    priority: Priority
    rivers: dict[str, Own] = {}
    away: list[datetime.date] = []

    def stored(self) -> party.Applicant:
        return party.Applicant(
            self.flow,
            self.temperature,
            self.priority.ratings(),
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
    """A river to consider, with any ratings of its own."""

    days: Annotated[int, Field(ge=1, le=30)] | None = None
    flow: RatedFlow | None = None
    temperature: RatedTemperature | None = None
    priority: RatedPriority | None = None


class PlanRequest(BaseModel):
    """A plan for one applicant without a team: their ratings and days away."""

    flow: RatedFlow
    temperature: RatedTemperature
    priority: RatedPriority
    rivers: dict[str, River]
    away: list[datetime.date] = []


UNRATED = "Rate every row of the preferences first."
UNSPLIT = "Choose which river each of the shared application's choices is for."

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
    """The rivers with their launch dates and the typical flow category on each,
    the categories on each scale, where each temperature category after "cold"
    starts in °F, and the ratings a category or a part of the priority can have."""
    return {
        "rivers": [
            river
            | {
                "launches": core.dates(river["name"]),
                "flow_typical": core.typical_flows(river["name"]),
            }
            for river in core.rivers()
        ],
        "flow": config.FLOW_CATEGORIES,
        "temperature": config.TEMPERATURE_CATEGORIES,
        "temperature_starts": config.TEMPERATURE_STARTS,
        "ratings": config.RATINGS,
        "priority_ratings": config.PRIORITY_RATINGS,
    }


@app.post("/api/plan")
def plan(request: PlanRequest) -> dict[str, object]:
    """The launches one applicant should apply for, and their odds against the most
    common launches and launches at random."""
    return core.plan(
        sg.Party(
            sg.Preferences(
                sg.scale(request.flow),
                sg.scale(request.temperature),
                sg.priority(request.priority.ratings()),
            ),
            {
                name: sg.Considered(
                    river.days,
                    None if river.flow is None else sg.scale(river.flow),
                    None if river.temperature is None else sg.scale(river.temperature),
                    None
                    if river.priority is None
                    else sg.priority(river.priority.ratings()),
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


@app.post("/api/party/{key}/applicants/{name}/done")
def mark_done(key: Key, name: Name) -> dict[str, object]:
    """Mark an applicant done, until they next change anything. One who has chosen
    no rivers, or a team whose dates are locked in, is a conflict."""
    try:
        when = core.mark_done(key, name)
    except KeyError:
        raise HTTPException(404) from None
    except core.NoRivers:
        raise HTTPException(409, "Select at least one river to apply for.") from None
    except core.NotRated:
        raise HTTPException(409, UNRATED) from None
    except core.NotSplit:
        raise HTTPException(409, UNSPLIT) from None
    except core.Locked:
        raise HTTPException(409, "The team's dates are locked in.") from None
    if when is None:
        raise HTTPException(404)
    return {"done": when}


@app.post("/api/party/{key}/plan")
def plan_party(key: Key, applicant: str | None = None) -> dict[str, object]:
    """The team's plan, or only the launches one applicant applies for in it. An
    applicant who hasn't rated every row, or a team where no one has, is a
    conflict."""
    try:
        found = core.party_plan(key, applicant)
    except KeyError:
        raise HTTPException(404) from None
    except core.NotRated:
        raise HTTPException(409, UNRATED) from None
    if found is None:
        raise HTTPException(404)
    return found


@app.post("/api/party/{key}/lock")
def lock(key: Key) -> dict[str, object]:
    """Lock in the team's dates. Returns when. Anyone not done, or a plan with no
    launches, is a conflict."""
    try:
        when = core.lock(key)
    except core.NotDone as waiting:
        names = ", ".join(waiting.args[0])
        raise HTTPException(409, f"Not done yet: {names}.") from None
    except core.NothingToLock:
        raise HTTPException(409, "There are no launches to lock in.") from None
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
