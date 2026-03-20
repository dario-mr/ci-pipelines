# CI Pipelines

This repository contains my shared [Dagger](https://docs.dagger.io/) CI pipelines, with only a thin
`GitHub Actions` wrapper to trigger them.

## How it works

Each repository has a small workflow file that simply calls the reusable workflow here, passing
required inputs (like image repository) and secrets.

The real CI logic — build, test, package, publish, etc. — lives in `Dagger` code in this repo.

## Workflows

- [build-and-push-java](.github/workflows/build-and-push-java.yml): Builds a java package and
  pushes its image to Docker Hub
    - tag rules:
        - `push` to `main`: `<pomVersion>`
        - `pull_request`: `<pomVersion>-<shortSha>`
- [build-and-push-node](.github/workflows/build-and-push-node.yml): Builds a Node frontend and
  pushes its image to Docker Hub
    - tag rules:
        - `push` to `main`: `<packageVersion>`
        - `pull_request`: `<packageVersion>-<shortSha>`
    - quality gates:
        - runs `npm run lint` when a `lint` script exists
        - runs `npm test` when a `test` script exists
        - runs `npm run test:e2e` when a `test:e2e` script exists
- [java-coverage](.github/workflows/java-coverage.yml): Generates a Java coverage summary for
  a pull request and posts/updates a PR comment
    - intended to be called from `pull_request` workflows
    - requires JaCoCo coverage XML in the caller repo

## Usage

```yaml
# Build and push (Java app)

jobs:
  build-and-push-java:
    uses: dario-mr/ci-pipelines/.github/workflows/build-and-push-java.yml@main
    with:
      image-repo: dariomr8/app
      # optional, comma-separated; defaults to linux/arm64
      platforms: linux/arm64,linux/amd64
    secrets:
      DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}
      DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}
```

```yaml
# Build and push (Node frontend)

jobs:
  build-and-push-node:
    uses: dario-mr/ci-pipelines/.github/workflows/build-and-push-node.yml@main
    with:
      image-repo: dariomr8/frontend-app
    secrets:
      DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}
      DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}
```

```yaml
# Coverage (PR comment)
jobs:
  coverage:
    uses: dario-mr/ci-pipelines/.github/workflows/java-coverage.yml@main
    with:
      pull-request-number: ${{ github.event.pull_request.number }}
```

## Updating Dagger

### Install Dagger locally

```bash
brew update
brew install dagger/tap/dagger
```

### Upgrade an existing local Dagger installation

Bump `engineVersion` in [dagger.json](dagger.json)
(see [Dagger release page](https://github.com/dagger/dagger/releases)), then run:

```bash
brew update
brew upgrade dagger/tap/dagger
dagger develop
```

Update the "setup dagger" action version
in [action.yml](.github/actions/setup-dagger/action.yml) to match [dagger.json](dagger.json).

## Verify Python syntax

From the repository root, you can sanity-check the Dagger Python module with:

```bash
python3 -m py_compile .dagger/src/ci/*.py
```
