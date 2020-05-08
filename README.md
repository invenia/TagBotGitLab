# Julia TagBot for GitLab

[![Build Status](https://travis-ci.org/invenia/tagbotgitlab.svg?branch=master)](https://travis-ci.org/invenia/tagbotgitlab?branch=master)
[![Coverage Status](https://coveralls.io/repos/github/invenia/tagbotgitlab/badge.svg?branch=master)](https://coveralls.io/github/invenia/tagbotgitlab)
[![Python Version](https://img.shields.io/badge/python-3.7%20%7C%203.8-blue.svg)](https://www.python.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

A minimal clone of [TagBot](https://github.com/JuliaRegistries/TagBot) for registries hosted on GitLab.

Creates tags, releases, and changelogs when Julia packages are registered.

## License

tagbotgitlab is provided under an MIT License.

## Deployment

- Install the [Serverless Framework](https://serverless.com).
- Run `npm install`.
- Set the following environment variables:
  - `GITLAB_URL`: The base URL of your GitLab instance (not its API).
  - `GITLAB_API_TOKEN`: A GitLab API access token.
    It should have write access to all repositories that you want to create tags on.
  - `GITLAB_WEBHOOK_TOKEN`: A secure secret that you have generated.
  - `REGISTRATOR_ID`: The ID of the user making Registrator merge requests.
  - `AUTOMATIC_MERGE`: Set to `true` to enable automatic merge of merge requests.
    Enabling this feature requires the user to have Maintainer privileges on the registry, and for the "Prevent approval of merge requests by merge request author" repository setting to be disabled.
- Run `serverless deploy --stage prod` to deploy the API.
- Create a webhook on your registry repository.
  The URL should be the one that appeared after the last step.
  The secret token should be the one that you generated earlier.
  Only "Merge request events" should be enabled.

---

This code is tested on GitLab version `11.11.0-ee`.

### Changelogs

TagBotGitlab creates a changelog for each release based on the issues that have been closed and the merge requests that have been merged. Unlike [TagBot](https://github.com/JuliaRegistries/TagBot), TagBotGitLab currently does not support custom release notes or customizable templates.

Issues and pull requests with specified labels are not included in the changelog data.
By default, the following labels are ignored:

- changelog skip
- duplicate
- exclude from changelog
- invalid
- no changelog
- question
- wont fix

White-space, case, dashes, and underscores are ignored when comparing labels.
