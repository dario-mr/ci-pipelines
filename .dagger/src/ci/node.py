import dagger
from .containers import build_node_container


async def node_build(source: dagger.Directory) -> str:
  container = (
    build_node_container(source)
    .with_exec(["npm", "ci"])
    .with_exec(["npm", "run", "build"])
  )

  return await container.stdout()


async def read_package_version(source: dagger.Directory) -> str:
  container = build_node_container(source).with_exec(["node", "-p", "require('./package.json').version"])
  version = (await container.stdout()).strip()
  if not version:
    raise ValueError("Could not resolve version from package.json")
  return version


def compute_node_tag(event_name: str, commit_sha: str, package_version: str) -> str:
  if event_name == "pull_request":
    short_sha = commit_sha.strip()[:7]
    return f"{package_version}-{short_sha}"
  return package_version
