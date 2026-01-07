# CI Pipelines

This repository contains my shared `Dagger` CI pipelines, with only a thin `GitHub Actions` wrapper
to trigger it.

## How it works

Each repository has a very small workflow file that simply calls the reusable workflow here, passing
any required inputs (like image name) and secrets.

The real CI logic — build, test, package, publish, etc. — lives in `Dagger` code in this repo.

## Workflows

- [build-and-push](.github/workflows/build-and-push.yml): Builds a container image with Dagger
  and pushes it to Docker Hub
- [java-coverage](.github/workflows/java-coverage.yml): Generates a Java coverage summary for
  a pull request and posts/updates a PR comment
    - intended to be called from `pull_request` workflows
    - requires JaCoCo coverage XML in the caller repo

## Usage

```yaml
# Build and push 

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
# Coverage (PR comment)
jobs:
  coverage:
    uses: dario-mr/ci-pipelines/.github/workflows/java-coverage.yml@main
    with:
      pull-request-number: ${{ github.event.pull_request.number }}
```

## References

- [Dagger Documentation](https://docs.dagger.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)