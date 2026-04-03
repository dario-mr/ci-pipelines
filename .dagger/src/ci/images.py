import dagger

from .constants import DOCKER_REGISTRY


async def publish_image(
    source: dagger.Directory,
    docker_username: str,
    docker_password: dagger.Secret,
    image_name: str,
    dockerfile: str,
    platforms: str,
) -> str:
  platform_values = _resolve_platforms(platforms)
  built_images = [
    source.docker_build(
        dockerfile=dockerfile,
        platform=platform,
    )
    for platform in platform_values
  ]
  authed_images = [
    image.with_registry_auth(DOCKER_REGISTRY, docker_username, docker_password)
    for image in built_images
  ]

  return await authed_images[0].publish(
      f"{DOCKER_REGISTRY}/{image_name}",
      platform_variants=authed_images[1:] if len(authed_images) > 1 else None,
  )


def _resolve_platforms(platforms: str) -> list[dagger.Platform]:
  platform_values = [value.strip() for value in platforms.split(",") if value.strip()]
  if not platform_values:
    raise ValueError("platforms must be a non-empty platform string, e.g. linux/arm64")

  return [dagger.Platform(platform) for platform in platform_values]
