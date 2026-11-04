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

- **river**: a stretch with its own permit lottery, e.g. the Middle Fork Salmon.
- **launch**: a river on a date.
- **applicant**: a person who can apply. A **party** is the applicants planning together.
- **preferences**: flow, and whether to avoid cold, heat or bugs.
- **odds**: the probability of winning, from 0 to 1. Shown as a percentage, or — with no lottery history.
- **plan**: which applicant applies for which launch.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Tests run offline.
