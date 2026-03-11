import dagger
from dagger import dag

from .constants import NODE_24_IMAGE


async def node_build(source: dagger.Directory) -> str:
  npm_cache = dag.cache_volume("npm-cache")

  container = (
    dag.container()
    .from_(NODE_24_IMAGE)
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
