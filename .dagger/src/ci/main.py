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
  REDIS_IMAGE = "redis:7-alpine"
  REDIS_PORT = 6379
  POSTGRES_IMAGE = "postgres:16-alpine"
  POSTGRES_PORT = 5432

  @function
  async def test(self, source: dagger.Directory, with_redis: bool = False, with_postgres: bool = False) -> str:
    maven_cache = dag.cache_volume("maven-cache")

    container = self.build_java_container(maven_cache, source)

    if with_redis:
      container = self.with_redis_service(container)

    if with_postgres:
      container = self.with_postgres_service(container)

    container = container.with_exec(["mvn", "--batch-mode", "test"])

    return await container.stdout()

  @function
  async def build_and_push(
      self,
      source: dagger.Directory,
      docker_username: str,
      docker_password: dagger.Secret,
      image_name: str,
      with_redis: bool = False,
      with_postgres: bool = False,
  ) -> str:
    # run tests
    await self.test(source, with_redis=with_redis, with_postgres=with_postgres)

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
      with_redis: bool = False,
      with_postgres: bool = False,
  ) -> str:
    head_xml = await self.coverage_xml(source, with_redis=with_redis, with_postgres=with_postgres)

    base_requested = base_source is not None

    base_xml: Optional[str] = None
    if base_source is not None and changed_files.strip():
      try:
        base_xml = await self.coverage_xml(base_source, with_redis=with_redis, with_postgres=with_postgres)
        ET.fromstring(base_xml)
      except (dagger.QueryError, ET.ParseError):
        base_xml = None

    return render_coverage_markdown(
        head_xml=head_xml,
        base_xml=base_xml,
        base_requested=base_requested,
        changed_files=changed_files,
    )

  async def coverage_xml(self, source: dagger.Directory, with_redis: bool = False, with_postgres: bool = False) -> str:
    maven_cache = dag.cache_volume("maven-cache")

    container = self.build_java_container(maven_cache, source)

    if with_redis:
      container = self.with_redis_service(container)

    if with_postgres:
      container = self.with_postgres_service(container)

    container = container.with_exec(["mvn", "--batch-mode", "verify", "-Pcoverage"])

    # default jacoco output location
    xml_file = container.file("/app/target/site/jacoco/jacoco.xml")
    return await xml_file.contents()

  def build_java_container(self, maven_cache, source):
    return (
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
    )

  def with_redis_service(self, container):
    redis = (
      dag.container()
      .from_(self.REDIS_IMAGE)
      .with_exposed_port(self.REDIS_PORT)
      .as_service()
    )

    return (
      container
      .with_service_binding("redis", redis)
      .with_env_variable("SPRING_DATA_REDIS_HOST", "redis")
      .with_env_variable("SPRING_DATA_REDIS_PORT", str(self.REDIS_PORT))
    )

  def with_postgres_service(self, container):
    postgres = (
      dag.container()
      .from_(self.POSTGRES_IMAGE)
      .with_env_variable("POSTGRES_USER", "test")
      .with_env_variable("POSTGRES_PASSWORD", "test")
      .with_env_variable("POSTGRES_DB", "postgres")
      .with_exposed_port(self.POSTGRES_PORT)
      .as_service()
    )

    return (
      container
      .with_service_binding("postgres", postgres)
      .with_env_variable(
          "SPRING_DATASOURCE_URL",
          f"jdbc:postgresql://postgres:{self.POSTGRES_PORT}/postgres"
      )
      .with_env_variable("SPRING_DATASOURCE_USERNAME", "test")
      .with_env_variable("SPRING_DATASOURCE_PASSWORD", "test")
    )
