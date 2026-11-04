import json

import boto3


def neo4j_config() -> dict[str, str]:
    client = boto3.client("secretsmanager")
    secret = client.get_secret_value(SecretId="maxfloat/neo4j-kg")
    return json.loads(secret["SecretString"])


### TMP
# cfg = neo4j_config()
# driver = GraphDatabase.driver(cfg["NEO4J_URI"],
#                               auth=(cfg["NEO4J_USERNAME"],
#                                     cfg["NEO4J_PASSWORD"]))
