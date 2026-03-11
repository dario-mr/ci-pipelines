# CI Pipelines

This repository contains my shared [Dagger](https://docs.dagger.io/) CI pipelines, with only a thin
`GitHub Actions` wrapper to trigger them.

## How it works

Each repository has a small workflow file that simply calls the reusable workflow here, passing
any required inputs (like image name) and secrets.

The real CI logic — build, test, package, publish, etc. — lives in `Dagger` code in this repo.

## Workflows

- [build-and-push](.github/workflows/build-and-push.yml): Builds a java package and
  pushes its image to Docker Hub
- [build-and-push-node](.github/workflows/build-and-push-node.yml): Builds a Node frontend and
  pushes its image to Docker Hub
- [java-coverage](.github/workflows/java-coverage.yml): Generates a Java coverage summary for
  a pull request and posts/updates a PR comment
    - intended to be called from `pull_request` workflows
    - requires JaCoCo coverage XML in the caller repo

## Usage

```yaml
# Build and push (Java app)

jobs:
  build-and-push:
    uses: dario-mr/ci-pipelines/.github/workflows/build-and-push.yml@main
    with:
      image-name: dariomr8/app:latest
    secrets:
      DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}
      DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}
```

```yaml
# Build and push (Node frontend)

jobs:
  build-and-push:
    uses: dario-mr/ci-pipelines/.github/workflows/build-and-push-node.yml@main
    with:
      image-name: dariomr8/frontend-app:latest
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
