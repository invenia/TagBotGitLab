from os import environ as env
from unittest.mock import Mock, call, patch

import gitlab


# Set some environment variables required for import.
env["REGISTRATOR_ID"] = "0"
env["GITLAB_URL"] = env["GITLAB_API_TOKEN"] = env["GITLAB_WEBHOOK_TOKEN"] = "abc"

import tagbotgitlab.tagbot as tagbot  # isort:skip  # noqa: E402


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

    # with protocol in url
    body = (
        "Repository: https://gitlab.foo.com/goodRepo\nVersion: v0.1.2\nCommit: abcdef"
    )
    repo, version, commit, err = tagbot.parse_body(body)
    assert repo == "goodRepo"

    # w/o protocol and no repo prefix
    body = "Repository: gitlab.foo.com/goodRepo\nVersion: v0.1.2\nCommit: abcdef"
    repo, version, commit, err = tagbot.parse_body(body)
    assert repo == "goodRepo"

    # single repo prefix
    body = "Repository: gitlab.foo.com/p1/goodRepo\nVersion: v0.1.2\nCommit: abcdef"
    repo, version, commit, err = tagbot.parse_body(body)
    assert repo == "p1/goodRepo"

    # multiple repo prefixs
    body = (
        "Repository: gitlab.foo.com/p1/p2/p3/goodRepo\nVersion: v0.1.2\nCommit: abcdef"
    )
    repo, version, commit, err = tagbot.parse_body(body)
    assert repo == "p1/p2/p3/goodRepo"


def test_get_in():
    d = {"a": {"b": {"c": "d"}}}
    assert tagbot.get_in(d, "a", "b", "c") == "d"
    assert tagbot.get_in(d, "a", "b", "d") is None
    assert tagbot.get_in(d, "a", "b", "c", "d") is None
    assert tagbot.get_in(d, "b", default="foo") == "foo"


@patch("tagbotgitlab.tagbot.handle_event")
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


@patch("tagbotgitlab.tagbot.handle_merge")
@patch("tagbotgitlab.tagbot.handle_open")
def test_handle_event(handle_open, handle_merge):
    # empty payload
    payload = {}
    assert (
        tagbot.handle_event(payload)
        == "MR not created by Registrator, MR created by author_id: None"
    )

    # an event that's not triggered by the registrar
    payload = {"object_attributes": {"author_id": 1}}
    assert (
        tagbot.handle_event(payload)
        == "MR not created by Registrator, MR created by author_id: 1"
    )

    # registrar triggered but not a merge request
    payload = {"object_attributes": {"author_id": 0}, "object_kind": "push"}
    assert tagbot.handle_event(payload) == "Not an MR event, Skipping event: push"

    # registrar merge_request but irrelevent action
    payload = {
        "object_attributes": {"author_id": 0, "action": "approve"},
        "object_kind": "merge_request",
    }
    assert (
        tagbot.handle_event(payload)
        == "Skipping event, irrelevent or missing action: approve"
    )

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
    tagbot.client.projects.get = Mock(return_value=p)
    p.get_id = Mock(return_value="foo/bar")

    p.tags = Mock(spec=gitlab.v4.objects.ProjectTagManager)
    p.tags.gitlab = Mock(spec=gitlab.Gitlab)
    p.tags.gitlab.url = "gitlab.foo.com"

    prev_tag = Mock(spec=gitlab.v4.objects.ProjectTag)
    prev_tag.name = "v0.1.0"
    prev_tag.attributes = {"commit": {"created_at": "2020-01-01 11:00:00"}}
    tag = Mock(spec=gitlab.v4.objects.ProjectTag)
    tag.name = "v0.1.2"
    tag.attributes = {"commit": {"created_at": "2020-02-01 11:00:00"}}
    p.tags.list = Mock(return_value=[prev_tag, tag])

    commit = Mock(spec=gitlab.v4.objects.ProjectCommit)
    commit.id = "1a2b3c"
    commit.created_at = "2020-02-01 11:00:00"
    p.commits = Mock(spec=gitlab.v4.objects.ProjectCommitManager)
    p.commits.get = Mock(return_value=commit)

    commits_detail = {"commits": [{"id": commit.id}]}
    p.repository_compare = Mock(return_value=commits_detail)

    author = {
        "name": "John Smith",
        "web_url": "https://gitlab.foo.com/john.smith",
        "username": "john.smith",
    }

    merge_request = Mock(spec=gitlab.v4.objects.MergeRequest)
    merge_request.merged_at = "2020-01-15 11:00:00"
    merge_request.labels = []
    merge_request.merge_commit_sha = "1a2b3c"
    merge_request.iid = "1"
    merge_request.author = author
    merge_request.description = ""
    merge_request.title = "Merge Request"
    merge_request.web_url = "https://gitlab.foo.com/foo/bar/~/merge_requests/2"
    merge_request.merged_by = author
    p.mergerequests = Mock(spec=gitlab.v4.objects.MergeRequestManager)
    p.mergerequests.list = Mock(return_value=[merge_request])

    issue = Mock(spec=gitlab.v4.objects.Issue)
    issue.closed_at = "2020-01-15 11:00:00"
    issue.closed_by = Mock(return_value=[{"iid": merge_request.iid}])
    issue.labels = []
    issue.author = author
    issue.description = ""
    issue.title = "Issue"
    issue.web_url = "https://gitlab.foo.com/foo/bar/~/issues/2"
    p.issues = Mock(spec=gitlab.v4.objects.ProjectIssueManager)
    p.issues.list = Mock(return_value=[issue])

    # not a merge action
    payload = {"object_attributes": {"action": "open"}}
    assert (
        tagbot.handle_merge(payload)
        == "Skipping event, not a merge action. action: open"
    )

    # merge action but not a merged state
    payload = {"object_attributes": {"action": "merge", "state": "conflict"}}
    assert (
        tagbot.handle_merge(payload)
        == "Skipping event, not a merged state. state: conflict"
    )

    # merge action and merged state, but not to the default branch
    payload = {
        "object_attributes": {
            "action": "merge",
            "state": "merged",
            "target_branch": "develop",
            "target": {"default_branch": "master"},
        }
    }
    assert tagbot.handle_merge(payload) == "Target branch is not the default"

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
    except Exception:
        parse_fail = True
    assert parse_fail

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
    assert tagbot.handle_merge(payload) == "Created tag v0.1.2 for foo/bar at abcdef"
    tagbot.client.projects.get.assert_called_once_with("foo/bar", lazy=True)
    p.tags.create.assert_called_once_with({"tag_name": "v0.1.2", "ref": "abcdef"})


@patch("time.sleep", return_value=None)
def test_handle_open(patched_time_sleep):
    # MR that is not ready to be accepted/merged
    mr = Mock(spec=gitlab.v4.objects.ProjectMergeRequest)
    mr.head_pipeline = {"id": 62299}
    mr.merge_status = "checking"

    # MR that is approved and ready to be accepted/merged
    mr_approved = Mock(spec=gitlab.v4.objects.ProjectMergeRequest)
    mr_approved.head_pipeline = {"id": 62299}
    mr_approved.merge_status = "can_be_merged"

    p = Mock(spec=gitlab.v4.objects.Project)
    p.mergerequests = Mock(spec=gitlab.v4.objects.ProjectMergeRequestManager)
    p.mergerequests.get = Mock(return_value=mr)
    tagbot.client.projects.get = Mock(return_value=p)

    # when auto merging is disabled
    tagbot.merge = False
    assert tagbot.handle_open({}) == "Automatic merging is disabled"

    # when mr is not a newly opened mr
    tagbot.merge = True
    assert (
        tagbot.handle_open({"changes": {"updated_by_id": {"previous": 1}}})
        == "Not a new MR"
    )

    # Return the approved MR on the 3rd get call (inside merge_status check)
    p.mergerequests.get = Mock(side_effect=[mr, mr, mr_approved])

    # all valid, performs merge
    assert (
        tagbot.handle_open({"object_attributes": {"source_project_id": 1}})
        == "Approved and merged."
    )

    tagbot.client.projects.get.assert_called_once_with(1, lazy=True)
    # Assert we've gotten the MR three times
    # 1. Before approval 2. After approval 3. Before merging
    calls = [
        call(None, lazy=True),
        call(None, lazy=False),
        call(None, lazy=False),
    ]
    p.mergerequests.get.assert_has_calls(calls)
    mr.approve.assert_called_once_with()
    mr_approved.merge.assert_called_once_with(
        merge_when_pipeline_succeeds=True, should_remove_source_branch=True
    )

    # Test with head pipeline not set
    # Note it should still approve and try merging, GitLab API will throw an error if
    # the merge is not valid but this is mocked so it succeeds fine
    mr = Mock(spec=gitlab.v4.objects.ProjectMergeRequest)
    mr.head_pipeline = None
    mr.merge_status = "can_be_merged"
    p = Mock(spec=gitlab.v4.objects.Project)
    p.mergerequests = Mock(spec=gitlab.v4.objects.ProjectMergeRequestManager)
    p.mergerequests.get = Mock(return_value=mr)
    tagbot.client.projects.get = Mock(return_value=p)

    assert (
        tagbot.handle_open({"object_attributes": {"source_project_id": 1}})
        == "Approved and merged."
    )
    tagbot.client.projects.get.assert_called_once_with(1, lazy=True)
    # Assert we've gotten the MR 5 times because of the retries
    calls = [
        call(None, lazy=True),
        call(None, lazy=False),
        call(None, lazy=False),
        call(None, lazy=False),
        call(None, lazy=False),
    ]
    p.mergerequests.get.assert_has_calls(calls)
    mr.approve.assert_called_once_with()
    mr.merge.assert_called_once_with(
        merge_when_pipeline_succeeds=True, should_remove_source_branch=True
    )
