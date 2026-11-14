# ui

The page: one screen of plain HTML, CSS and JavaScript, with no build step. The service serves it at `/` and at `/{key}`. Words on the page are the words in [AGENTS.md](../../../AGENTS.md). What the page reads and writes is in [graph/README.md](../graph/README.md).

## v0.6

[index.html](index.html) plans for a group, reading and writing the graph through `core.py`:

- Tabs across the top: **Group**, one for each applicant by name, and **+**, where typing a name adds you. Everything a tab sets sits on one sheet joined to that tab, in that tab's color: gray for the Group, and a color for each applicant in the order they joined. The first name on `/` makes the group and moves to `/{key}`, with a notice giving the link to share and a Copy link button. The Group tab opens first and shows everyone's unavailable dates, with how many of the group are away each day, such as 2/3, and dark when everyone is, the applicants' votes and priority averaged, which can fill part of a dot and split the pie into three parts, the rivers, trip lengths and `minimum`, and the group's plan with who applies for each launch. An applicant's tab sets their own votes, priority and days, and gives their own plan. Each tab saves itself two seconds after an edit and when the page closes. Submit on the Group tab reads the group again first, so it sees what others saved.
- A bar at the top of every tab says whether the group is **Planning**, with an open padlock, or **Locked in**, with a closed padlock, the time, and green. **Lock in dates for group** is on the Group tab while planning. It saves the plan as the group's applications and locks them, and from then on nothing can be changed on any tab, and no one can be added, until someone presses **Unlock**, which is on every tab while locked.
- **Submit** floats at the lower right of every tab, and glows while the results don't show the latest edits.

- The preferences, for all rivers and for one river. Flow and temperature are each a dot plot of votes, a row of ten dots for each category: click a dot to give its category that many votes, click its last dot to take one back, or use the arrow keys on a row. The count of votes left is beside the scale's name. Each category's range is beside its name: temperature in °F everywhere, and flow in cfs only in a river's own votes, as each river's gauge has its own ranges, from `flow_starts`. Flows from 1,000 cfs are in thousands, such as 1.5k–5k. The priority is a pie of twelve slices: pick odds, flow or temperature, then click or drag across slices, or press Enter on them, to give them to it. The slices regroup when a drag ends or focus leaves the pie.
- A dropdown of rivers above the calendar, for any number of them or all, and a calendar of every in-season month for marking unavailable dates. Days with no launch on a chosen river are shaded off, such as the Selway's outfitter days.
- A Submit button, which is the only thing that updates the results.
- The recommended launches: each lottery's choices per application, with `config.DEFAULT_CHOICES` where no source states them. They show on the calendar, each as its river's code in its river's color, with a key below, and in a list for each river, closed until opened. Download CSV saves them with the API's column names.
- A chart of the odds of at least one permit with the recommended launches and with random ones, each as a multiple of the odds with the most common ones, for all rivers and then for each. Hovering over a row gives all three odds.

River codes appear only on the calendar and its key. A river's color stays the same whichever rivers are chosen. Ten colors can't all be told apart, especially with color blindness, so the code is what identifies a river and the color only helps. To run it:

```bash
uv run uvicorn max_float.service:app --reload
```

Rivers and launches are read once, so restart it after loading the graph. It needs Neo4j's credentials and `MAX_FLOAT_SECRET`, as in [graph/README.md](../graph/README.md).

Not in v0.6: removing an applicant, and the MCP tools. The rest of this file is the design for the beta.

## Layout

Tabs across the top: **Group**, one tab for each applicant with their name, and **+**, where typing a name adds an applicant. The Group tab is the one that opens.

An applicant's tab has their votes and priority, for all rivers and for one river, their unavailable dates, and Submit, which gives their own best dates: their preferences, their days, and one application in each lottery, as if they were applying alone.

The Group tab has the rivers and a trip length for each, `minimum`, everyone's unavailable dates on one calendar with how many are away each day, the applicants' votes and priority averaged, shown but not set there, and Submit, which gives the group's plan: each applicant's application in each lottery. Under the results, **Lock in dates for group**.

Typing the first name on `/` makes the party and moves to `/{key}`. The address is the link to share. Each tab saves itself a few seconds after an edit and when it's closed, and the group's latest plan is saved with it.

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
- Then one row per application: date, river, applicant, odds, typical flow and typical temperature. A widened river's rows are marked "widened" in red.
- **Lock in dates for group** saves the plan as the group's applications and locks them: the button then shows when, and reads **Unlock**. Edits after that still save, but the locked dates stay until the group unlocks them. Applications count against other parties only once they're locked in.

### Widened rivers

A widened river stays open, and the categories added for it show in red in its votes, and each counts as one vote. They aren't saved as votes: the party's own votes stay as set, and the widening is worked out again each time the plan updates. The banner also covers a river with no launches to widen to, such as "Salt: no launches when the party is free."

### Below the whole party

When the minimum is lower than the party, the group's plan can use a launch some applicants can't make, and the applicant it names for that launch is one who can. With the minimum at the whole party, every launch in the plan is one everyone is free for.

## Open questions

- Do result rows show typical flow and temperature, the frequencies (runnable, good, cold, heat), or both?
- How does the applicants-by-days grid fit a phone?
- Can an applicant who isn't the holder for any application be added just to mark days?
- Do the starting preferences suit most parties, or should they come from the first river picked?
