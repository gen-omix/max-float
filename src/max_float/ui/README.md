# ui

The page: one screen of plain HTML, CSS and JavaScript, with no build step. The service serves it at `/` and at `/p/{key}`. Words on the page are the words in [AGENTS.md](../../../AGENTS.md). What the page reads and writes is in [graph/README.md](../graph/README.md).

## v0.4

[index.html](index.html) is a first version for one applicant, reading from Neo4j through `core.py`:

- The preferences, for all rivers and for one river. Flow and temperature are each a dot plot of votes, a row of ten dots for each category: click a dot to give its category that many votes, click its last dot to take one back, or use the arrow keys on a row. The count of votes left is beside the scale's name. Each category's range is beside its name: temperature in °F everywhere, and flow in cfs only in a river's own votes, as each river's gauge has its own ranges, from `flow_starts`. Flows from 1,000 cfs are in thousands, such as 1.5k–5k. The priority is a pie of twelve slices: pick odds, flow or temperature, then click or drag across slices, or press Enter on them, to give them to it. The slices regroup when a drag ends or focus leaves the pie.
- A dropdown of rivers above the calendar, for any number of them or all, and a calendar of every in-season month for marking unavailable dates. Days with no launch on a chosen river are shaded off, such as the Selway's outfitter days.
- A Submit button, which is the only thing that updates the results.
- The recommended launches: each lottery's choices per application, with `config.DEFAULT_CHOICES` where no source states them. They show on the calendar, each as its river's code in its river's color, with a key below, and in a list for each river, closed until opened. Download CSV saves them with the API's column names.
- A chart of the odds of at least one permit with the recommended launches and with random ones, each as a multiple of the odds with the most common ones, for all rivers and then for each. Hovering over a row gives all three odds.

River codes appear only on the calendar and its key. A river's color stays the same whichever rivers are chosen. Ten colors can't all be told apart, especially with color blindness, so the code is what identifies a river and the color only helps. To run it:

```bash
uv run uvicorn max_float.service:app --reload
```

Rivers and launches are read once, so restart it after loading the graph. It needs Neo4j's credentials, as in [graph/README.md](../graph/README.md).

Not in v0.4: applicants, `minimum`, the Applied toggle and the party's key, as nothing is saved. The rest of this file is the design for the beta.

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
| Flow | ten votes among not running · extra low · low · normal · high · spicy high · extra spicy high | low 2, normal 3, high 3, spicy high 2 |
| Temperature | ten votes among cold · cool · mild · warm · hot · extra hot | cool 2, mild 3, warm 3, hot 2 |
| Minimum | how many applicants must be free, from 1 to the whole party | the whole party |
| Priority | a pie of twelve slices, each given to odds, flow or temperature | 4 each |

Each scale is a row of dots for each category in order, and the category names are the only labels. Votes can go to any mix of categories, up to ten, and the last vote on a scale can't be taken back.

The votes decide which launches can be in the plan: a category with no votes removes every launch that is typically in it. Among the launches left, more votes for a launch's categories in past years make a better match, and the pie then weighs odds, flow and temperature.

### For one river

Each river in the river list opens to show the same controls. Changing one there sets it for that river only, and that river keeps it when the party's changes. So a river's flow votes or pie replace the party's for that river, while its other controls can still follow the party. A river's pie changes which launches that river gets, never how many. A river with any preference of its own stays open, so a difference is never hidden behind a closed river. Setting a river's controls back to the party's values closes it again.

## Results

- First, when a river was widened: a red banner across the full width of the results, one line per river, such as "Salt: no launches matched. Widened flow to include low." It can't be dismissed, and it goes away when the river no longer needs widening.
- Next: the odds of at least one permit, against the most common launches and random ones, as in v0.3.
- Then one row per application: date, river, applicant, odds, typical flow, typical temperature, and an Applied toggle. A widened river's rows are marked "widened" in red.
- An application counts against other parties only once it's toggled to Applied.

### Widened rivers

A widened river stays open, and the categories added for it show in red in its votes, and each counts as one vote. They aren't saved as votes: the party's own votes stay as set, and the widening is worked out again each time the plan updates. The banner also covers a river with no launches to widen to, such as "Salt: no launches when the party is free."

### Below the whole party

When the minimum is lower than the party, a switch sits above the results: the party, then each applicant by name. The party plan maximizes the odds of at least one permit. An applicant's plan maximizes the odds that that applicant gets on a trip, and the number at the top becomes theirs. With the minimum at the whole party, the switch isn't shown.

## Open questions

- Do result rows show typical flow and temperature, the frequencies (runnable, good, cold, heat), or both?
- How does the applicants-by-days grid fit a phone?
- Can an applicant who isn't the holder for any application be added just to mark days?
- Do the starting preferences suit most parties, or should they come from the first river picked?
