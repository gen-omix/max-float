"""The web service."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="max-float")

PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>max-float</title>
<h1>max-float</h1>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    """The page."""
    return PAGE
