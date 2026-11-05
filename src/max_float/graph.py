import json

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


### TMP
# cfg = neo4j_config()
# driver = GraphDatabase.driver(cfg["NEO4J_URI"],
#                               auth=(cfg["NEO4J_USERNAME"],
#                                     cfg["NEO4J_PASSWORD"]))
