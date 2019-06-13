import gitlab
import json
import os
import re
import traceback

re_repo = re.compile("Repository:.*/(.*/.*)")
re_version = re.compile("Version:\s*(v.*)")
re_commit = re.compile("Commit:\s*(.*)")

merge = os.getenv("AUTOMATIC_MERGE", "").lower() == "true"
registrator = int(os.environ["REGISTRATOR_ID"])
token = os.environ["GITLAB_WEBHOOK_TOKEN"]
client = gitlab.Gitlab(
    os.environ["GITLAB_URL"], private_token=os.environ["GITLAB_API_TOKEN"]
)


def main(evt, _ctx):
    """Lambda entrypoint."""
    try:
        if get_in(evt, "headers", "X-Gitlab-Token") != token:
            status, err = 403, "Invalid token"
        else:
            status, err = 200, handle_event(json.loads(evt.get("body", "{}")))
    except:
        traceback.print_exc()
        status, err = 500, "Runtime error"
    print(f"Status: {status}\nError: {err}")
    return {"statusCode": status, "body": err or "No error"}


def handle_event(payload):
    """Handle a GitLab event."""
    print("Payload:", json.dumps(payload, indent=2))
    if get_in(payload, "object_attributes", "author_id") != registrator:
        return "MR not created by Registrator"
    if payload.get("event_type") != "merge_request":
        return "Skipping event"
    a = get_in(payload, "object_attributes", "action")
    if a == "open":
        return handle_open(payload)
    if a == "merge":
        return handle_merge(payload)
    return "Unknown or missing action"


def handle_open(payload):
    """Handle a merge request open event."""
    if not merge:
        return "Automatic merging is disabled"
    if get_in(payload, "changes", "iid", "previous") is not None:
        return "Not a new MR"
    p_id = get_in(payload, "object_attributes", "source_project_id")
    p = client.projects.get(p_id, lazy=True)
    mr_id = get_in(payload, "changes", "iid", "current")
    mr = p.mergerequests.get(mr_id, lazy=True)
    print("Approving and merging MR")
    mr.approve()
    mr.merge(merge_when_pipeline_succeeds=True)


def handle_merge(payload):
    """Handle a merge request merge event."""
    if get_in(payload, "changes", "state", "previous") == "merged":
        return "MR was previously merged"
    if get_in(payload, "changes", "state", "current") != "merged":
        return "MR is not merged"
    target = get_in(payload, "object_attributes", "target_branch")
    default = get_in(payload, "object_attributes", "target", "default_branch")
    if target != default:
        return "Target branch is not the default"
    body = get_in(payload, "object_attributes", "description")
    print(f"MR body:\n{body}")
    m = re_repo.search(body)
    if not m:
        return "No repo match"
    repo = m[1].strip()
    m = re_version.search(body)
    if not m:
        return "No version match"
    version = m[1].strip()
    m = re_commit.search(body)
    if not m:
        return "No commit match"
    commit = m[1].strip()
    p = client.projects.get(repo, lazy=True)
    print(f"Creating tag {version} for {repo} at {commit}")
    p.tags.create({"tag_name": version, "ref": commit})


def get_in(d, *keys, default=None):
    """Get a nested value from a dict."""
    for k in keys:
        if k not in d:
            return default
        d = d[k]
    return d
