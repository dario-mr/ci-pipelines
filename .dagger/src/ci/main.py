import xml.etree.ElementTree as elementTree
from typing import Optional

import dagger
from dagger import function, object_type
from .coverage import render_coverage_markdown
from .images import publish_image
from .java import compute_java_tag, generate_coverage_xml, read_pom_version, run_java_tests
from .node import compute_node_tag, node_build, read_package_version


@object_type
class Ci:

  @function
  async def build_and_push_java(
      self,
      source: dagger.Directory,
      docker_username: str,
      docker_password: dagger.Secret,
      image_repo: str,
      event_name: str,
      commit_sha: str,
      platforms: str,
      dockerfile: str = "Dockerfile",
      with_redis: bool = False,
      with_postgres: bool = False,
  ) -> str:
    await run_java_tests(source, with_redis=with_redis, with_postgres=with_postgres)

    pom_version = await read_pom_version(source)
    tag = compute_java_tag(event_name=event_name, commit_sha=commit_sha, pom_version=pom_version)
    image_name = f"{image_repo}:{tag}"

    return await publish_image(
        source=source,
        docker_username=docker_username,
        docker_password=docker_password,
        image_name=image_name,
        dockerfile=dockerfile,
        platforms=platforms,
    )

  @function
  async def build_and_push_node(
      self,
      source: dagger.Directory,
      docker_username: str,
      docker_password: dagger.Secret,
      image_repo: str,
      event_name: str,
      commit_sha: str,
      platforms: str,
      dockerfile: str = "Dockerfile",
  ) -> str:
    await node_build(source)

    package_version = await read_package_version(source)
    tag = compute_node_tag(event_name=event_name, commit_sha=commit_sha, package_version=package_version)
    image_name = f"{image_repo}:{tag}"

    return await publish_image(
        source=source,
        docker_username=docker_username,
        docker_password=docker_password,
        image_name=image_name,
        dockerfile=dockerfile,
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
    head_xml = await generate_coverage_xml(source, with_redis=with_redis, with_postgres=with_postgres)

    base_requested = base_source is not None

    base_xml: Optional[str] = None
    if base_source is not None and changed_files.strip():
      try:
        base_xml = await generate_coverage_xml(base_source, with_redis=with_redis, with_postgres=with_postgres)
        elementTree.fromstring(base_xml)
      except (dagger.QueryError, elementTree.ParseError):
        base_xml = None

    return render_coverage_markdown(
        head_xml=head_xml,
        base_xml=base_xml,
        base_requested=base_requested,
        changed_files=changed_files,
    )
