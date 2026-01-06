import xml.etree.ElementTree as ET

import dagger
from dagger import dag, object_type, function


@object_type
class Ci:
  DOCKER_REGISTRY = "docker.io"
  PLATFORM_LINUX_ARM64 = "linux/arm64"
  JAVA_21_IMAGE = "maven:3.9.9-eclipse-temurin-21-jammy"

  @function
  async def test(self, source: dagger.Directory) -> str:
    maven_cache = dag.cache_volume("maven-cache")

    container = (
      dag.container()
      .from_(self.JAVA_21_IMAGE)
      .with_mounted_cache("/root/.m2", maven_cache)
      .with_mounted_directory(
          "/app",
          source
          .without_directory(".git")
          .without_directory(".dagger")
      )
      .with_workdir("/app")
      .with_exec(["mvn", "--batch-mode", "test"])
    )

    return await container.stdout()

  @function
  async def build_and_push(
      self,
      source: dagger.Directory,
      docker_username: str,
      docker_password: dagger.Secret,
      image_name: str,
  ) -> str:
    # run tests
    await self.test(source)

    # build docker image
    platform = dagger.Platform(self.PLATFORM_LINUX_ARM64)
    image = source.docker_build(
        dockerfile="Dockerfile",
        platform=platform,
    )

    # authenticate and push image to docker hub
    authed = image.with_registry_auth(self.DOCKER_REGISTRY, docker_username, docker_password)
    return await authed.publish(f"{self.DOCKER_REGISTRY}/{image_name}")

  @function
  async def coverage_markdown(self, source: dagger.Directory) -> str:
    def get_line_counter(elem: ET.Element) -> tuple[int, int]:
      for counter in elem.findall("counter"):
        if counter.get("type") == "LINE":
          missed = int(counter.get("missed") or 0)
          covered = int(counter.get("covered") or 0)
          return missed, covered
      return 0, 0

    xml = await self.coverage_xml(source)
    root = ET.fromstring(xml)

    missed_total, covered_total = get_line_counter(root)
    total_lines = missed_total + covered_total
    total_pct = 0.0 if total_lines == 0 else covered_total * 100.0 / total_lines

    packages: list[tuple[str, float, int, int]] = []
    for pkg in root.findall("package"):
      missed, covered = get_line_counter(pkg)
      total = missed + covered
      if total == 0:
        continue

      name = (pkg.get("name") or "").replace("/", ".")
      pct = covered * 100.0 / total
      packages.append((name, pct, covered, total))

    packages.sort(key=lambda p: p[0])

    markdown_lines: list[str] = [
      "<!-- ci-pipelines:coverage-comment -->",
      "## ☂️ Code coverage",
      "",
      f"**Total line coverage:** {total_pct:.2f}% ({covered_total}/{total_lines} lines)",
      "",
      "| Package | Line coverage |",
      "| ------- | ------------- |",
    ]

    for name, pct, covered, total in packages:
      markdown_lines.append(f"| `{name}` | {pct:.2f}% ({covered}/{total}) |")

    return "\n".join(markdown_lines) + "\n"

  async def coverage_xml(self, source: dagger.Directory) -> str:
    maven_cache = dag.cache_volume("maven-cache")

    container = (
      dag.container()
      .from_(self.JAVA_21_IMAGE)
      .with_mounted_cache("/root/.m2", maven_cache)
      .with_mounted_directory(
          "/app",
          source
          .without_directory(".git")
          .without_directory(".dagger")
      )
      .with_workdir("/app")
      .with_exec(["mvn", "--batch-mode", "verify", "-Pcoverage"])
    )

    # default jacoco output location
    xml_file = container.file("/app/target/site/jacoco/jacoco.xml")
    return await xml_file.contents()
