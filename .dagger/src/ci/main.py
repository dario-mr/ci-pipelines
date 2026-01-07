import xml.etree.ElementTree as ET
from typing import Optional

import dagger
from dagger import dag, function, object_type

from .coverage import render_coverage_markdown


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
  async def coverage_markdown(
      self,
      source: dagger.Directory,
      base_source: Optional[dagger.Directory] = None,
      changed_files: str = "",
  ) -> str:
    head_xml = await self.coverage_xml(source)

    base_requested = base_source is not None

    base_xml: Optional[str] = None
    if base_source is not None and changed_files.strip():
      try:
        base_xml = await self.coverage_xml(base_source)
        ET.fromstring(base_xml)
      except (dagger.QueryError, ET.ParseError):
        base_xml = None

    return render_coverage_markdown(
        head_xml=head_xml,
        base_xml=base_xml,
        base_requested=base_requested,
        changed_files=changed_files,
    )

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
