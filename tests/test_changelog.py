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
    # State this issue was closed by MR with iid 1
    issue_1.closed_by =  Mock(return_value=[{"iid": "1"}])

    # This issue should not appear in any of the results
    issue_2 = Mock(spec=gitlab.v4.objects.MergeRequest)
    issue_2.closed_at = "2020-01-01 11:00:00"
    issue_2.labels = ["changelog_skip"]
     # State this issue was closed by MR with iid 2
    issue_2.closed_by = Mock(return_value=[{"iid": "2"}])

    all_issues = [issue_1, issue_2]
    p.issues = Mock(spec=gitlab.v4.objects.ProjectIssueManager)
    p.issues.list = Mock(return_value=all_issues)

    changelog = Changelog(p)

    start = datetime(2020, 1, 1, 10, 59)
    included_mrs_in_tag = ["1"]
    assert changelog._issues(start, included_mrs_in_tag) == [issue_1]

    # Test including MR that closes issue that is labeled to be skipped
    included_mrs_in_tag = ["1", "2"]
    assert changelog._issues(start, included_mrs_in_tag) == [issue_1]

    # Test with the API saying issue_1 was not updated after start
    p.issues.list = Mock(return_value=[issue_2])
    assert changelog._issues(start, included_mrs_in_tag) == []


def test_merge_requests():
    p = Mock(spec=gitlab.v4.objects.Project)

    merge_request_1 = Mock(spec=gitlab.v4.objects.ProjectMergeRequest)
    merge_request_1.merged_at = "2020-01-01 11:00:00"
    merge_request_1.labels = []
    merge_request_1.merge_commit_sha = "1a2b3c"

    merge_request_2 = Mock(spec=gitlab.v4.objects.ProjectMergeRequest)
    merge_request_2.merged_at = "2020-01-01 20:00:00"
    merge_request_2.labels = ["bugfix"]
    merge_request_2.merge_commit_sha = "2b3c4d"

    # This merge request should not appear in any of the results
    merge_request_3 = Mock(spec=gitlab.v4.objects.ProjectMergeRequest)
    merge_request_3.merged_at = "2020-01-01 20:00:00"
    merge_request_3.labels = ["changelog_skip"]
    merge_request_3.merge_commit_sha = "3c4d4e"

    all_merge_requests = [merge_request_1, merge_request_2, merge_request_3]
    p.mergerequests = Mock(spec=gitlab.v4.objects.MergeRequestManager)
    p.mergerequests.list = Mock(return_value=all_merge_requests)

    changelog = Changelog(p)

    start = datetime(2020, 1, 1, 10, 59)
    commit_shas = ["1a2b3c"]
    assert changelog._merge_requests(start, commit_shas) == [merge_request_1]

    # Test MR that is labelled with a skip label is not included
    start = datetime(2020, 1, 1, 10)
    commit_shas = ["1a2b3c", "3c4d4e"]
    assert changelog._merge_requests(start, commit_shas) == [merge_request_1]

    # Test returns in chronological order
    start = datetime(2020, 1, 1, 10, 59)
    commit_shas = ["1a2b3c", "2b3c4d", "3c4d4e"]
    assert changelog._merge_requests(start, commit_shas) == [
        merge_request_1,
        merge_request_2,
    ]

    # Test with only the 2nd and 3rd MRs included in the commits diff since the prev tag
    start = datetime(2020, 1, 1, 13)
    commit_shas = ["2b3c4d", "3c4d4e"]
    assert changelog._merge_requests(start, commit_shas) == [merge_request_2]

    # Test when the API doesn't return any merge requests
    p.mergerequests.list = Mock(return_value=[])
    assert changelog._merge_requests(start, commit_shas) == []


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

    # Set up tags
    version = "v0.1.2"
    commit_sha = "abcdef"

    p.tags = Mock(spec=gitlab.v4.objects.ProjectTagManager)
    p.tags.gitlab = Mock(spec=gitlab.Gitlab)
    p.tags.gitlab.url = "gitlab.foo.com"

    prev_tag = Mock(spec=gitlab.v4.objects.ProjectTag)
    prev_tag.name = "v0.1.0"
    prev_tag.attributes = {"commit": {"created_at": "2020-01-01 11:00:00"}}

    tag = Mock(spec=gitlab.v4.objects.ProjectTag)
    tag.name = version
    tag.attributes = {"commit": {"created_at": "2020-02-01 11:00:00"}}

    p.tags.list = Mock(return_value=[prev_tag, tag])

    # Set up commits
    commit = Mock(spec=gitlab.v4.objects.ProjectCommit)
    commit.id = commit_sha
    commit.created_at = "2020-02-01 11:00:00"

    p.commits = Mock(spec=gitlab.v4.objects.ProjectCommitManager)
    p.commits.get = Mock(return_value=commit)

    commits_detail = {"commits": [{"id": commit_sha}]}
    p.repository_compare = Mock(return_value=commits_detail)

    # Set up GitLab user
    author = {
        "name": "John Smith",
        "web_url": "https://gitlab.foo.com/john.smith",
        "username": "john.smith",
    }

    # Set up merged merge requests in the repo
    merge_request = Mock(spec=gitlab.v4.objects.MergeRequest)
    merge_request.merged_at = "2020-01-15 11:00:00"
    merge_request.labels = []
    merge_request.merge_commit_sha = commit_sha
    merge_request.iid = "1"
    merge_request.author = author
    merge_request.description = ""
    merge_request.title = "Merge Request"
    merge_request.web_url = "https://gitlab.foo.com/foo/bar/~/merge_requests/1"
    merge_request.merged_by = author

    # Note this merge request is not included in the commits returned from
    # repository_compare (not part of the tag) so it should not appear in the result
    # even though it was merged during the time interval between the previous tag
    # and this tag
    merge_request_2 = Mock(spec=gitlab.v4.objects.MergeRequest)
    merge_request_2.merged_at = "2020-01-15 11:00:00"
    merge_request_2.labels = []
    merge_request_2.merge_commit_sha = "2b3c4d"
    merge_request_2.iid = "2"

    p.mergerequests = Mock(spec=gitlab.v4.objects.MergeRequestManager)
    p.mergerequests.list = Mock(return_value=[merge_request, merge_request_2])

    # Set up closed issues in the repo
    issue = Mock(spec=gitlab.v4.objects.Issue)
    issue.closed_at = "2020-01-15 11:00:00"
    issue.closed_by =  Mock(return_value=[{"iid": merge_request.iid}])
    issue.labels = []
    issue.author = author
    issue.description = ""
    issue.title = "Issue"
    issue.web_url = "https://gitlab.foo.com/foo/bar/~/issues/1"

    # Note this issue was not closed by a MR that belongs to the tag so it should
    # not appear in the release notes even though it was closed during the time interval
    # between the previous tag and this tag
    issue_2 = Mock(spec=gitlab.v4.objects.Issue)
    issue_2.closed_at = "2020-01-15 11:00:00"
    issue_2.closed_by =  Mock(return_value=[{"iid": merge_request_2.iid}])

    # Note this issue was not closed by a MR that belongs to the tag so it should
    # not appear in the release notes even though it was closed during the time interval
    # between the previous tag and this tag
    issue_3 = Mock(spec=gitlab.v4.objects.Issue)
    issue_3.closed_at = "2020-01-15 11:00:00"
    issue_3.closed_by =  Mock(return_value=[])

    p.issues = Mock(spec=gitlab.v4.objects.ProjectIssueManager)
    p.issues.list = Mock(return_value=[issue, issue_2, issue_3])

    # Test changelog returned is as expected
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
        "url": "https://gitlab.foo.com/foo/bar/~/merge_requests/1",
    }
    expected_issue = {
        "author": expected_user,
        "description": "",
        "labels": [],
        "number": issue.get_id(),
        "title": "Issue",
        "url": "https://gitlab.foo.com/foo/bar/~/issues/1",
    }
    expected = {
        "compare_url": "gitlab.foo.com/foo/bar/-/compare/v0.1.0...v0.1.2",
        "issues": [expected_issue],
        "package": "bar",
        "previous_release": prev_tag.name,
        "merge_requests": [expected_merge_request],
        "sha": commit_sha,
        "version": version,
        "version_url": "gitlab.foo.com/foo/bar/tree/v0.1.2",
    }
    assert changelog._collect_data(version, commit_sha) == expected
