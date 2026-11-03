# hubverse-llm-index

An index of everything the hubverse publishes: every repository in [hubverse-org](https://github.com/hubverse-org), every page of [docs.hubverse.io](https://docs.hubverse.io/) and [hubverse.io](https://hubverse.io/), every page of each package documentation site, and every external link those pages contain.

It is a context source for language model tools such as chatbots, agents and skills. It stores links, not copies, so the content it points to is always current.

## Contents

| File | Purpose |
|------|---------|
| [`llms.txt`](llms.txt) | Entry point in the [llms.txt](https://llmstxt.org/) format. Generated. |
| [`overview.md`](overview.md) | What the hubverse is, how the pieces fit together, where to start by role. Hand-written. |
| [`catalog/categories.toml`](catalog/categories.toml) | Grouping of repositories and related external repositories. Hand-written. |
| [`catalog/repos.json`](catalog/repos.json) | One record per org repository: description, category, repository, issues, README, docs and llms.txt URLs. Generated. |
| [`catalog/sources.json`](catalog/sources.json) | One record per documentation page, with a Markdown URL where one exists. Generated. |
| [`catalog/domains.txt`](catalog/domains.txt) | Every domain the documentation links to, with link counts. Generated. |
| [`catalog/links.txt`](catalog/links.txt) | Every external URL the documentation links to. Generated. |

## Using it

Point a tool at `llms.txt`:

```
https://raw.githubusercontent.com/hubverse-org/hubverse-llm-index/main/llms.txt
```

Each R package site publishes its own `llms.txt` that lists every reference page and article as Markdown. `llms.txt` here links to those, so a tool can go from the hubverse overview down to a single function's documentation in two hops. docs.hubverse.io does not publish Markdown, so its pages are linked to their Markdown source in hubDocs.

A harness that restricts which URLs a model may fetch can build its allowlist from `catalog/domains.txt`.

## Updating

`scripts/build.py` regenerates every generated file. It needs Python 3.11 or later and no other dependencies. A GitHub token is optional and raises the API rate limit.

```sh
GITHUB_TOKEN=$(gh auth token) python3 scripts/build.py
```

The `Refresh index` workflow runs the build weekly and opens a pull request when anything changed. A new repository appears under "Uncategorised" in `llms.txt` until it is added to `catalog/categories.toml`.

`scripts/local_clones.py <workspace>` maps the clones in a local workspace to the repositories in the catalog and writes `local/clones.md`, which is not committed.
