# max-float

**Max flow, max float.** A river permit planner that helps boaters pick lottery launch dates, combining a knowledge graph, an MCP server, and an LLM chatbot with probability-of-success estimates from past lottery data.

> Status: early. See [ROADMAP.md](ROADMAP.md) for the plan and timeline.

## What it will do

Tell it when you can go, how long a trip you want, and which rivers you're considering. It ranks launch dates by the chance you win the permit *and* the chance conditions (flow, heat) match what you like.

## Quickstart

```bash
uv sync
uv run pytest
uv run max-float
```

Copy `.env.example` to `.env` and fill in credentials as later phases need them.

## Layout

```
src/max_float/
  data/        # USGS, RIDB, hand-compiled lottery stats
  models/      # odds model layers + backtest
  graph/       # Neo4j schema and loaders
  mcp_server/  # MCP tools
  app/         # Streamlit chatbot
data/
  raw/         # cached downloads (git-ignored)
  processed/   # cleaned outputs (git-ignored)
  manual/      # small hand-compiled CSVs (committed)
```

## Disclaimer

Not safety or navigation advice. Check with the managing agency and use your own judgment on the water.

## Data credits

- Flow data: U.S. Geological Survey
- Permit and facility data: Recreation.gov
- Lottery statistics: managing-agency publications (sources listed per row)
