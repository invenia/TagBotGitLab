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
    os.environ["GITLAB_API_BASE"], private_token=os.environ["GITLAB_API_TOKEN"]
)


def main(evt, _ctx):
    """Lambda entrypoint."""
    try:
        if evt["headers"]["X-Gitlab-Token"] != token:
            status, err = 403, "Invalid token"
        else:
            status, err = 200, handle_event(json.loads(evt["body"]))
    except:
        traceback.print_exc()
        status, err = 500, "Runtime error"
    print(f"Status: {status}\nError: {err}")
    return {"statusCode": status, "body": err or "No error"}


def handle_event(payload):
    """Handle a GitLab event."""
    print("Payload:", json.dumps(payload, indent=2))
    if payload["object_attributes"]["author_id"] != registrator:
        return "MR not created by Registrator"
    if payload["event_type"] != "merge_request":
        return "Skipping event"
    a = payload["object_attributes"].get("action")
    if a == "open":
        return handle_open(payload)
    if a == "merge":
        return handle_merge(payload)
    return "Unknown or missing action"


def handle_open(payload):
    """Handle a merge request open event."""
    if not merge:
        return "Automatic merging is disabled"
    if payload["changes"]["iid"].get("previous") is not None:
        return "Not a new MR"
    p_id = payload["object_attributes"]["source_project_id"]
    p = client.projects.get(p1_id, lazy=True)
    mr_id = payload["changes"]["iid"]["current"]
    mr = p.mergerequests.get(mr_id, lazy=True)
    # mr.approve()
    # mr.merge(merge_when_pipeline_succeeds=True)


def handle_merge(payload):
    """Handle a merge request merge event."""
    if payload["changes"]["state"]["previous"] == "merged":
        return "MR was previously merged"
    if payload["changes"]["state"]["current"] != "merged":
        return "MR is not merged"
    target = payload["object_attributes"]["target_branch"]
    default = payload["object_attributes"]["target"]["default_branch"]
    if target != default:
        return "Target branch is not the default"
    body = payload["object_attributes"]["description"]
    print(f"MR body:\n{body}")
    m = re_repo.match(body)
    if not m:
        return "No repo match"
    repo = m[1]
    m = re_version.match(body)
    if not m:
        return "No version match"
    version = m[1]
    m = re_commit.match(body)
    if not m:
        return "No commit match"
    commit = m[1]
    print(f"Creating tag {version} for {repo} at {commit}")
    p = client.projects.get(repo, lazy=True)
    # p.tags.create({"tag_name": version, "ref": commit})
