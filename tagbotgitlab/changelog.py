import os.path
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import unquote

import semver  # type: ignore
from dateutil import parser
from gitlab.v4.objects import (  # type: ignore
    Project,
    ProjectIssue,
    ProjectMergeRequest,
    ProjectTag,
)
from jinja2 import Template


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

    def __init__(self, repo: Project):
        self._repo = repo
        self._ignore = set(self._slug(s) for s in DEFAULT_IGNORE)

    def _slug(self, s: str) -> str:
        """Return a version of the string that's easy to compare."""
        return self._slug_re.sub("", s.casefold())

    def _previous_release(self, version: str) -> Optional[ProjectTag]:
        """Get the release previous to the current one (according to SemVer)."""
        cur_ver = semver.VersionInfo.parse(version[1:])
        prev_ver = semver.VersionInfo.parse("0.0.0")
        prev_rel = None
        for tag in self._repo.tags.list(all=True):
            if not tag.name.startswith("v"):
                continue
            try:
                ver = semver.VersionInfo.parse(tag.name[1:])
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

    def _issues(self, start: datetime, merge_request_ids: List) -> List[ProjectIssue]:
        """Collect issues that were closed by merge requests in the tag."""
        issues = []

        # Only include issues that were explicitly closed by merge requests in this tag
        # This errs on the side of minimizing false positives in favour of occasionally
        # missing issues that should belong to a tag (issues closed that were't
        # closed by the corresponding MR aren't included)
        for x in self._repo.issues.list(
            state="closed",
            updated_after=start,
            all=True,
            order_by="updated_at",
            sort="asc",
        ):
            if any(mr["iid"] in merge_request_ids for mr in x.closed_by()):
                if self._ignore.intersection(self._slug(label) for label in x.labels):
                    continue
                issues.append(x)

        return issues

    def _merge_requests(
        self, start: datetime, commit_shas: List
) -> List[ProjectMergeRequest]:
        """Collect merge requests that are related to the commits since the previous tag."""
        merge_requests = []

        # Have to list all merge requests and cross reference to the commits in this tag
        # as commit.merge_requests() doesn't work for mrs that squash their commits
        # on merge
        for x in self._repo.mergerequests.list(
            state="merged",
            updated_after=start,
            all=True,
            order_by="updated_at",
            sort="asc",
        ):
            if x.merge_commit_sha in commit_shas:
                if self._ignore.intersection(self._slug(label) for label in x.labels):
                    continue
                merge_requests.append(x)

        return merge_requests

    def _format_user(self, user: Optional[Dict]) -> Optional[Dict[str, object]]:
        """Format a user for the template."""
        if user is None:
            return None

        return {
            "name": user["name"],
            "url": user["web_url"],
            "username": user["username"],
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

        # Get previous tag if it exists to compare this tag to
        previous = self._previous_release(version)
        start = datetime.fromtimestamp(0, tz=timezone.utc)
        prev_tag = None
        compare = None
        if previous:
            previous_created_at = parser.parse(
                previous.attributes["commit"]["created_at"]
            )
            start = previous_created_at + timedelta(minutes=1)
            prev_tag = previous.name
            compare = f"{gitlab_url}/{repo}/-/compare/{prev_tag}...{version}"

        tag_commits = self._repo.repository_compare(prev_tag, version)['commits']

        # Get merge requests where the merge commit is one of the commits in the tag
        # Works even for merge requests that squash their commits on merge
        tag_commit_shas = [commit_detail["id"] for commit_detail in tag_commits]
        merge_requests = self._merge_requests(start, tag_commit_shas)

        # Get issues that were explicitly closed by MRs in the tag
        issues = self._issues(start, [mr.iid for mr in merge_requests])

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
