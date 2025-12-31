# CI Pipelines

This repository contains my shared `Dagger` CI pipelines, with only a thin `GitHub Actions` wrapper
to
trigger it.

## How it works

Each repository has a very small workflow file that simply calls the reusable workflow here, passing
any required inputs (like image name) and secrets.

The real CI logic — build, test, package, publish, etc. — lives in `Dagger` code in this repo.

## Usage

In each repo:

```yaml
jobs:
  build-and-push:
    uses: dario-mr/ci-pipelines/.github/workflows/build-and-push.yml@v1
    with:
      image-name: dariomr8/app:latest
    secrets:
      DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}
      DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}
```

## References

- [Dagger Documentation](https://docs.dagger.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)