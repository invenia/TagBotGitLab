import re

from tagbotgitlab.version import get_version_number


# Make sure version matches SemVar
def test_version_string():
    # Regex found here: https://github.com/k-bx/python-semver/blob/master/semver.py
    regex = (
        r"^(?P<major>(?:0|[1-9][0-9]*))\."
        r"(?P<minor>(?:0|[1-9][0-9]*))\."
        r"(?P<patch>(?:0|[1-9][0-9]*))"
        r"(\-(?P<prerelease>(?:0|[1-9A-Za-z-][0-9A-Za-z-]*)"
        r"(\.(?:0|[1-9A-Za-z-][0-9A-Za-z-]*))*))?"
        r"(\+(?P<build>[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*))?$"
    )
    assert re.search(regex, get_version_number())
