# This file is intended for local testing when contributing to this repository
# Do not commit any changes
# You will need to generate a GitLab Personal Access Token to use this
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
mr = p.mergerequests.get("146", lazy=False)
print(mr)
