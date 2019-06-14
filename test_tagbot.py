# Set some environment variables required for import.
from os import environ as env

env["REGISTRATOR_ID"] = "0"
env["GITLAB_URL"] = env["GITLAB_API_TOKEN"] = env["GITLAB_WEBHOOK_TOKEN"] = "abc"

from unittest.mock import Mock, patch

import gitlab
import pytest
import tagbot

good_body = """
Repository: gitlab.foo.com/foo/bar
Version: v0.1.2
Commit: abcdef
"""


def test_parse_body():
    repo, version, commit, err = tagbot.parse_body(good_body)
    assert repo == "foo/bar"
    assert version == "v0.1.2"
    assert commit == "abcdef"
    assert err is None
    repo, version, commit, err = tagbot.parse_body("")
    assert repo is version is commit is None
    assert err == "No repo match"
    repo, version, commit, err = tagbot.parse_body("Repository: gitlab.foo.com/foo/bar")
    assert repo is version is commit is None
    assert err == "No version match"
    repo, version, commit, err = tagbot.parse_body(
        "Repository: gitlab.foo.com/foo/bar\nVersion: v0.1.2"
    )
    assert repo is version is commit is None
    assert err == "No commit match"


def test_get_in():
    d = {"a": {"b": {"c": "d"}}}
    assert tagbot.get_in(d, "a", "b", "c") == "d"
    assert tagbot.get_in(d, "a", "b", "d") is None
    assert tagbot.get_in(d, "a", "b", "c", "d") is None
    assert tagbot.get_in(d, "b", default="foo") == "foo"


@patch("tagbot.handle_event")
def test_handler(handle_event):
    assert tagbot.handler({}, None) == {"statusCode": 403, "body": "Invalid token"}
    assert tagbot.handler({"headers": {"X-Gitlab-Token": "aaa"}}, None) == {
        "statusCode": 403,
        "body": "Invalid token",
    }
    d = {"headers": {"X-Gitlab-Token": "abc"}}
    assert tagbot.handler(d, None)["statusCode"] == 200
    handle_event.called_once_with(d)


@patch("tagbot.handle_merge")
@patch("tagbot.handle_open")
def test_handle_event(handle_open, handle_merge):
    assert tagbot.handle_event({}) == "MR not created by Registrator"
    assert (
        tagbot.handle_event({"object_attributes": {"author_id": 0}}) == "Skipping event"
    )
    assert (
        tagbot.handle_event(
            {"event_type": "merge_request", "object_attributes": {"author_id": 0}}
        )
        == "Unknown or missing action"
    )
    d = {
        "event_type": "merge_request",
        "object_attributes": {"author_id": 0, "action": "open"},
    }
    tagbot.handle_event(d)
    handle_open.called_once_with(d)
    handle_merge.assert_not_called()
    d["object_attributes"]["action"] = "merge"
    tagbot.handle_event(d)
    handle_merge.assert_called_once_with(d)
    handle_open.assert_called_once()  # From before.


def test_handle_merge():
    p = Mock(spec=gitlab.v4.objects.Project)
    p.tags = Mock(spec=gitlab.v4.objects.ProjectTagManager)
    tagbot.client.projects.get = Mock(return_value=p)

    assert (
        tagbot.handle_merge({"changes": {"state": {"previous": "merged"}}})
        == "MR was previously merged"
    )
    assert (
        tagbot.handle_merge({"changes": {"state": {"current": "open"}}})
        == "MR is not merged"
    )
    assert (
        tagbot.handle_merge(
            {
                "changes": {"state": {"current": "merged"}},
                "object_attributes": {
                    "target_branch": "foo",
                    "target": {"default_branch": "master"},
                },
            }
        )
        == "Target branch is not the default"
    )
    assert (
        tagbot.handle_merge({"changes": {"state": {"current": "merged"}}}) is not None
    )
    assert (
        tagbot.handle_merge(
            {
                "changes": {"state": {"current": "merged"}},
                "object_attributes": {"description": good_body},
            }
        )
        is None
    )
    tagbot.client.projects.get.assert_called_once_with("foo/bar", lazy=True)
    p.tags.create.assert_called_once_with({"tag_name": "v0.1.2", "ref": "abcdef"})


def test_handle_open():
    mr = Mock(spec=gitlab.v4.objects.ProjectMergeRequest)
    p = Mock(spec=gitlab.v4.objects.Project)
    p.mergerequests = Mock(spec=gitlab.v4.objects.ProjectMergeRequestManager)
    p.mergerequests.get = Mock(return_value=mr)
    tagbot.client.projects.get = Mock(return_value=p)
    tagbot.merge = False
    assert tagbot.handle_open({}) == "Automatic merging is disabled"
    tagbot.merge = True
    assert tagbot.handle_open({"changes": {"iid": {"previous": 1}}}) == "Not a new MR"
    assert tagbot.handle_open({"object_attributes": {"source_project_id": 1}}) is None
    tagbot.client.projects.get.assert_called_once_with(1, lazy=True)
    mr.approve.assert_called_once_with()
    mr.merge.assert_called_once_with(merge_when_pipeline_succeeds=True)
