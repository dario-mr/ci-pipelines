import dagger
from .containers import build_node_container, build_playwright_container


async def node_build(source: dagger.Directory) -> str:
  container = build_node_container(source).with_exec(["npm", "ci"])

  container = _with_standard_node_checks(container)
  await _run_optional_playwright_tests(source)

  container = container.with_exec(["npm", "run", "build"])

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


def _with_standard_node_checks(container: dagger.Container) -> dagger.Container:
  container = _with_optional_npm_script(container, "lint")
  return _with_optional_npm_script(container, "test")


def _with_optional_npm_script(container: dagger.Container, script_name: str) -> dagger.Container:
  return container.with_exec([
    "sh",
    "-lc",
    (
      f"if node -e \"process.exit(require('./package.json').scripts?.['{script_name}'] ? 0 : 1)\"; "
      f"then npm run {script_name}; "
      f"else echo \"Skipping npm run {script_name} (no {script_name} script)\"; fi"
    ),
  ])


async def _run_optional_playwright_tests(source: dagger.Directory) -> str:
  if not await _has_npm_script(source, "test:e2e"):
    return "Skipping npm run test:e2e (no test:e2e script defined)"

  container = (
    build_playwright_container(source)
    .with_exec(["npm", "ci"])
  )
  return await container.with_exec(["npm", "run", "test:e2e"]).stdout()


async def _has_npm_script(source: dagger.Directory, script_name: str) -> bool:
  container = build_node_container(source).with_exec([
    "node",
    "-e",
    f"process.stdout.write(require('./package.json').scripts?.['{script_name}'] ? 'true' : 'false')",
  ])
  return (await container.stdout()).strip() == "true"
