import dagger
from dagger import dag

from .constants import JAVA_21_IMAGE, POSTGRES_IMAGE, POSTGRES_PORT, REDIS_IMAGE, REDIS_PORT


def build_java_container(source: dagger.Directory) -> dagger.Container:
  maven_cache = dag.cache_volume("maven-cache")
  return (
    dag.container()
    .from_(JAVA_21_IMAGE)
    .with_mounted_cache("/root/.m2", maven_cache)
    .with_mounted_directory(
        "/app",
        source
        .without_directory(".git")
        .without_directory(".dagger")
    )
    .with_workdir("/app")
  )


def with_redis_service(container: dagger.Container) -> dagger.Container:
  redis = (
    dag.container()
    .from_(REDIS_IMAGE)
    .with_exposed_port(REDIS_PORT)
    .as_service()
  )

  return (
    container
    .with_service_binding("redis", redis)
    .with_env_variable("SPRING_DATA_REDIS_HOST", "redis")
    .with_env_variable("SPRING_DATA_REDIS_PORT", str(REDIS_PORT))
  )


def with_postgres_service(container: dagger.Container) -> dagger.Container:
  postgres = (
    dag.container()
    .from_(POSTGRES_IMAGE)
    .with_env_variable("POSTGRES_USER", "test")
    .with_env_variable("POSTGRES_PASSWORD", "test")
    .with_env_variable("POSTGRES_DB", "postgres")
    .with_exposed_port(POSTGRES_PORT)
    .as_service()
  )

  return (
    container
    .with_service_binding("postgres", postgres)
    .with_env_variable(
        "SPRING_DATASOURCE_URL",
        f"jdbc:postgresql://postgres:{POSTGRES_PORT}/postgres"
    )
    .with_env_variable("SPRING_DATASOURCE_USERNAME", "test")
    .with_env_variable("SPRING_DATASOURCE_PASSWORD", "test")
  )
