# Contributing

See the [WLAN Pi developer documentation](https://github.com/WLAN-Pi/developers) for contribution guidelines, workflow, branch naming, commit standards, and style guides.

## wlanpi-webui Specific

### Pull Requests

Before submitting a PR:

1. Lint your code with `tox -e lint` and make sure it passes the flake8 checks.
2. Format your code with `tox -e format` (runs autoflake, black, and isort).
3. (Optional but encouraged) Create a test in `/tests` that validates your changes.
4. (Optional but encouraged) Ensure tests pass by running `tox`.

Failure to lint and format will cause CI to fail and slow review.

## Code of Conduct

See the [WLAN Pi Code of Conduct](https://github.com/WLAN-Pi/.github/blob/main/docs/code_of_conduct.md).
