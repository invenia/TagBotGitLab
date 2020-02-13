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
    handle_event.side_effect = RuntimeError()
    assert tagbot.handler(d, None) == {"statusCode": 500, "body": "Runtime error"}


@patch("tagbot.handle_merge")
@patch("tagbot.handle_open")
def test_handle_event(handle_open, handle_merge):
    # empty payload
    payload = {}
    assert tagbot.handle_event(payload) == \
        "MR not created by Registrator, MR created by author_id: None"

    # an event that's not triggered by the registrar
    payload = {"object_attributes": {"author_id": 1}}
    assert tagbot.handle_event(payload) == \
        "MR not created by Registrator, MR created by author_id: 1"

    # registrar triggered but not a merge request
    payload = {
        "object_attributes": {"author_id": 0},
        "object_kind": "push"
    }
    assert tagbot.handle_event(payload) == \
        "Not an MR event, Skipping event: push"

    # registrar merge_request but irrelevent action
    payload = {
        "object_attributes": {"author_id": 0, "action": "approve"},
        "object_kind": "merge_request"
    }
    assert tagbot.handle_event(payload) == \
        "Skipping event, irrelevent or missing action: approve"

    # registrar merge_request with open action
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {"author_id": 0, "action": "open"},
    }
    tagbot.handle_event(payload)
    handle_open.called_once_with(payload)
    handle_merge.assert_not_called()

    # registrar merge_request with merge action
    payload = {
        "object_kind": "merge_request",
        "object_attributes": {"author_id": 0, "action": "merge"},
    }
    tagbot.handle_event(payload)
    handle_merge.assert_called_once_with(payload)
    handle_open.assert_called_once()  # From before.


def test_handle_merge():
    p = Mock(spec=gitlab.v4.objects.Project)
    p.tags = Mock(spec=gitlab.v4.objects.ProjectTagManager)
    tagbot.client.projects.get = Mock(return_value=p)

    # not a merge action
    payload = {"object_attributes": {"action": "open"}}
    assert tagbot.handle_merge(payload) == \
        "Skipping event, not a merge action. action: open"

    # merge action but not a merged state
    payload = {"object_attributes": {"action": "merge", "state": "conflict"}}
    assert tagbot.handle_merge(payload) == \
        "Skipping event, not a merged state. state: conflict"

    # merge action and merged state, but not to the default branch
    payload = {
        "object_attributes": {
            "action": "merge",
            "state": "merged",
            "target_branch": "develop",
            "target": {"default_branch": "master"}
        }
    }
    assert tagbot.handle_merge(payload) == \
        "Target branch is not the default"

    # merge action, merged state, default branch, but invalid MR description.
    payload = {
        "object_attributes": {
            "action": "merge",
            "state": "merged",
            "target_branch": "master",
            "target": {"default_branch": "master"},
            "description": "invalid description",
        }
    }
    try:
        parse_fail = False
        tagbot.handle_merge(payload)
    except:
        parse_fail = True
    assert (parse_fail)

    # all valid
    payload = {
        "object_attributes": {
            "action": "merge",
            "state": "merged",
            "target_branch": "master",
            "target": {"default_branch": "master"},
            "description": good_body,
        }
    }
    assert tagbot.handle_merge(payload) == \
        "Created tag v0.1.2 for foo/bar at abcdef"
    tagbot.client.projects.get.assert_called_once_with("foo/bar", lazy=True)
    p.tags.create.assert_called_once_with({"tag_name": "v0.1.2", "ref": "abcdef"})


def test_handle_open():
    mr = Mock(spec=gitlab.v4.objects.ProjectMergeRequest)
    p = Mock(spec=gitlab.v4.objects.Project)
    p.mergerequests = Mock(spec=gitlab.v4.objects.ProjectMergeRequestManager)
    p.mergerequests.get = Mock(return_value=mr)
    tagbot.client.projects.get = Mock(return_value=p)

    # when auto merging is disabled
    tagbot.merge = False
    assert tagbot.handle_open({}) == "Automatic merging is disabled"

    # when mr is not a newly opened mr
    tagbot.merge = True
    assert tagbot.handle_open({"changes": {"iid": {"previous": 1}}}) == "Not a new MR"

    # all valid, performs merge
    assert tagbot.handle_open({"object_attributes": {"source_project_id": 1}}) == \
        "Approved and merged."
    tagbot.client.projects.get.assert_called_once_with(1, lazy=True)
    mr.approve.assert_called_once_with()
    mr.merge.assert_called_once_with(
        merge_when_pipeline_succeeds=True, should_remove_source_branch=True
    )
