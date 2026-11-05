"""Credentials from the environment, else from the files named in `config`."""

import json
import os
from pathlib import Path

import boto3
import botocore.session


def read(path: Path) -> dict[str, str]:
    """A credentials file's values: a .json file's object, else its KEY=VALUE
    lines, skipping blanks and # comments."""
    text = path.expanduser().read_text()
    if path.suffix == ".json":
        return json.loads(text)
    found = {}
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            found[key.strip()] = value.strip()
    return found


def get(name: str, path: Path | None) -> str | None:
    """The environment variable `name`, else its value in the file at `path`."""
    if name in os.environ:
        return os.environ[name]
    return read(path).get(name) if path else None


def aws(path: Path | None) -> boto3.Session:
    """An AWS session. Credentials come from the environment, else the AWS shared
    credentials file at `path`, else AWS's usual places."""
    env = {"AWS_ACCESS_KEY_ID", "AWS_SHARED_CREDENTIALS_FILE", "AWS_PROFILE"}
    if not path or env & os.environ.keys():
        return boto3.Session()
    session = botocore.session.Session()
    session.set_config_variable("credentials_file", str(path.expanduser()))
    return boto3.Session(botocore_session=session)
