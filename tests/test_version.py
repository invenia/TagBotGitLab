import re

from tagbotgitlab.version import get_version_number


# Make sure version matches SemVer
def test_version_string():
    # Regex found here: https://github.com/k-bx/python-semver/blob/master/semver.py
    regex = re.compile(
        r"""
    ^(?P<major>0|[1-9]\d*)\.
    (?P<minor>0|[1-9]\d*)\.
    (?P<patch>0|[1-9]\d*)
    (?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)
    (?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?
    (?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$
""",
        re.VERBOSE,
    )
    assert re.search(regex, get_version_number())
