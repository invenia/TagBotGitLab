import json
import os
import re
import time
import traceback

import gitlab  # type: ignore
from gitlabchangelog.changelog import Changelog  # type: ignore


POLL_TIMEOUT = 1

# match on group3 to get everything after the host, i.e everything after the single '/'
re_repo = re.compile("Repository:\\s*(http[s]?://)?([^/\\s]+/)(.*)")
re_version = re.compile("Version:\\s*(v.*)")
re_commit = re.compile("Commit:\\s*(.*)")

merge = os.getenv("AUTOMATIC_MERGE", "").lower() == "true"
registrator = int(os.environ["REGISTRATOR_ID"])
token = os.environ["GITLAB_WEBHOOK_TOKEN"]
client = gitlab.Gitlab(
    os.environ["GITLAB_URL"], private_token=os.environ["GITLAB_API_TOKEN"]
)


def handler(evt, _ctx):
    """Lambda entrypoint."""
    try:
        if get_in(evt, "headers", "X-Gitlab-Token") != token:
            status, msg = 403, "Invalid token"
        else:
            status, msg = 200, handle_event(json.loads(evt.get("body", "{}")))
    except Exception:
        traceback.print_exc()
        status, msg = 500, "Runtime error"
    level = "INFO" if status == 200 else "ERROR"
    print(f"STATUS : {status}\n{level} : {msg}")
    return {"statusCode": status, "body": msg or "No error"}


def handle_event(payload):
    """Handle a GitLab event."""
    # MR event payload format :
    # https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#merge-request-events
    print("Payload:", json.dumps(payload, indent=2))
    author_id = get_in(payload, "object_attributes", "author_id")
    if author_id != registrator:
        return f"MR not created by Registrator, MR created by author_id: {author_id}"
    object_kind = payload.get("object_kind")
    if object_kind != "merge_request":
        return f"Not an MR event, Skipping event: {object_kind}"
    a = get_in(payload, "object_attributes", "action")
    if a == "open":
        return handle_open(payload)
    if a == "merge":
        return handle_merge(payload)
    return f"Skipping event, irrelevent or missing action: {a}"


def handle_open(payload):
    """Handle a merge request open event."""
    if not merge:
        return "Automatic merging is disabled"
    if get_in(payload, "changes", "updated_by_id", "previous") is not None:
        return "Not a new MR"
    p_id = get_in(payload, "object_attributes", "source_project_id")
    p = client.projects.get(p_id, lazy=True)
    mr_id = get_in(payload, "object_attributes", "iid")
    mr = p.mergerequests.get(mr_id, lazy=True)

    print("Approving MR")
    mr.approve()

    # Add printing the MR state to assist in debugging cases where the mr.merge() below
    # returns an error
    mr = p.mergerequests.get(mr_id, lazy=False)
    print(mr)

    # Add timeout to wait for the head pipeline to be associated properly with the MR
    # Avoids merge failures
    timeout = 1
    while timeout <= 3 and mr.head_pipeline is None:
        print(f"The MR's head_pipeline is not set - sleeping for {timeout} seconds")
        time.sleep(timeout)
        timeout += 1
        mr = p.mergerequests.get(mr_id, lazy=False)

    # Accepting the MR while the merge_status is "checking" seems to result in a
    # 406 error.
    # To work around this, poll until the merge_status is no longer "checking".
    # See https://gitlab.com/gitlab-org/gitlab/-/issues/196962
    while mr.merge_status == "checking":
        print(f"Polling for merge_status: {mr.merge_status}")
        # Avoid slamming the API
        time.sleep(POLL_TIMEOUT)
        mr = p.mergerequests.get(mr_id, lazy=False)

    print(f"Merging MR {mr}")
    mr.merge(merge_when_pipeline_succeeds=True, should_remove_source_branch=True)
    return "Approved and merged."


def handle_merge(payload):
    """Handle a merge request merge event."""
    # just check the action again for completeness
    action = get_in(payload, "object_attributes", "action")
    if action != "merge":
        return f"Skipping event, not a merge action. action: {action}"
    state = get_in(payload, "object_attributes", "state")
    if state != "merged":
        return f"Skipping event, not a merged state. state: {state}"
    target = get_in(payload, "object_attributes", "target_branch")
    default = get_in(payload, "object_attributes", "target", "default_branch")
    if target != default:
        return "Target branch is not the default"
    body = get_in(payload, "object_attributes", "description", default="")
    print(f"MR body:\n{body}")
    repo, version, commit, err = parse_body(body)
    if err:
        raise Exception("Parsing MR description failed. " + err)
    p = client.projects.get(repo, lazy=True)

    changelog = Changelog(p)
    release_notes = changelog.get(version, commit)

    print(f"Creating release and tag {version} for {repo} at {commit}")
    p.releases.create(
        {
            "tag_name": version,
            "ref": commit,
            "description": release_notes,
            # This can be removed after
            # https://github.com/python-gitlab/python-gitlab/pull/1555 is released
            "name": version,
        }
    )

    return f"Created release and tag {version} for {repo} at {commit}"


def parse_body(body):
    """Parse the MR body."""
    m = re_repo.search(body)
    if not m:
        return None, None, None, "No repo match"
    repo = m[3].strip()
    m = re_version.search(body)
    if not m:
        return None, None, None, "No version match"
    version = m[1].strip()
    m = re_commit.search(body)
    if not m:
        return None, None, None, "No commit match"
    commit = m[1].strip()
    return repo, version, commit, None


def get_in(d, *keys, default=None):
    """Get a nested value from a dict."""
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d
