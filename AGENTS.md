# max-float

Pick the river permit launch dates your group should apply for.

## Principles

- **Better for everyone at once.** Every change makes max-float better to use, to build on, and for agents to call. If it helps one at another's cost, find a different change.
- **One purpose.** If it doesn't help a group choose launch dates, it doesn't ship.
- **One core.** `rivers`, `launches` and `plan` do all the work. The page, the JSON API and the MCP server are thin adapters with no logic of their own.
- **One vocabulary.** The words below mean the same thing in the page, the code, the API, the MCP tools and the graph.
- **No helper text.** No taglines, hints or secondary labels. If a screen needs them, change the layout.
- **No placeholders.** No file, flag, dependency or abstraction before it has a job.
- **Nothing breaks.** Every commit passes the checks below.

## Vocabulary

- **river**: a stretch, e.g. the Middle Fork Salmon. Its **code** is three letters, e.g. MFS, shown on the calendar and its key. Everywhere else on the page, a river goes by its full name.
- **lottery**: one draw with its own rules, for one or more rivers. Gates of Lodore and the Yampa share one.
- **launch**: a river on a date.
- **applicant**: a person who can apply. A **party** is the applicants planning together.
- **key**: the four words that open a party's plan, e.g. `otter-canyon-cobble-ferry`.
- **minimum**: how many applicants must be free for a launch.
- **preferences**: the flow categories and temperature categories that are checked, and the priority. Set for the party, or for one river.
- **priority**: how twelve slices split between odds, flow and temperature, which weighs them among the launches left after the checks.
- **widened**: a river whose checked categories left no launches, so its plan uses the nearest categories instead, with a warning.
- **odds**: the probability of winning, from 0 to 1. Shown as a percentage, or — with no lottery history.
- **plan**: which applicant applies for which launch. Its launches are the **recommended** ones.
- **most common**: a river's launches with the most applications, as many as it has recommended. **Random** is as many at random.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Tests run offline.
