# This file is intended for local testing when contributing to this repository
# Do not committ any changes
# You will need to generate a Gitlab Personal Access Token to use this
import os
from os import environ as env

import gitlab
from tagbotgitlab.changelog import Changelog


# Set some environment variables required for import.
env["GITLAB_URL"] = "https://gitlab.invenia.ca"
env["GITLAB_API_TOKEN"] = "<the-personal-access-token-you-created>"


client = gitlab.Gitlab(
    os.environ["GITLAB_URL"], private_token=os.environ["GITLAB_API_TOKEN"]
)

repo = "invenia/TestRepo.jl"

p = client.projects.get(repo, lazy=True)
changelog = Changelog(p)


tags = p.tags.list(all=False)
for tag in tags:
    commit = tag.commit["id"]
    version = tag.name

    release_notes = changelog.get(version, commit)
    print(release_notes)
    print("\n-----------------------------------------------------------------------\n")

    # Note the line below will actually set the release notes in the repository used
    # Should only be used if that is intended behaviour
    # tag.set_release_description(release_notes)
