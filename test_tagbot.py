# Set some environment variables required for import.
from os import environ as env

env["REGISTRATOR_ID"] = "0"
env["GITLAB_URL"] = env["GITLAB_API_TOKEN"] = env["GITLAB_WEBHOOK_TOKEN"] = ""

import pytest
import tagbot


def test_parse_body():
    body = """
    Repository: gitlab.foo.com/foo/bar
    Version: v0.1.2
    Commit: abcdef
    """
    repo, version, commit, err = tagbot.parse_body(body)
    assert repo == "foo/bar"
    assert version == "v0.1.2"
    assert commit == "abcdef"
    assert err is None


def test_get_in():
    d = {"a": {"b": {"c": "d"}}}
    assert tagbot.get_in(d, "a", "b", "c") == "d"
    assert tagbot.get_in(d, "a", "b", "d") is None
    assert tagbot.get_in(d, "a", "b", "c", "d") is None
    assert tagbot.get_in(d, "b", default="foo") == "foo"