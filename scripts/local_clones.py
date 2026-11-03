#!/usr/bin/env python3
"""Map local git clones to hubverse-org repositories.

Scans the immediate subdirectories of a workspace for git repositories
whose origin is in the org, and writes local/clones.md. The output is
specific to one machine, so local/ is not committed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def origin(path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(path), "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def repo_name(url: str, orgs: list[str]) -> str | None:
    pattern = "|".join(re.escape(org) for org in orgs)
    match = re.search(
        rf"github\.com[:/](?:{pattern})/([^/]+?)(?:\.git)?/?$", url, re.I)
    return match.group(1) if match else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workspace", type=Path)
    parser.add_argument(
        "--orgs", nargs="+",
        default=["hubverse-org", "Infectious-Disease-Modeling-Hubs"],
        help="org names to match; the second is the org's former name, "
             "which older clones still use as their origin",
    )
    parser.add_argument("--out", type=Path, default=ROOT / "local")
    args = parser.parse_args()

    catalog = json.loads((ROOT / "catalog" / "repos.json").read_text())
    known = {r["name"].lower(): r["name"] for r in catalog}
    workspace = args.workspace.expanduser().resolve()

    clones, other = {}, []
    for path in sorted(p for p in workspace.iterdir() if (p / ".git").exists()):
        url = origin(path)
        name = repo_name(url, args.orgs) if url else None
        if name and name.lower() in known:
            clones.setdefault(known[name.lower()], []).append(path)
        else:
            other.append((path, url))

    lines = [f"# Local clones under {workspace}", "", "| Repository | Local path |",
             "|---|---|"]
    for record in catalog:
        paths = clones.get(record["name"], [])
        cell = "<br>".join(f"`{p}`" for p in paths) if paths else "not cloned"
        lines.append(f"| [{record['name']}]({record['repo_url']}) | {cell} |")
    lines += ["", "## Other git repositories", "", "| Local path | Origin |",
              "|---|---|"]
    lines += [f"| `{p}` | {u or 'no origin'} |" for p, u in other]

    args.out.mkdir(exist_ok=True)
    (args.out / "clones.md").write_text("\n".join(lines) + "\n")
    print(args.out / "clones.md")


if __name__ == "__main__":
    main()
