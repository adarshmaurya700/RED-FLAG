"""Publish only the validated catalogue tree, without touching application files."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.models.source_findings import SourceCatalog

BRANCH = "refs/heads/codex/source-data"


def git(*args, input=None):
    return subprocess.run(
        ["git", *args], input=input, text=True, check=True, capture_output=True
    ).stdout.strip()


if __name__ == "__main__":
    catalog_path = Path(sys.argv[1])
    SourceCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    parent = []
    if git("ls-remote", "origin", BRANCH):
        git("fetch", "origin", BRANCH)
        parent = ["-p", git("rev-parse", "FETCH_HEAD")]
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    blob = git("hash-object", "-w", str(catalog_path))
    tree = git("mktree", input=f"100644 blob {blob}\tcatalog.json\n")
    commit = git(
        "commit-tree", tree, *parent, input="Refresh public source review catalogue\n"
    )
    git("push", "origin", f"{commit}:{BRANCH}")
    print(f"Published validated catalogue to codex/source-data ({commit[:12]})")
