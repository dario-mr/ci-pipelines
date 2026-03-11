import xml.etree.ElementTree as ET
from typing import Optional

import dagger
from dagger import dag, function, object_type

from .coverage import render_coverage_markdown


@object_type
class Ci:
  DOCKER_REGISTRY = "docker.io"
  JAVA_21_IMAGE = "maven:3.9.9-eclipse-temurin-21-jammy"
  NODE_24_IMAGE = "node:24-alpine"
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
      platforms: str,
      with_redis: bool = False,
      with_postgres: bool = False,
  ) -> str:
    # run tests
    await self.test(source, with_redis=with_redis, with_postgres=with_postgres)

    return await self.publish_image(
        source=source,
        docker_username=docker_username,
        docker_password=docker_password,
        image_name=image_name,
        platforms=platforms,
    )

  @function
  async def node_build(self, source: dagger.Directory) -> str:
    npm_cache = dag.cache_volume("npm-cache")

    container = (
      dag.container()
      .from_(self.NODE_24_IMAGE)
      .with_mounted_cache("/root/.npm", npm_cache)
      .with_mounted_directory(
          "/app",
          source
          .without_directory(".git")
          .without_directory(".dagger")
      )
      .with_workdir("/app")
      .with_exec(["npm", "ci"])
      .with_exec(["npm", "run", "build"])
    )

    return await container.stdout()

  @function
  async def node_build_and_push(
      self,
      source: dagger.Directory,
      docker_username: str,
      docker_password: dagger.Secret,
      image_name: str,
      platforms: str,
  ) -> str:
    # run frontend build
    await self.node_build(source)

    return await self.publish_image(
        source=source,
        docker_username=docker_username,
        docker_password=docker_password,
        image_name=image_name,
        platforms=platforms,
    )

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

  async def publish_image(
      self,
      source: dagger.Directory,
      docker_username: str,
      docker_password: dagger.Secret,
      image_name: str,
      platforms: str,
  ) -> str:
    platform_values = self.resolve_platforms(platforms)
    built_images = [
      source.docker_build(
          dockerfile="Dockerfile",
          platform=platform,
      )
      for platform in platform_values
    ]
    authed_images = [
      image.with_registry_auth(self.DOCKER_REGISTRY, docker_username, docker_password)
      for image in built_images
    ]

    return await authed_images[0].publish(
        f"{self.DOCKER_REGISTRY}/{image_name}",
        platform_variants=authed_images[1:] if len(authed_images) > 1 else None,
    )

  @staticmethod
  def resolve_platforms(platforms: str) -> list[dagger.Platform]:
    platform_values = [value.strip() for value in platforms.split(",") if value.strip()]
    if not platform_values:
      raise ValueError("platforms must be a non-empty platform string, e.g. linux/arm64")

    return [dagger.Platform(platform) for platform in platform_values]

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
