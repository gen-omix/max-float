import json

from neo4j import Driver, GraphDatabase

from max_float import config, credentials

NEO4J = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")


def neo4j_config() -> dict[str, str]:
    """Neo4j's URI, username and password from the environment or
    `config.NEO4J_CREDENTIALS`, else from the `config.NEO4J_SECRET` AWS secret."""
    found = {name: credentials.get(name, config.NEO4J_CREDENTIALS) for name in NEO4J}
    if all(found.values()):
        return found
    client = credentials.aws(config.AWS_CREDENTIALS).client("secretsmanager")
    secret = client.get_secret_value(SecretId=config.NEO4J_SECRET)
    return json.loads(secret["SecretString"])


def driver() -> Driver:
    """A Neo4j driver for the instance in `neo4j_config`."""
    found = neo4j_config()
    auth = found["NEO4J_USERNAME"], found["NEO4J_PASSWORD"]
    return GraphDatabase.driver(found["NEO4J_URI"], auth=auth)


def check() -> str:
    """Connect and sign in to Neo4j, and return the server's address and version.
    Raises if the instance can't be reached or refuses the credentials."""
    with driver() as connection:
        server = connection.get_server_info()
    return f"{server.address} {server.agent}"
