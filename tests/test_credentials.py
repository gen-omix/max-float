import pytest

from max_float import config, credentials, graph

AWS = ("AWS_ACCESS_KEY_ID", "AWS_SHARED_CREDENTIALS_FILE", "AWS_PROFILE")


@pytest.fixture
def file(tmp_path):
    path = tmp_path / "credentials.txt"
    path.write_text("# Neo4j Aura\nNEO4J_URI=neo4j+s://a.io\n\nNEO4J_PASSWORD = p=q\n")
    return path


def test_read_skips_comments_and_blanks(file):
    assert credentials.read(file) == {
        "NEO4J_URI": "neo4j+s://a.io",
        "NEO4J_PASSWORD": "p=q",
    }


def test_environment_comes_first(monkeypatch, file):
    monkeypatch.setenv("NEO4J_URI", "bolt://env")
    assert credentials.get("NEO4J_URI", file) == "bolt://env"


def test_file_when_not_in_environment(monkeypatch, file):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    assert credentials.get("NEO4J_URI", file) == "neo4j+s://a.io"


def test_missing_without_file(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    assert credentials.get("NEO4J_URI", None) is None


def test_aws_uses_the_file_when_not_in_environment(monkeypatch, tmp_path):
    for name in AWS:
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / "aws"
    session = credentials.aws(path)
    assert session._session.get_config_variable("credentials_file") == str(path)


def test_aws_environment_comes_first(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/env/aws")
    session = credentials.aws(tmp_path / "aws")
    assert session._session.get_config_variable("credentials_file") == "/env/aws"


def test_neo4j_without_aws(monkeypatch, file):
    file.write_text("NEO4J_URI=u\nNEO4J_USERNAME=n\nNEO4J_PASSWORD=p\n")
    for name in graph.NEO4J:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "NEO4J_CREDENTIALS", file)
    monkeypatch.setattr(credentials, "aws", None)
    assert graph.neo4j_config() == {
        "NEO4J_URI": "u",
        "NEO4J_USERNAME": "n",
        "NEO4J_PASSWORD": "p",
    }


def test_read_json(tmp_path):
    path = tmp_path / "neo4j.json"
    path.write_text('{"NEO4J_URI": "neo4j+s://a.io"}')
    assert credentials.read(path) == {"NEO4J_URI": "neo4j+s://a.io"}
