from datetime import datetime
from unittest.mock import Mock

import gitlab

from tagbotgitlab.changelog import Changelog


def test_previous_release():
    p = Mock(spec=gitlab.v4.objects.Project)
    p.tags = Mock(spec=gitlab.v4.objects.ProjectTagManager)

    tag_1 = Mock(spec=gitlab.v4.objects.ProjectTag)
    tag_1.name = "v0.0.1"
    tag_1.attributes = {"commit": {"created_at": "2020-01-01 11:00:00"}}
    tag_2 = Mock(spec=gitlab.v4.objects.ProjectTag)
    tag_2.name = "v0.0.2"
    tag_2.attributes = {"commit": {"created_at": "2020-01-01 11:00:00"}}
    p.tags.list = Mock(return_value=[tag_1, tag_2])

    changelog = Changelog(p)

    assert changelog._previous_release("v0.1.0") == tag_2
    assert changelog._previous_release("v0.0.3") == tag_2
    assert changelog._previous_release("v0.0.2") == tag_1
    assert changelog._previous_release("v0.0.1") is None
    assert changelog._previous_release("v0.0.0") is None


def test_issues():
    p = Mock(spec=gitlab.v4.objects.Project)

    issue_1 = Mock(spec=gitlab.v4.objects.Issue)
    issue_1.closed_at = "2020-01-01 11:00:00"
    issue_1.labels = ["bugfix"]

    # This issue should not appear in any of the results
    issue_2 = Mock(spec=gitlab.v4.objects.MergeRequest)
    issue_2.closed_at = "2020-01-01 11:00:00"
    issue_2.labels = ["changelog_skip"]

    all_issues = [issue_1, issue_2]
    p.issues = Mock(spec=gitlab.v4.objects.ProjectIssueManager)
    p.issues.list = Mock(return_value=all_issues)

    changelog = Changelog(p)

    start = datetime(2020, 1, 1, 10, 59)
    end = datetime(2020, 1, 1, 12)
    assert changelog._issues(start, end) == [issue_1]

    # Test doesn't include starting point
    start = datetime(2020, 1, 1, 11)
    assert changelog._issues(start, end) == []

    # Test includes end point
    start = datetime(2020, 1, 1, 10)
    end = datetime(2020, 1, 1, 11)
    assert changelog._issues(start, end) == [issue_1]


def test_merge_requests():
    p = Mock(spec=gitlab.v4.objects.Project)

    merge_request_1 = Mock(spec=gitlab.v4.objects.MergeRequest)
    merge_request_1.merged_at = "2020-01-01 11:00:00"
    merge_request_1.labels = []
    merge_request_2 = Mock(spec=gitlab.v4.objects.MergeRequest)
    merge_request_2.merged_at = "2020-01-01 20:00:00"
    merge_request_2.labels = ["bugfix"]

    # This merge request should not appear in any of the results
    merge_request_3 = Mock(spec=gitlab.v4.objects.MergeRequest)
    merge_request_3.merged_at = "2020-01-01 20:00:00"
    merge_request_3.labels = ["changelog_skip"]

    all_merge_requests = [merge_request_1, merge_request_2, merge_request_3]
    p.mergerequests = Mock(spec=gitlab.v4.objects.MergeRequestManager)
    p.mergerequests.list = Mock(return_value=all_merge_requests)

    changelog = Changelog(p)

    start = datetime(2020, 1, 1, 10, 59)
    end = datetime(2020, 1, 1, 12)
    assert changelog._merge_requests(start, end) == [merge_request_1]

    # Test doesn't include starting point
    start = datetime(2020, 1, 1, 11)
    end = datetime(2020, 1, 1, 12)
    assert changelog._merge_requests(start, end) == []

    # Test includes end point
    start = datetime(2020, 1, 1, 10)
    end = datetime(2020, 1, 1, 11)
    assert changelog._merge_requests(start, end) == [merge_request_1]

    # Test returns in reverse chronological order
    start = datetime(2020, 1, 1, 10, 59)
    end = datetime(2020, 1, 1, 20)
    assert changelog._merge_requests(start, end) == [merge_request_2, merge_request_1]

    start = datetime(2020, 1, 1, 13)
    end = datetime(2020, 1, 1, 20)
    assert changelog._merge_requests(start, end) == [merge_request_2]

    start = datetime(2015, 1, 1)
    end = datetime(2015, 1, 2)
    assert changelog._merge_requests(start, end) == []


def test_format_issue():
    p = Mock(spec=gitlab.v4.objects.Project)
    changelog = Changelog(p)

    author = {
        "id": 1,
        "name": "John Smith",
        "web_url": "https://gitlab.foo.com/john.smith",
        "username": "john.smith",
    }

    issue = Mock(spec=gitlab.v4.objects.Issue)
    issue.description = ""
    issue.title = "Issue"
    issue.web_url = "https://gitlab.foo.com/foo/~/issues/1"
    issue.closed_at = "2020-01-01 11:00:00"
    issue.author = author
    issue.labels = ["bugfix"]

    expected = {
        "author": {
            "name": "John Smith",
            "url": "https://gitlab.foo.com/john.smith",
            "username": "john.smith",
        },
        "description": "",
        "labels": ["bugfix"],
        "number": issue.get_id(),
        "title": "Issue",
        "url": "https://gitlab.foo.com/foo/~/issues/1",
    }
    assert changelog._format_issue(issue) == expected


def test_format_mergerequest():
    p = Mock(spec=gitlab.v4.objects.Project)
    changelog = Changelog(p)

    author = {
        "id": 1,
        "name": "John Smith",
        "web_url": "https://gitlab.foo.com/john.smith",
        "username": "john.smith",
    }

    merge_request = Mock(spec=gitlab.v4.objects.Issue)
    merge_request.description = ""
    merge_request.title = "Merge Request"
    merge_request.web_url = "https://gitlab.foo.com/foo/~/merge_requests/1"
    merge_request.merged_at = "2020-01-01 11:00:00"
    merge_request.author = author
    merge_request.labels = ["bugfix"]
    merge_request.merged_by = author

    expected_user = {
        "name": "John Smith",
        "url": "https://gitlab.foo.com/john.smith",
        "username": "john.smith",
    }
    expected = {
        "author": expected_user,
        "description": "",
        "labels": ["bugfix"],
        "merger": expected_user,
        "number": merge_request.get_id(),
        "title": "Merge Request",
        "url": "https://gitlab.foo.com/foo/~/merge_requests/1",
    }
    assert changelog._format_merge_request(merge_request) == expected


def test_collect_data():
    p = Mock(spec=gitlab.v4.objects.Project)
    p.get_id = Mock(return_value="foo/bar")
    changelog = Changelog(p)

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
    commit.created_at = "2020-02-01 11:00:00"
    p.commits = Mock(spec=gitlab.v4.objects.ProjectCommitManager)
    p.commits.get = Mock(return_value=commit)

    author = {
        "name": "John Smith",
        "web_url": "https://gitlab.foo.com/john.smith",
        "username": "john.smith",
    }
    issue = Mock(spec=gitlab.v4.objects.Issue)
    issue.closed_at = "2020-01-15 11:00:00"
    issue.labels = []
    issue.author = author
    issue.description = ""
    issue.title = "Issue"
    issue.web_url = "https://gitlab.foo.com/foo/bar/~/issues/2"
    p.issues = Mock(spec=gitlab.v4.objects.ProjectIssueManager)
    p.issues.list = Mock(return_value=[issue])

    merge_request = Mock(spec=gitlab.v4.objects.MergeRequest)
    merge_request.merged_at = "2020-01-15 11:00:00"
    merge_request.labels = []
    merge_request.author = author
    merge_request.description = ""
    merge_request.title = "Merge Request"
    merge_request.web_url = "https://gitlab.foo.com/foo/bar/~/merge_requests/2"
    merge_request.merged_by = author
    p.mergerequests = Mock(spec=gitlab.v4.objects.MergeRequestManager)
    p.mergerequests.list = Mock(return_value=[merge_request])

    version = "v0.1.2"
    commit = "abcdef"

    expected_user = {
        "name": "John Smith",
        "url": "https://gitlab.foo.com/john.smith",
        "username": "john.smith",
    }
    expected_merge_request = {
        "author": expected_user,
        "description": "",
        "labels": [],
        "merger": expected_user,
        "number": merge_request.get_id(),
        "title": "Merge Request",
        "url": "https://gitlab.foo.com/foo/bar/~/merge_requests/2",
    }
    expected_issue = {
        "author": expected_user,
        "description": "",
        "labels": [],
        "number": issue.get_id(),
        "title": "Issue",
        "url": "https://gitlab.foo.com/foo/bar/~/issues/2",
    }
    expected = {
        "compare_url": "gitlab.foo.com/foo/bar/-/compare/v0.1.0...v0.1.2",
        "issues": [expected_issue],
        "package": "bar",
        "previous_release": prev_tag.name,
        "merge_requests": [expected_merge_request],
        "sha": commit,
        "version": version,
        "version_url": "gitlab.foo.com/foo/bar/tree/v0.1.2",
    }
    assert changelog._collect_data(version, commit) == expected
