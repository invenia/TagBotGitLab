# Julia TagBot for GitLab

[![CI](https://github.com/invenia/TagBotGitlab/workflows/CI/badge.svg)](https://github.com/invenia/TagBotGitlab/actions?query=workflow%3ACI)
[![Python Version](https://img.shields.io/badge/python-3.7%20%7C%203.8-blue.svg)](https://www.python.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

A minimal clone of [TagBot](https://github.com/JuliaRegistries/TagBot) for registries hosted on GitLab.

Automatically merges MRs, creates tags on the merge, and sets the corresponding release notes.
Our Julia packages are registered in a private Julia package registry hosted on a GitLab repository and the MRs that get automatically merged are made by [Registrator.jl](https://github.com/JuliaRegistries/Registrator.jl).
Each MR registers a new package or a new version of a Julia package.
Even though we host a private Registrator deployment, this can be used on any GitLab Julia package registry repository independently from where the MRs originate.

## Changelogs (Release Notes)

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

## Future Direction

This package is not uploaded to PyPI for now, but we hope to upload it eventually so that things like the `Changelog` can be used separately from the automatic merging of GitLab MRs.

The vision is to use only the `Changelog` on our prod repository when manual tags are made to populate the release notes automatically.

## Installation

To install this just install it into a virtualenv like so:

```
cd TagBotGitLab
python -m venv venv
. venv/bin/activate

pip install --upgrade pip
pip install -e .
```

## Deployment

To properly use this package you will likely want to deploy it to be used on a GitLab repository.
We use AWS but you can update the `serverless.yml` file to deploy on other platforms.

Steps:
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

## Contributing

This package uses the [python-gitlab](https://python-gitlab.readthedocs.io/en/stable/index.html) package to interact with GitLab and it's useful to refer to their documentation when making changes.
You can test using their API locally by generating a [Personal Access Token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html#creating-a-personal-access-token) and setting it in the `local_test.py` script included.

You can run tests locally by running in the virtualenv you installed the package in:
```
tox
```

## License

tagbotgitlab is provided under an MIT License.
