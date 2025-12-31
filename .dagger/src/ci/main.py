import dagger
from dagger import dag, object_type, function, Platform


@object_type
class Ci:
  DOCKER_REGISTRY = "docker.io"
  PLATFORM_LINUX_ARM64 = "linux/arm64"

  @function
  async def test(self, source: dagger.Directory) -> str:
    maven_cache = dag.cache_volume("maven-cache")

    container = (
      dag.container()
      .from_("maven:3.9.9-eclipse-temurin-21-jammy")
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
