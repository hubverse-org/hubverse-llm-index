#!/usr/bin/env python3
"""Build the hubverse knowledge base index.

Lists every repository in the GitHub org, finds each documentation site
and its llms.txt, enumerates the pages those sites publish, collects every
link the pages contain, and writes:

  llms.txt               entry point in llmstxt.org format
  catalog/repos.json     one record per org repository
  catalog/related.json   software the hubverse builds on, and R packages
                         that build on the hubverse
  catalog/sources.json   one record per documentation page
  catalog/domains.txt    every domain linked from the documentation
  catalog/links.txt      every external URL linked from the documentation

Standard library only. Requires Python 3.11 or later (tomllib).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "hubverse-llm-index-builder"
API = "https://api.github.com"
R_UNIVERSE_API = "https://r-universe.dev/api"
HARD_DEPENDENCIES = {"Depends", "Imports", "LinkingTo"}
DOCS_SITE = "https://docs.hubverse.io/en/latest/"
LANDING_SITE = "https://hubverse.io/"
URL_RE = re.compile(r"https?://[^\s<>\"'`)\]}]+")
HREF_RE = re.compile(r"""href=["']([^"'#]+)""")
MD_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
TITLE_MD_RE = re.compile(r"^(?:#\s+(.+)|(\S.*)\n[=]{3,})$", re.MULTILINE)
TITLE_HTML_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
HOST_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
IGNORED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "example.com"}


def fetch(url: str, token: str | None = None) -> tuple[int, str]:
    headers = {"User-Agent": USER_AGENT}
    if token and url.startswith(API):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return 0, ""


def fetch_json(url: str, token: str | None) -> object:
    status, text = fetch(url, token)
    if status != 200:
        sys.exit(f"GitHub API request failed ({status}): {url}")
    return json.loads(text)


def list_repos(org: str, token: str | None) -> list[dict]:
    repos, page = [], 1
    while True:
        batch = fetch_json(
            f"{API}/orgs/{org}/repos?per_page=100&type=public&page={page}",
            token,
        )
        repos.extend(batch)
        if len(batch) < 100:
            return sorted(repos, key=lambda r: r["name"].lower())
        page += 1


def site_base(url: str) -> str:
    """Directory URL of a site, with any index.html removed."""
    url = re.sub(r"index\.html?$", "", url)
    return url if url.endswith("/") else url + "/"


def docs_candidates(repo: dict) -> list[str]:
    """Possible documentation sites of a GitHub repository."""
    bases = []
    if repo.get("homepage"):
        bases.append(site_base(repo["homepage"]))
    owner = repo["owner"]["login"].lower()
    pages_base = f"https://{owner}.github.io/{repo['name']}/"
    if repo.get("has_pages") and pages_base not in bases:
        bases.append(pages_base)
    return bases


def find_docs(bases: list[str]) -> tuple[str | None, str | None]:
    """Return the documentation URL and llms.txt URL of the first site found.

    Note that some pkgdown sites only publish the development build, under
    dev/, so dev/llms.txt is tried as well as llms.txt.
    """
    for base in bases:
        for candidate in (base, urljoin(base, "../")):
            for path in ("llms.txt", "dev/llms.txt"):
                url = urljoin(candidate, path)
                if fetch(url)[0] == 200:
                    return base, url
    docs = next((b for b in bases if fetch(b)[0] == 200), None)
    return docs, None


def category_lookup(config: dict) -> dict[str, str]:
    return {
        repo: category["key"]
        for category in config["category"]
        for repo in category["repos"]
    }


def repo_record(repo: dict, org: str, categories: dict[str, str]) -> dict:
    docs, llms = find_docs(docs_candidates(repo))
    branch = repo["default_branch"]
    return {
        "name": repo["name"],
        "description": repo.get("description") or "",
        "category": categories.get(repo["name"], "uncategorised"),
        "archived": repo["archived"],
        "language": repo.get("language"),
        "topics": sorted(repo.get("topics") or []),
        "repo_url": repo["html_url"],
        "issues_url": f"{repo['html_url']}/issues",
        "readme_raw_url": (
            f"https://raw.githubusercontent.com/{org}/{repo['name']}"
            f"/{branch}/README.md"
        ),
        "default_branch": branch,
        "docs_url": docs,
        "llms_txt_url": llms,
    }


def github_repo(full_name: str, token: str | None) -> dict | None:
    status, text = fetch(f"{API}/repos/{full_name}", token)
    return json.loads(text) if status == 200 else None


def dependency_record(entry: dict, token: str | None) -> dict:
    """A package from the `external` list in categories.toml."""
    repo = github_repo(entry["repo"], token)
    if "docs" in entry:
        bases = [site_base(entry["docs"])]
    else:
        bases = docs_candidates(repo) if repo else []
    docs, llms = find_docs(bases)
    return {
        "name": entry["name"],
        "summary": entry["summary"],
        "repo_url": f"https://github.com/{entry['repo']}",
        "docs_url": docs,
        "llms_txt_url": llms,
    }


def org_r_packages(org: str) -> set[str]:
    status, text = fetch(
        f"https://{org.lower()}.r-universe.dev/api/packages?fields=Package")
    return {p["Package"] for p in json.loads(text)} if status == 200 else set()


def dependent_record(
    name: str, user: str, packages: set[str], token: str | None,
) -> dict | None:
    """An R package outside the org that imports a hubverse package.

    Returns None when the package depends on the hubverse only through
    another package.
    """
    status, text = fetch(f"https://{user}.r-universe.dev/api/packages/{name}")
    if status != 200:
        return None
    description = json.loads(text)
    uses = sorted(
        d["package"] for d in description.get("_dependencies", [])
        if d["role"] in HARD_DEPENDENCIES and d["package"] in packages
    )
    if not uses:
        return None
    remote = description.get("RemoteUrl") or ""
    repo = None
    if urlparse(remote).hostname == "github.com":
        repo = github_repo(urlparse(remote).path.strip("/"), token)
    docs, llms = find_docs(docs_candidates(repo) if repo else [])
    return {
        "name": name,
        "title": " ".join(description.get("Title", "").split()),
        "uses": uses,
        "repo_url": repo["html_url"] if repo else remote or None,
        "docs_url": docs or f"https://{user}.r-universe.dev/{name}",
        "llms_txt_url": llms,
    }


def r_dependents(org: str, token: str | None) -> list[dict]:
    """R packages outside the org that import hubverse packages.

    R-universe indexes CRAN and every other universe. Its `needs:` search
    follows hard dependencies recursively, so each match is checked against
    its own DESCRIPTION by dependent_record().
    """
    packages = org_r_packages(org)
    found: dict[str, str] = {}
    for package in sorted(packages):
        status, text = fetch(
            f"{R_UNIVERSE_API}/search?q=needs:{package}&limit=500")
        if status != 200:
            continue
        for hit in json.loads(text)["results"]:
            # Note that other universes can hold copies of hubverse packages.
            if hit["_user"].lower() == org.lower() or hit["Package"] in packages:
                continue
            found.setdefault(hit["Package"], hit["_user"])
    records = [
        dependent_record(name, user, packages, token)
        for name, user in sorted(found.items())
    ]
    return [r for r in records if r]


def markdown_pages(org: str, entry: dict, token: str | None) -> list[dict]:
    """Markdown files of a repository named in the `markdown` list.

    Each page links to its raw Markdown on GitHub. Note that Read the Docs
    does not publish page sources for docs.hubverse.io, so this is how its
    pages are indexed too. Returns no pages if the repository is not in the
    org.
    """
    repo = github_repo(f"{org}/{entry['repo']}", token)
    if not repo:
        return []
    branch = repo["default_branch"]
    tree = fetch_json(
        f"{API}/repos/{org}/{entry['repo']}/git/trees/{branch}?recursive=1",
        token,
    )
    root = entry.get("root", "")
    include = tuple(entry.get("include", [""]))
    exclude = tuple(entry.get("exclude", []))
    pages = []
    for item in tree["tree"]:
        path = item["path"]
        if not (path.startswith(root) and path.endswith(".md")):
            continue
        rel = path[len(root):]
        if not rel.startswith(include) or (exclude and rel.startswith(exclude)):
            continue
        if "rendered" in entry:
            url = entry["rendered"] + rel[:-3] + ".html"
        else:
            url = f"{repo['html_url']}/blob/{branch}/{path}"
        pages.append({
            "site": entry["site"],
            "url": url,
            "markdown_url": (
                f"https://raw.githubusercontent.com/{org}/{entry['repo']}"
                f"/{branch}/{path}"
            ),
            "section": rel.split("/")[0] if "/" in rel else "home",
        })
    return pages


def landing_pages() -> list[dict]:
    status, text = fetch(urljoin(LANDING_SITE, "sitemap.xml"))
    if status != 200:
        return []
    return [
        {"site": "hubverse.io", "url": url, "markdown_url": None,
         "section": "hubverse.io"}
        for url in sorted(set(re.findall(r"<loc>([^<]+)</loc>", text)))
    ]


def pkgdown_pages(record: dict, llms_text: str) -> list[dict]:
    """Pages a package site lists in its llms.txt."""
    base = site_base(record["docs_url"] or record["llms_txt_url"])
    base_host = urlparse(base).netloc + urlparse(base).path.split("/dev/")[0]
    llms_base = site_base(record["llms_txt_url"].rsplit("/", 1)[0])
    candidates = URL_RE.findall(llms_text) + [
        urljoin(llms_base, href) for href in MD_LINK_RE.findall(llms_text)
    ]
    pages = set()
    for url in candidates:
        url = url.rstrip(".,;:")
        parsed = urlparse(url)
        if url.endswith(".md") and (parsed.netloc + parsed.path).startswith(
            base_host
        ):
            pages.add(url)
    return [
        {"site": record["name"], "url": url, "markdown_url": url,
         "section": urlparse(url).path.rstrip("/").split("/")[-2]}
        for url in sorted(pages)
    ]


def extract_links(text: str, base: str | None = None) -> set[str]:
    links = {u.rstrip(".,;:") for u in URL_RE.findall(text)}
    if base:
        links |= {
            urljoin(base, href) for href in HREF_RE.findall(text)
            if not href.startswith(("mailto:", "javascript:"))
        }
    return {
        u for u in links
        if HOST_RE.match(urlparse(u).hostname or "")
        and urlparse(u).hostname not in IGNORED_HOSTS
    }


def page_title(text: str) -> str | None:
    match = TITLE_MD_RE.search(text)
    if match:
        return (match.group(1) or match.group(2)).strip()
    match = TITLE_HTML_RE.search(text)
    if not match:
        return None
    title = html.unescape(match.group(1)).replace("\xa0", " ")
    return title.removesuffix(" – hubverse").strip()


def is_internal(url: str, org: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return (
        host.endswith("hubverse.io")
        or host == f"{org.lower()}.github.io"
        or host == f"{org.lower()}.r-universe.dev"
        or (host in {"github.com", "raw.githubusercontent.com"}
            and parsed.path.lower().startswith(f"/{org.lower()}/"))
    )


def render_llms_txt(
    config: dict, repos: list[dict], related: dict, sources: list[dict],
    kb_base: str,
) -> str:
    by_name = {r["name"]: r for r in repos}
    lines = [
        "# hubverse",
        "",
        "> The hubverse is a set of open-source software and data standards "
        "for collaborative modeling hubs: repositories where teams submit "
        "forecasts or scenario projections in a shared format, which are "
        "then validated, stored, ensembled, evaluated and visualised. It is "
        "developed by the Consortium of Infectious Disease Modeling Hubs.",
        "",
        "This file indexes everything the hubverse publishes. Start with the "
        "overview. Each R package site has its own llms.txt that lists every "
        "reference page and vignette as Markdown. catalog/repos.json and "
        "catalog/sources.json hold the same information in machine-readable "
        "form, and catalog/domains.txt lists every domain the documentation "
        "links to.",
        "",
        "## Overview",
        "",
        f"- [Hubverse overview]({kb_base}overview.md): concepts, architecture "
        "and which repository does what",
        f"- [hubverse.io]({LANDING_SITE}): public landing page, quickstarts "
        "by role, community",
        f"- [docs.hubverse.io]({DOCS_SITE}): technical documentation for hub "
        "administrators, modelers and developers",
        "- [Mailing list and community meetings](https://groups.io/g/hubverse)",
        "",
    ]
    for entry in config.get("markdown", []):
        pages = sorted(
            (s for s in sources if s["site"] == entry["site"]),
            key=lambda s: s["url"],
        )
        if not pages:
            continue
        lines += [f"## {entry['title']}", ""]
        if entry.get("summary"):
            lines += [entry["summary"], ""]
        for page in pages:
            title = page.get("title") or page["url"].rsplit("/", 1)[-1]
            lines.append(
                f"- [{title}]({page['markdown_url']}): {page['section']}, "
                f"rendered at {page['url']}"
            )
        lines.append("")
    lines += ["## hubverse.io pages", ""]
    for page in (s for s in sources if s["site"] == "hubverse.io"):
        title = page.get("title") or page["url"]
        lines.append(f"- [{title}]({page['url']})")
    lines.append("")

    def repo_line(record: dict) -> str:
        description = " ".join(record["description"].split()).rstrip(".")
        parts = [description] if description else []
        if record["llms_txt_url"]:
            parts.append(f"page index: {record['llms_txt_url']}")
        elif record["docs_url"]:
            parts.append(f"docs: {record['docs_url']}")
        else:
            parts.append(f"README: {record['readme_raw_url']}")
        if record["archived"]:
            parts.append("archived")
        return f"- [{record['name']}]({record['repo_url']}): " + "; ".join(
            parts)

    listed = set()
    optional = []
    for category in config["category"]:
        block = [f"## {category['title']}", "", category["summary"], ""]
        for name in category["repos"]:
            if name in by_name:
                block.append(repo_line(by_name[name]))
                listed.add(name)
        block.append("")
        (optional if category.get("optional") else lines).extend(block)
    unlisted = [r for r in repos if r["name"] not in listed]
    if unlisted:
        lines += ["", "## Uncategorised", ""]
        lines += [repo_line(r) for r in unlisted]
    def related_line(record: dict, text: str) -> str:
        url = record["docs_url"] or record["repo_url"]
        parts = [text.rstrip(".")]
        if record["llms_txt_url"]:
            parts.append(f"page index: {record['llms_txt_url']}")
        return f"- [{record['name']}]({url}): " + "; ".join(parts)

    lines += ["", "## Software the hubverse builds on", ""]
    lines += [related_line(r, r["summary"]) for r in related["dependencies"]]
    if related["dependents"]:
        lines += [
            "", "## R packages that build on the hubverse", "",
            "Packages outside hubverse-org, on CRAN or R-universe, that "
            "import hubverse packages.", "",
        ]
        lines += [
            related_line(r, f"{r['title']}. Uses {', '.join(r['uses'])}")
            for r in related["dependents"]
        ]
    lines += [
        "",
        "## Optional",
        "",
        f"- [Repository catalog]({kb_base}catalog/repos.json)",
        f"- [Related software catalog]({kb_base}catalog/related.json)",
        f"- [Documentation page catalog]({kb_base}catalog/sources.json)",
        f"- [Linked domains]({kb_base}catalog/domains.txt)",
        f"- [Linked external URLs]({kb_base}catalog/links.txt)",
        "",
    ]
    lines += optional
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", default="hubverse-org")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
        help="GitHub token; raises the API rate limit (default: "
             "$GITHUB_TOKEN or $GH_TOKEN)",
    )
    parser.add_argument(
        "--depth", type=int, choices=(1, 2), default=2,
        help="1: links in site indexes only; 2: also links in every page",
    )
    parser.add_argument(
        "--kb-base",
        default="https://raw.githubusercontent.com/hubverse-org/hubverse-llm-index"
                "/main/",
        help="URL the knowledge base files are served from",
    )
    parser.add_argument("--out", type=Path, default=ROOT)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    config = tomllib.loads(
        (args.out / "catalog" / "categories.toml").read_text())
    categories = category_lookup(config)

    print(f"Listing {args.org} repositories", file=sys.stderr)
    raw_repos = list_repos(args.org, args.token)
    with ThreadPoolExecutor(args.workers) as pool:
        repos = list(pool.map(
            lambda r: repo_record(r, args.org, categories), raw_repos))
    print(f"  {len(repos)} repositories, "
          f"{sum(bool(r['llms_txt_url']) for r in repos)} with llms.txt",
          file=sys.stderr)

    with ThreadPoolExecutor(args.workers) as pool:
        dependencies = list(pool.map(
            lambda e: dependency_record(e, args.token),
            config.get("external", [])))
    related = {
        "dependencies": dependencies,
        "dependents": r_dependents(args.org, args.token),
    }
    print(f"  {len(related['dependencies'])} dependencies, "
          f"{len(related['dependents'])} R packages that build on the "
          "hubverse", file=sys.stderr)

    links: set[str] = set()
    sources = []
    for entry in config.get("markdown", []):
        sources += markdown_pages(args.org, entry, args.token)
    titled_sites = {e["site"] for e in config.get("markdown", [])}
    titled_sites.add("hubverse.io")
    sources += landing_pages()
    with ThreadPoolExecutor(args.workers) as pool:
        indexed = [r for r in repos if r["llms_txt_url"]]
        for record, (_, text) in zip(indexed, pool.map(
                lambda r: fetch(r["llms_txt_url"]), indexed)):
            sources += pkgdown_pages(record, text)
            links |= extract_links(text)
    print(f"  {len(sources)} documentation pages", file=sys.stderr)

    # Page titles are needed for every page listed individually in llms.txt.
    # Package pages are fetched only to collect their links.
    to_fetch = [
        s for s in sources
        if args.depth == 2 or s["site"] in titled_sites
    ]
    with ThreadPoolExecutor(args.workers) as pool:
        results = pool.map(
            lambda s: fetch(s["markdown_url"] or s["url"]), to_fetch)
        for source, (status, text) in zip(to_fetch, results):
            source["status"] = status
            if status != 200:
                continue
            if source["site"] in titled_sites:
                source["title"] = page_title(text)
            links |= extract_links(text, base=source["url"])
    broken = [s["url"] for s in to_fetch if s.get("status") != 200]

    external = sorted(u for u in links if not is_internal(u, args.org))
    domains = Counter(urlparse(u).hostname for u in links)

    catalog = args.out / "catalog"
    (catalog / "repos.json").write_text(json.dumps(repos, indent=2) + "\n")
    (catalog / "related.json").write_text(
        json.dumps(related, indent=2) + "\n")
    for s in sources:
        s.pop("status", None)
    sources.sort(key=lambda s: (s["site"], s["url"]))
    (catalog / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    (catalog / "links.txt").write_text("\n".join(external) + "\n")
    (catalog / "domains.txt").write_text("".join(
        f"{host}\t{count}\n"
        for host, count in sorted(domains.items(), key=lambda kv: kv[0])
    ))
    (args.out / "llms.txt").write_text(
        render_llms_txt(config, repos, related, sources, args.kb_base))

    print(f"  {len(external)} external links across {len(domains)} domains",
          file=sys.stderr)
    if broken:
        print(f"  {len(broken)} pages could not be fetched:", file=sys.stderr)
        for url in broken:
            print(f"    {url}", file=sys.stderr)


if __name__ == "__main__":
    main()
