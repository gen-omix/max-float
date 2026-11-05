# ui

The page: one screen of plain HTML, CSS and JavaScript, with no build step. The service serves it at `/` and at `/p/{key}`. Words on the page are the words in [AGENTS.md](../../../AGENTS.md). What the page reads and writes is in [graph/README.md](../graph/README.md).

## Layout

From top to bottom:

1. **Rivers.** Pick the rivers and a trip length for each.
2. **Preferences.** Flow, temperature, bugs and minimum, set once for the party.
3. **Applicants.** One row per applicant and one column per day. Drag across days to mark them off.
4. **Results.** Updated as you edit.

Opening `/` makes a party and moves to `/p/{key}`. The address is the link to share. Nothing needs saving.

## Preferences

| Preference | Control | Starts at |
|---|---|---|
| Flow | a range on not running · extra low · low · normal · high · spicy high · extra spicy high | low to spicy high |
| Temperature | a range on cold · cool · mild · warm · hot · extra hot | cool to hot |
| Bugs | avoid, or don't | don't |
| Minimum | how many applicants must be free, from 1 to the whole party | the whole party |

A range is one track with two handles that stop on the steps. The step names sit under the track and are the only labels.

### For one river

Each river in the river list opens to show the same controls. Changing one there sets it for that river only. A river with any preference of its own stays open, so a difference is never hidden behind a closed river. Setting a river's controls back to the party's values closes it again.

## Results

- At the top: the odds of at least one permit, to the whole percent.
- Then one row per application: date, river, applicant, odds, typical flow, typical temperature, and an Applied toggle.
- An application counts against other parties only once it's toggled to Applied.

### Below the whole party

When the minimum is lower than the party, a switch sits above the results: the party, then each applicant by name. The party plan maximizes the odds of at least one permit. An applicant's plan maximizes the odds that that applicant gets on a trip, and the number at the top becomes theirs. With the minimum at the whole party, the switch isn't shown.

## Open questions

- Do result rows show typical flow and temperature, the frequencies (runnable, good, cold, heat), or both?
- How does the applicants-by-days grid fit a phone?
- Can an applicant who isn't the holder for any application be added just to mark days?
- Do the starting preferences suit most parties, or should they come from the first river picked?
