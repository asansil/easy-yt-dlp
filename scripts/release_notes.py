"""Release helpers used by .github/workflows/release.yml.

python scripts/release_notes.py check-tag v2.0.0-beta.1   # tag must match pyproject
python scripts/release_notes.py notes v2.0.0-beta.1       # print the CHANGELOG section
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from easy_ytdlp.updater.versions import Version  # noqa: E402


def project_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def check_tag(tag: str) -> int:
    if Version(tag) != Version(project_version()):
        print(f"Tag {tag} does not match pyproject version {project_version()}", file=sys.stderr)
        return 1
    print(f"Tag {tag} matches version {project_version()}")
    return 0


def notes(tag: str) -> int:
    """Print the CHANGELOG section of ``tag`` (e.g. "## [2.0.0b1]"), or [Unreleased]."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version = Version(tag)
    headings = {version.pep440(), tag.lstrip("v"), "Unreleased"}
    sections = re.split(r"(?m)^## ", text)
    for wanted in (version.pep440(), tag.lstrip("v"), "Unreleased"):
        for section in sections:
            title = section.split("\n", 1)[0]
            match = re.match(r"\[([^\]]+)\]", title)
            if match and match.group(1) == wanted and match.group(1) in headings:
                body = section.split("\n", 1)[1] if "\n" in section else ""
                # Drop empty "### Fixed" style headings.
                body = re.sub(r"(?m)^### [^\n]+\n(?=\s*(?:### |\Z))", "", body)
                print(body.strip())
                return 0
    print(f"No CHANGELOG section for {tag}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in {"check-tag", "notes"}:
        print(__doc__)
        sys.exit(2)
    sys.exit(check_tag(sys.argv[2]) if sys.argv[1] == "check-tag" else notes(sys.argv[2]))
