# Julia TagBot for GitLab

[![Build Status](https://travis-ci.com/invenia/TagBotGitLab.svg?branch=master)](https://travis-ci.com/invenia/TagBotGitLab)

A minimal clone of [TagBot](https://github.com/JuliaRegistries/TagBot) for registries hosted on GitLab.

## Deployment

- Install the [Serverless Framework](https://serverless.com).
- Install the [Go compiler](https://golang.org/dl).
- Build the API by running `build.sh`.
- Set the following environment variables:
  - `GITLAB_API_BASE`: The base URL of your GitLab instance's API.
  - `GITLAB_API_TOKEN`: A GitLab API access token.
    It should have write access to all repositories that you want to create tags on.
  - `GITLAB_WEBHOOK_TOKEN`: A secure secret that you have generated.
- Run `serverless deploy --stage prod` to deploy the API.
- Create a webhook on your registry repository.
  The URL should be the one that appeared after the last step.
  The secret token should be the one that you generated earlier.
  Only "Merge request events" should be enabled.

---

This code is tested on GitLab version `11.10.4-ee`.
