import gitlab
import os.path
import re
import semver

from dateutil import parser
from datetime import datetime, timedelta, timezone
from gitlab.v4.objects import ProjectIssue, ProjectMergeRequest, ProjectTag
from jinja2 import Template
from typing import Dict, List, Optional, Union
from urllib.parse import unquote


path = os.path.join(os.path.dirname(__file__), "template.md")
with open(path, "r") as f:
    default_template = f.read()
TEMPLATE = Template(default_template, trim_blocks=True)

DEFAULT_IGNORE = [
    "changelog skip",
    "duplicate",
    "exclude from changelog",
    "invalid",
    "no changelog",
    "question",
    "wont fix",
]


class Changelog:
    """A Changelog produces release notes for a single release."""
    _slug_re = re.compile(r"[\s_-]")

    def __init__(self, repo):
        self._repo = repo
        self._ignore = set(self._slug(s) for s in DEFAULT_IGNORE)

    def _slug(self, s: str) -> str:
        """Return a version of the string that's easy to compare."""
        return self._slug_re.sub("", s.casefold())

    def _previous_release(self, version: str) -> Optional[ProjectTag]:
        """Get the release previous to the current one (according to SemVer)."""
        cur_ver = semver.parse_version_info(version[1:])
        prev_ver = semver.parse_version_info("0.0.0")
        prev_rel = None
        for tag in self._repo.tags.list(all=True):
            if not tag.name.startswith("v"):
                continue
            try:
                ver = semver.parse_version_info(tag.name[1:])
            except ValueError:
                continue
            if ver.prerelease or ver.build:
                continue
            # Get the highest version that is not greater than the current one.
            # That means if we're creating a backport v1.1, an already existing v2.0,
            # despite being newer than v1.0, will not be selected.
            if ver < cur_ver and ver > prev_ver:
                prev_rel = tag
                prev_ver = ver
        return prev_rel

    def _issues(self, start: datetime, end: datetime) -> List[ProjectIssue]:
        """Collect issues that were closed in the interval."""
        issues = []
        for x in self._repo.issues.list(state="closed", updated_after=start, all=True):
            # If a previous release's last commit closed an issue, then that issue
            # should be included in the previous release's changelog and not this one.
            # The interval includes the endpoint for this same reason.
            closed_at = parser.parse(x.closed_at)
            if closed_at <= start or closed_at > end:
                continue
            if self._ignore.intersection(self._slug(label) for label in x.labels):
                continue
            else:
                issues.append(x)
        issues.reverse()  # Sort in chronological order.
        return issues

    def _merge_requests(self, start: datetime, end: datetime) -> List[ProjectMergeRequest]:
        """Collect merge requests in the interval."""
        merge_requests = []
        for x in self._repo.mergerequests.list(state="merged", updated_after=start, all=True):
            merged_at = parser.parse(x.merged_at)
            if merged_at <= start or merged_at > end:
                continue
            if self._ignore.intersection(self._slug(label) for label in x.labels):
                continue
            else:
                merge_requests.append(x)
        merge_requests.reverse()  # Sort in chronological order.
        return merge_requests

    def _format_user(self, user: Optional[Dict]) -> Optional[Dict[str, object]]:
        """Format a user for the template."""
        if user is None:
            return None

        return {
            "name": user['name'],
            "url": user['web_url'],
            "username": user['username'],
        }

    def _format_issue(self, issue: ProjectIssue) -> Dict[str, object]:
        """Format an issue for the template."""
        return {
            "author": self._format_user(issue.author),
            "description": issue.description,
            "labels": issue.labels,
            "number": issue.get_id(),
            "title": issue.title,
            "url": issue.web_url,
        }

    def _format_merge_request(
        self, merge_request: ProjectMergeRequest
    ) -> Dict[str, object]:
        """Format a pull request for the template."""
        return {
            "author": self._format_user(merge_request.author),
            "description": merge_request.description,
            "labels": merge_request.labels,
            "merger": self._format_user(merge_request.merged_by),
            "number": merge_request.get_id(),
            "title": merge_request.title,
            "url": merge_request.web_url,
        }

    def _collect_data(self, version: str, commit_sha: str) -> Dict[str, object]:
        """Collect data needed to create the changelog."""
        gitlab_url = self._repo.tags.gitlab.url
        repo = unquote(self._repo.get_id())
        project_name = repo.split("/")[-1]
        previous = self._previous_release(version)
        start = datetime.fromtimestamp(0, tz=timezone.utc)
        prev_tag = None
        compare = None
        if previous:
            previous_created_at = parser.parse(previous.attributes['commit']['created_at'])
            start = previous_created_at + timedelta(minutes=1)
            prev_tag = previous.name
            compare = f"{gitlab_url}/{repo}/-/compare/{prev_tag}...{version}"

        # When the last commit is a PR merge, the commit happens a second or two before
        # the PR and associated issues are closed.
        commit_creation = parser.parse(self._repo.commits.get(id=commit_sha).created_at)
        end = commit_creation + timedelta(minutes=1)
        issues = self._issues(start, end)
        merge_requests = self._merge_requests(start, end)
        return {
            "compare_url": compare,
            "issues": [self._format_issue(i) for i in issues],
            "package": project_name,
            "previous_release": prev_tag,
            "merge_requests": [self._format_merge_request(p) for p in merge_requests],
            "sha": commit_sha,
            "version": version,
            "version_url": f"{gitlab_url}/{repo}/tree/{version}",
        }

    def _render(self, data: Dict[str, object]) -> str:
        """Render the template."""
        return TEMPLATE.render(data).strip()

    def get(self, version: str, sha: str) -> str:
        """Get the changelog for a specific version."""
        data = self._collect_data(version, sha)
        return self._render(data)
