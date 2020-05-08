from pathlib import Path


def get_version_number():
    # This file must exist in the root of the module, as the following code
    # tries to find the module root so that it can find the VERSION file.
    # project_root/
    #  - module/
    #    - VERSION
    #    - version.py
    root_dir = Path(__file__).parent
    version = "-1.-1.-1"

    with (root_dir / "VERSION").open() as version_file:
        version = version_file.read().strip()

    return version


__version__ = get_version_number()
