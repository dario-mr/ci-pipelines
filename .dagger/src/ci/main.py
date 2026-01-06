import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

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
  async def coverage_markdown(
      self,
      source: dagger.Directory,
      base_source: Optional[dagger.Directory] = None,
      changed_files: str = "",
  ) -> str:
    def get_line_counter(elem: ET.Element) -> Tuple[int, int]:
      for counter in elem.findall("counter"):
        if counter.get("type") == "LINE":
          missed = int(counter.get("missed") or 0)
          covered = int(counter.get("covered") or 0)
          return missed, covered
      return 0, 0

    def file_line_counters(root: ET.Element) -> Dict[str, Tuple[int, int]]:
      counters: Dict[str, Tuple[int, int]] = {}
      for pkg in root.findall("package"):
        pkg_name = pkg.get("name") or ""
        for sourcefile in pkg.findall("sourcefile"):
          filename = sourcefile.get("name") or ""
          if not filename:
            continue
          missed, covered = get_line_counter(sourcefile)
          key = f"{pkg_name}/{filename}" if pkg_name else filename
          counters[key] = (missed, covered)
      return counters

    def changed_path_to_jacoco_key(path: str) -> Optional[str]:
      normalized = path.strip().lstrip("./")
      if not normalized:
        return None

      markers = (
        "src/main/java/",
        "src/main/kotlin/",
        "src/test/java/",
        "src/test/kotlin/",
      )
      for marker in markers:
        idx = normalized.find(marker)
        if idx != -1:
          return normalized[idx + len(marker):]
      return None

    head_xml = await self.coverage_xml(source)
    head_root = ET.fromstring(head_xml)

    missed_total, covered_total = get_line_counter(head_root)
    total_lines = missed_total + covered_total
    total_pct = 0.0 if total_lines == 0 else covered_total * 100.0 / total_lines

    packages: List[Tuple[str, float, int, int]] = []
    for pkg in head_root.findall("package"):
      missed, covered = get_line_counter(pkg)
      total = missed + covered
      if total == 0:
        continue

      name = (pkg.get("name") or "").replace("/", ".")
      pct = covered * 100.0 / total
      packages.append((name, pct, covered, total))

    packages.sort(key=lambda p: p[0])

    markdown_lines: List[str] = [
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

    if base_source is not None and changed_files.strip():
      base_files: Dict[str, Tuple[int, int]] = {}
      base_total_pct: Optional[float] = None
      try:
        base_xml = await self.coverage_xml(base_source)
        base_root = ET.fromstring(base_xml)
        base_files = file_line_counters(base_root)

        base_missed_total, base_covered_total = get_line_counter(base_root)
        base_total_lines = base_missed_total + base_covered_total
        base_total_pct = (
          0.0 if base_total_lines == 0 else base_covered_total * 100.0 / base_total_lines
        )

        base_available = True
      except (dagger.QueryError, ET.ParseError):
        base_available = False

      head_files = file_line_counters(head_root)

      changed = [line.strip() for line in changed_files.splitlines() if line.strip()]
      changed_keys: List[Tuple[str, str]] = []
      ignored: List[str] = []
      for path in changed:
        key = changed_path_to_jacoco_key(path)
        if key is None:
          ignored.append(path)
          continue
        changed_keys.append((path, key))

      rows: List[str] = []

      for original_path, key in changed_keys:
        head_counts = head_files.get(key)
        base_counts = base_files.get(key) if base_available else None

        if head_counts is None:
          continue

        head_m, head_c = head_counts
        head_t = head_m + head_c
        head_p = 0.0 if head_t == 0 else head_c * 100.0 / head_t

        if base_counts is not None:
          base_m, base_c = base_counts
          base_t = base_m + base_c
          base_p = 0.0 if base_t == 0 else base_c * 100.0 / base_t
          delta_label = f"{(head_p - base_p):+.2f}%"
          coverage_label = f"{head_p:.2f}% ({delta_label})"
        else:
          coverage_label = f"{head_p:.2f}% (n/a)"

        rows.append(f"| `{original_path}` | {coverage_label} |")

      max_rows = 50
      omitted_rows = 0
      if len(rows) > max_rows:
        omitted_rows = len(rows) - max_rows
        rows = rows[:max_rows]

      total_delta_label = "n/a"
      if base_available and base_total_pct is not None:
        total_delta_label = f"{(total_pct - base_total_pct):+.2f}%"

      markdown_lines += [
        "",
        "## 🔍 Changed files coverage",
        "",
        f"Total coverage: {total_pct:.2f}% ({total_delta_label})",
        "",
      ]

      if rows:
        markdown_lines += [
          "| File | Line coverage |",
          "| ---- | ------------- |",
          *rows,
        ]

      if omitted_rows:
        markdown_lines += [
          "",
          f"_Table truncated: {omitted_rows} more files omitted._",
        ]

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
