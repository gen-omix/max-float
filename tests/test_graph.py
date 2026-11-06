from types import SimpleNamespace

from max_float import graph


class Driver:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_server_info(self):
        return SimpleNamespace(address="a.io:7687", agent="Neo4j/5.27-aura")


def test_check(monkeypatch):
    found = {
        "NEO4J_URI": "neo4j+s://a.io",
        "NEO4J_USERNAME": "n",
        "NEO4J_PASSWORD": "p",
    }
    calls = []
    monkeypatch.setattr(graph, "neo4j_config", lambda: found)
    monkeypatch.setattr(
        graph.GraphDatabase,
        "driver",
        lambda uri, auth: calls.append((uri, auth)) or Driver(),
    )
    assert graph.check() == "a.io:7687 Neo4j/5.27-aura"
    assert calls == [("neo4j+s://a.io", ("n", "p"))]
