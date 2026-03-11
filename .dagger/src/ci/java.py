import dagger

from .containers import build_java_container, with_postgres_service, with_redis_service


async def run_java_tests(source: dagger.Directory, with_redis: bool = False, with_postgres: bool = False) -> str:
  container = _with_optional_services(
      build_java_container(source),
      with_redis=with_redis,
      with_postgres=with_postgres,
  ).with_exec(["mvn", "--batch-mode", "test"])
  return await container.stdout()


async def generate_coverage_xml(
    source: dagger.Directory,
    with_redis: bool = False,
    with_postgres: bool = False,
) -> str:
  container = _with_optional_services(
      build_java_container(source),
      with_redis=with_redis,
      with_postgres=with_postgres,
  ).with_exec(["mvn", "--batch-mode", "verify", "-Pcoverage"])

  xml_file = container.file("/app/target/site/jacoco/jacoco.xml")
  return await xml_file.contents()


async def read_pom_version(source: dagger.Directory) -> str:
  container = (
    build_java_container(source)
    .with_exec(["sh", "-lc", "mvn -q -DforceStdout help:evaluate -Dexpression=project.version | tail -n 1"])
  )
  version = (await container.stdout()).strip()
  if not version:
    raise ValueError("Could not resolve project.version from pom.xml")
  return version


def compute_java_tag(event_name: str, commit_sha: str, pom_version: str) -> str:
  if event_name == "pull_request":
    short_sha = commit_sha.strip()[:7]
    return f"{pom_version}-{short_sha}"
  return pom_version


def _with_optional_services(
    container: dagger.Container,
    with_redis: bool,
    with_postgres: bool,
) -> dagger.Container:
  if with_redis:
    container = with_redis_service(container)
  if with_postgres:
    container = with_postgres_service(container)
  return container
