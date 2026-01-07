import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

COVERAGE_COMMENT_MARKER = "<!-- ci-pipelines:coverage-comment -->"
MAX_CHANGED_FILES_ROWS = 50


@dataclass(frozen=True)
class LineCounts:
  missed: int
  covered: int

  @property
  def total(self) -> int:
    return self.missed + self.covered

  @property
  def pct(self) -> float:
    return 0.0 if self.total == 0 else self.covered * 100.0 / self.total


def line_counts(elem: ET.Element) -> LineCounts:
  for counter in elem.findall("counter"):
    if counter.get("type") == "LINE":
      missed = int(counter.get("missed") or 0)
      covered = int(counter.get("covered") or 0)
      return LineCounts(missed=missed, covered=covered)
  return LineCounts(missed=0, covered=0)


def file_line_counters(root: ET.Element) -> Dict[str, LineCounts]:
  counters: Dict[str, LineCounts] = {}
  for pkg in root.findall("package"):
    pkg_name = pkg.get("name") or ""
    for sourcefile in pkg.findall("sourcefile"):
      filename = sourcefile.get("name") or ""
      if not filename:
        continue
      counts = line_counts(sourcefile)
      key = f"{pkg_name}/{filename}" if pkg_name else filename
      counters[key] = counts
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


def package_rows(root: ET.Element) -> List[Tuple[str, float, int, int]]:
  packages: List[Tuple[str, float, int, int]] = []
  for pkg in root.findall("package"):
    counts = line_counts(pkg)
    if counts.total == 0:
      continue

    name = (pkg.get("name") or "").replace("/", ".")
    packages.append((name, counts.pct, counts.covered, counts.total))

  packages.sort(key=lambda p: p[0])
  return packages


def render_package_table(packages: Iterable[Tuple[str, float, int, int]]) -> List[str]:
  lines: List[str] = [
    "| Package | Line coverage |",
    "| ------- | ------------- |",
  ]
  for name, pct, covered, total in packages:
    lines.append(f"| `{name}` | {pct:.2f}% ({covered}/{total}) |")
  return lines


def _render_total_delta(total_pct: float, base_total_pct: float) -> Tuple[str, str]:
  total_delta = total_pct - base_total_pct
  total_delta_label = f"{total_delta:+.2f}%"
  total_delta_indicator = "🟢" if total_delta >= 0 else "🔴"
  return total_delta_indicator, total_delta_label


def _render_file_delta(head_pct: float, base_pct: float) -> str:
  delta = head_pct - base_pct
  delta_label = f"{delta:+.2f}%"
  delta_indicator = "🟢" if delta >= 0 else "🔴"
  return f"{head_pct:.2f}% ({delta_indicator} {delta_label})"


def render_changed_files_section(
    *,
    head_root: ET.Element,
    base_root: Optional[ET.Element],
    changed_files: str,
    total_pct: float,
    base_total_pct: Optional[float],
) -> List[str]:
  head_files = file_line_counters(head_root)
  base_files = file_line_counters(base_root) if base_root is not None else {}

  changed = [line.strip() for line in changed_files.splitlines() if line.strip()]
  changed_keys: List[Tuple[str, str]] = []
  for path in changed:
    key = changed_path_to_jacoco_key(path)
    if key is not None:
      changed_keys.append((path, key))

  rows: List[str] = []
  for original_path, key in sorted(changed_keys, key=lambda t: t[0]):
    head_counts = head_files.get(key)
    if head_counts is None:
      continue

    head_label = head_counts.pct
    base_counts = base_files.get(key)

    coverage_label = f"{head_label:.2f}% (n/a)"
    if base_counts is not None:
      coverage_label = _render_file_delta(head_label, base_counts.pct)

    rows.append(f"| `{original_path}` | {coverage_label} |")

  omitted_rows = 0
  if len(rows) > MAX_CHANGED_FILES_ROWS:
    omitted_rows = len(rows) - MAX_CHANGED_FILES_ROWS
    rows = rows[:MAX_CHANGED_FILES_ROWS]

  total_delta_label = "n/a"
  total_delta_indicator = ""
  if base_total_pct is not None:
    total_delta_indicator, total_delta_label = _render_total_delta(total_pct, base_total_pct)

  total_delta_prefix = f"{total_delta_indicator} " if total_delta_indicator else ""

  lines: List[str] = [
    "",
    "## 🔍 Changed files coverage",
    "",
    f"Total coverage: {total_pct:.2f}% ({total_delta_prefix}{total_delta_label})",
    "",
  ]

  if rows:
    lines += [
      "| File | Line coverage |",
      "| ---- | ------------- |",
      *rows,
    ]

  if omitted_rows:
    lines += [
      "",
      f"_Table truncated: {omitted_rows} more files omitted._",
    ]

  return lines


def render_coverage_markdown(
    *,
    head_xml: str,
    base_xml: Optional[str] = None,
    base_requested: bool = False,
    changed_files: str = "",
) -> str:
  head_root = ET.fromstring(head_xml)
  head_total = line_counts(head_root)

  markdown_lines: List[str] = [COVERAGE_COMMENT_MARKER]

  if base_requested and changed_files.strip():
    base_root: Optional[ET.Element] = None
    base_total_pct: Optional[float] = None

    if base_xml is not None:
      base_root = ET.fromstring(base_xml)
      base_total_pct = line_counts(base_root).pct

    markdown_lines += render_changed_files_section(
        head_root=head_root,
        base_root=base_root,
        changed_files=changed_files,
        total_pct=head_total.pct,
        base_total_pct=base_total_pct,
    )

  code_coverage_lines: List[str] = [
    f"**Total line coverage:** {head_total.pct:.2f}% ({head_total.covered}/{head_total.total} lines)",
    "",
    *render_package_table(package_rows(head_root)),
  ]

  markdown_lines += [
    "",
    "## ☂️ Coverage details",
    "",
    "<details>",
    "<summary>Show details</summary>",
    "",
    *code_coverage_lines,
    "",
    "</details>",
  ]

  return "\n".join(markdown_lines) + "\n"
