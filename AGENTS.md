# max-float

Pick the river permit launch dates your team should apply for.

## Principles

- **Better for everyone at once.** Every change makes max-float better to use, to build on, and for agents to call. If it helps one at another's cost, find a different change.
- **One purpose.** If it doesn't help a team choose launch dates, it doesn't ship.
- **One core.** `rivers`, `launches` and `plan` do all the work. The page, the JSON API and the MCP server are thin adapters with no logic of their own.
- **One vocabulary.** The words below mean the same thing in the page, the code, the API, the MCP tools and the graph.
- **No helper text.** No taglines, hints or secondary labels. If a screen needs them, change the layout.
- **No placeholders.** No file, flag, dependency or abstraction before it has a job.
- **Nothing breaks.** Every commit passes the checks below.

## Vocabulary

- **river**: a stretch, e.g. the Middle Fork Salmon. Its **code** is three letters, e.g. MFS, shown on the calendar and its key. Everywhere else on the page, a river goes by its full name.
- **lottery**: one draw with its own rules, for one or more rivers. Gates of Lodore and the Yampa share one, so they share an application: an applicant who chooses both says which river each of its choices is for.
- **launch**: a river on a date.
- **applicant**: a person who can apply, for the rivers they choose. A **team** is the applicants planning together, and its rivers are the ones any of them chose. The code, the API and the graph call a team a **party**.
- **team name**: the three words that open a team's plan, an adjective, a color and an animal, e.g. `salty-orange-otters`, and end its address. A team made before has four, e.g. `otter-canyon-cobble-ferry`. The code, the API and the graph still call it the **key**.
- **done**: an applicant who has pressed Done on their tab since they last changed anything.
- **minimum**: how many of a river's applicants must be free for a launch. One unless set higher, so an applicant who isn't free for a launch the others apply for gets the best ones they are free for.
- **preferences**: the ratings for flow, for temperature and for the priority. Set for the party, or for one river.
- **ratings**: for each flow and temperature category, No, OK, Good or Ideal, and for odds, flow and temperature, how much each matters: Not, Some, More or Most. A row's **share** is its rating over its set's total. No leaves out every launch typically in that category. Every row starts blank.
- **rated**: an applicant who has rated every row, with at least one flow and one temperature category above No. Only then does their tab show a draft, can they be done, and do their preferences count in the team's.
- **priority**: the ratings of odds, flow and temperature, which weigh them among the launches left after the checks.
- **widened**: a river whose rated categories left no launches, so its plan uses the nearest categories instead, with a warning.
- **odds**: the probability of winning, from 0 to 1. Shown as a percentage, or — with no lottery history. Other parties' locked-in applications for a launch count in its odds, and a party's own share them.
- **locked in**: a team's plan once everyone is done and it says these are its applications. Only then do they count in other teams' odds, and only then does the page list the plan's launches.
- **noise**: a small change to what each launch is worth in a party's plan, fixed by the party's **seed**, so that parties don't all get the same best launches. Preferences like the typical ones get the most, and the further they are from them, the less.
- **plan**: which applicant applies for which launch. A party applies for the same launches together, unless an applicant isn't free for one. Its launches are the **recommended** ones.
- **most common**: a river's launches with the most applications, as many as it has recommended. **Random** is as many at random.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Tests run offline.
