import codecs
from os import path

from setuptools import find_packages, setup


TEST_DEPS = ["coverage", "pytest", "pytest-cov"]
DOCS_DEPS = ["sphinx", "sphinx-rtd-theme", "sphinx-autoapi", "recommonmark"]
CHECK_DEPS = ["isort", "flake8", "flake8-quotes", "pep8-naming", "mypy", "black"]
REQUIREMENTS = [
    "Jinja2>=2.10.3",
    "python-dateutil>=2.8.1",
    "python-gitlab>=1.8.0",
    "semver>=2.9.0",
]

EXTRAS = {
    "test": TEST_DEPS,
    "docs": DOCS_DEPS,
    "check": CHECK_DEPS,
    "dev": TEST_DEPS + DOCS_DEPS + CHECK_DEPS,
}

# Read in the version
with open(path.join(path.dirname(path.abspath(__file__)), "VERSION")) as version_file:
    version = version_file.read().strip()


setup(
    name="TagBotGitLab",
    version=version,
    description="Julia TagBot for GitLab",
    long_description=codecs.open("README.md", "r", "utf-8").read(),
    long_description_content_type="text/markdown",
    author="Invenia Technical Computing",
    url="https://github.com/invenia/TagBotGitLab",
    packages=find_packages(exclude=["tests"]),
    install_requires=REQUIREMENTS,
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.8",
    ],
    platforms=["any"],
    include_package_data=True,
    tests_require=TEST_DEPS,
    extras_require=EXTRAS,
)
