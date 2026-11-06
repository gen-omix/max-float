# ui

The page: one screen of plain HTML, CSS and JavaScript, with no build step. The service serves it at `/` and at `/p/{key}`. Words on the page are the words in [AGENTS.md](../../../AGENTS.md). What the page reads and writes is in [graph/README.md](../graph/README.md).

## v0.2

[index.html](index.html) is a first version for one applicant, reading from Neo4j through `core.py`:

- The preferences, for all rivers and for one river.
- A dropdown of rivers above the calendar, for any number of them or all, and a calendar of every in-season month for marking unavailable dates.
- A Submit button, which is the only thing that updates the results.
- Each chosen river's full list of launches below the calendar, best first at its priority, with the launches to apply for marked. Those are each lottery's choices per application, with `config.DEFAULT_CHOICES` where no source states them.
- Those recommended launches also show on the calendar, each as its river's code in its river's color, with a key below. Hovering over a date lists its launches.

River codes appear only on the calendar and its key. A river's color stays the same whichever rivers are chosen. Ten colors can't all be told apart, especially with color blindness, so the code is what identifies a river and the color only helps. To run it:

```bash
uv run uvicorn max_float.service:app --reload
```

Rivers and launches are read once, so restart it after loading the graph. It needs Neo4j's credentials, as in [graph/README.md](../graph/README.md).

Not in v0.2: applicants, `minimum`, the Applied toggle and the party's key, as nothing is saved, and the odds of at least one permit, until it's settled how an application's choices share a place in the draw. The rest of this file is the design for the beta.

## Layout

From top to bottom:

1. **Rivers.** Pick the rivers and a trip length for each.
2. **Preferences.** Flow, temperature, minimum and priority, set once for the party.
3. **Applicants.** One row per applicant and one column per day. Drag across days to mark them off.
4. **Results.** Updated on Submit.

Opening `/` makes a party and moves to `/p/{key}`. The address is the link to share. Nothing needs saving.

## Preferences

| Preference | Control | Starts at |
|---|---|---|
| Flow | a checkbox for each of not running · extra low · low · normal · high · spicy high · extra spicy high | low, normal, high and spicy high checked |
| Temperature | a checkbox for each of cold · cool · mild · warm · hot · extra hot | cool, mild, warm and hot checked |
| Minimum | how many applicants must be free, from 1 to the whole party | the whole party |
| Priority | a slider from 0 to 10 in whole steps, with odds at the 0 end and conditions at the 10 end | 5 |

Each scale is one row of checkboxes in order, and the category names are the only labels. Any mix can be checked, and the last checked category on a scale can't be unchecked.

The checkboxes decide which launches can be in the plan: an unchecked category removes every launch that is typically in it. The slider then weighs odds against conditions among the launches left.

### For one river

Each river in the river list opens to show the same controls. Changing one there sets it for that river only, and that river keeps it when the party's changes. So a river's flow checkboxes or slider replace the party's for that river, while its other controls can still follow the party. A river's slider changes which launches that river gets, never how many. A river with any preference of its own stays open, so a difference is never hidden behind a closed river. Setting a river's controls back to the party's values closes it again.

## Results

- First, when a river was widened: a red banner across the full width of the results, one line per river, such as "Salt: no launches matched. Widened flow to include low." It can't be dismissed, and it goes away when the river no longer needs widening.
- Next: the odds of at least one permit in matching conditions, computed the same way at every priority. With no launches left it's 0%, with no rows below it.
- Then one row per application: date, river, applicant, odds, typical flow, typical temperature, and an Applied toggle. A widened river's rows are marked "widened" in red.
- An application counts against other parties only once it's toggled to Applied.

### Widened rivers

A widened river stays open, and the categories added for it show in red in its checkboxes. They aren't saved as checked: the party's own checks stay as set, and the widening is worked out again each time the plan updates. The banner also covers a river with no launches to widen to, such as "Salt: no launches when the party is free."

### Below the whole party

When the minimum is lower than the party, a switch sits above the results: the party, then each applicant by name. The party plan maximizes the odds of at least one permit. An applicant's plan maximizes the odds that that applicant gets on a trip, and the number at the top becomes theirs. With the minimum at the whole party, the switch isn't shown.

## Open questions

- Do result rows show typical flow and temperature, the frequencies (runnable, good, cold, heat), or both?
- How does the applicants-by-days grid fit a phone?
- Can an applicant who isn't the holder for any application be added just to mark days?
- Do the starting preferences suit most parties, or should they come from the first river picked?
