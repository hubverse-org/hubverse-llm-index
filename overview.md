# Hubverse overview

The hubverse is a set of open-source software and data standards for collaborative modeling hubs. It is developed by the Consortium of Infectious Disease Modeling Hubs. Public health agencies use it to run forecasting and scenario modeling exercises, among them US CDC FluSight and the European CDC RespiCast and RespiCompass hubs. The concepts are not specific to infectious disease.

- Landing page: <https://hubverse.io/>
- Technical documentation: <https://docs.hubverse.io/>
- GitHub organisation: <https://github.com/hubverse-org>
- R packages (R-universe): <https://hubverse-org.r-universe.dev/>
- Mailing list and monthly community meetings: <https://groups.io/g/hubverse>
- Full index of every page and repository: [llms.txt](llms.txt)

## Core concepts

A **hub** is a repository, usually on GitHub, that collects predictions from several modeling teams in one standard format.

- **Hub configuration** (`hub-config/`) holds three JSON files. `admin.json` describes the hub. `tasks.json` defines what teams are asked to predict. `model-metadata-schema.json` defines what teams must say about their models. Each file is validated against the [hubverse schemas](https://github.com/hubverse-org/schemas). Docs: [hub configuration](https://docs.hubverse.io/en/latest/user-guide/hub-config.html).
- **Modeling tasks** are defined in `tasks.json` as **rounds**. Each round lists **task IDs** (for example location, target, horizon, reference date) and the values they may take. Docs: [defining modeling tasks](https://docs.hubverse.io/en/latest/user-guide/tasks.html).
- **Output types** describe how a prediction is expressed: `mean`, `median`, `quantile`, `cdf`, `pmf` and `sample`. Docs: [model output](https://docs.hubverse.io/en/latest/user-guide/model-output.html), [sample output type](https://docs.hubverse.io/en/latest/user-guide/sample-output-type.html).
- **Model output** (`model-output/`) holds one file per team, model and round, in CSV or Parquet.
- **Model metadata** (`model-metadata/`) holds one YAML file per model.
- **Target data** (`target-data/`) holds the observed values. It comes in two forms: time series, and oracle output, which is expressed like model output so predictions can be scored against it. Docs: [target data](https://docs.hubverse.io/en/latest/user-guide/target-data.html).
- Terminology: [docs.hubverse.io terminology](https://docs.hubverse.io/en/latest/overview/terminology.html), [hubverse.io terminology](https://hubverse.io/terminology.html).

## How the pieces fit

1. **Set up a hub.** Start from [hubTemplate](https://github.com/hubverse-org/hubTemplate) or one of the [example hubs](#examples), write the configuration with [hubAdmin](https://hubverse-org.github.io/hubAdmin/), and validate it against the [schemas](https://github.com/hubverse-org/schemas). Quickstart: [hub administration](https://docs.hubverse.io/en/latest/quickstart-hub-admin/intro.html).
2. **Accept submissions.** Teams open pull requests. [hubverse-actions](https://github.com/hubverse-org/hubverse-actions) runs [hubValidations](https://hubverse-org.github.io/hubValidations/) on each one. [hubCI](https://hubverse-org.github.io/hubCI/) installs these workflows in a hub, together with a Dependabot configuration that keeps their actions up to date.
3. **Store and mirror.** Hub data can be mirrored to AWS S3 and converted to Parquet. This uses [hubverse-infrastructure](https://github.com/hubverse-org/hubverse-infrastructure) and [hubverse-transform](https://github.com/hubverse-org/hubverse-transform). Docs: [data storage](https://docs.hubverse.io/en/latest/user-guide/data-storage.html).
4. **Access data.** [hubData](https://hubverse-org.github.io/hubData/) (R) and [hub-data](https://hubverse-org.github.io/hub-data/) (Python) read model output and target data from local or cloud hubs. [hubUtils](https://hubverse-org.github.io/hubUtils/) provides shared utilities.
5. **Combine, score and plot.** [hubEnsembles](https://hubverse-org.github.io/hubEnsembles/dev/) builds ensembles. [hubEvals](https://hubverse-org.github.io/hubEvals/) scores predictions and builds on [scoringutils](https://github.com/epiforecasts/scoringutils). [hubVis](https://hubverse-org.github.io/hubVis/dev/) plots model output.
6. **Publish a dashboard.** A hub dashboard is created from [hub-dashboard-template](https://github.com/hubverse-org/hub-dashboard-template). It combines a forecast view ([predtimechart](https://github.com/reichlab/predtimechart), via [hub-dashboard-predtimechart](https://github.com/hubverse-org/hub-dashboard-predtimechart)), an evaluation view ([predevals](https://github.com/hubverse-org/predevals), with scores from [hubPredEvalsData](https://hubverse-org.github.io/hubPredEvalsData/)) and a Quarto site ([hub-dash-site-builder](https://github.com/hubverse-org/hub-dash-site-builder)). [hub-dashboard-control-room](https://github.com/hubverse-org/hub-dashboard-control-room) runs the builds for registered dashboards. Docs: [dashboards](https://docs.hubverse.io/en/latest/user-guide/dashboards.html), [dashboard template guide](https://hubverse-org.github.io/hub-dashboard-template/), [dashboard tools](https://docs.hubverse.io/en/latest/developer/dashboard-tools.html).

The [hubverse](https://github.com/hubverse-org/hubverse) R meta-package installs and loads the core R packages together.

## Examples

- **Example hubs.** [example-simple-forecast-hub](https://github.com/hubverse-org/example-simple-forecast-hub), [example-complex-forecast-hub](https://github.com/hubverse-org/example-complex-forecast-hub) and [example-complex-scenario-hub](https://github.com/hubverse-org/example-complex-scenario-hub) are complete hubs used throughout the documentation. [hubTemplate](https://github.com/hubverse-org/hubTemplate) is an empty hub to start from.
- **Example data.** [hubExamples](https://hubverse-org.github.io/hubExamples/) is an R package with model output and target data for an example forecast hub and an example scenario hub. Package examples and tests use it.
- **Example dashboards.** The [FluSight dashboard](https://reichlab.io/flusight-dashboard) ([source](https://github.com/reichlab/flusight-dashboard)) and the [COVID-19 Forecast Hub dashboard](https://reichlab.io/covidhub-dashboard) are live dashboards built from hub-dashboard-template. [dashboard-test-hub](https://github.com/hubverse-org/dashboard-test-hub) and [dashboard-test-hub-dashboard](https://github.com/hubverse-org/dashboard-test-hub-dashboard) are a paired hub and dashboard for developing the dashboard pipeline.
- **Test hubs.** The `ci-testhub-*` repositories are fixtures for CI. [llms.txt](llms.txt) lists them.

## Audiences

| Role | Start here |
|------|------------|
| Hub administrator | [Create a hub](https://hubverse.io/quickstart/create.html), [hub administration quickstart](https://docs.hubverse.io/en/latest/quickstart-hub-admin/intro.html) |
| Modeler submitting output | [Submit model output](https://hubverse.io/quickstart/submit.html), [model output format](https://docs.hubverse.io/en/latest/user-guide/model-output.html) |
| Analyst | [Analyze data](https://hubverse.io/quickstart/analyze.html), [hubData](https://hubverse-org.github.io/hubData/) |
| Developer | [Develop software](https://hubverse.io/quickstart/develop.html), [developer guide](https://docs.hubverse.io/en/latest/developer/index.html) |

## Versioning

Hub configuration files declare the schema version they follow. docs.hubverse.io documents one schema release at a time, and hubDocs release numbers match the schema release they track. Development practice, release processes and security policies are in the [developer guide](https://docs.hubverse.io/en/latest/developer/index.html).

## Getting help

- Problems with a tool: file an issue in that tool's repository. [catalog/repos.json](catalog/repos.json) lists every repository with its issues URL.
- Problems with the documentation: <https://github.com/hubverse-org/hubDocs/issues>.
- Everything else: [contact](https://docs.hubverse.io/en/latest/overview/contact.html).
