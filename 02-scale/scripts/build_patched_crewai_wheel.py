"""Build a patched CrewAI wheel for Agent Engine source deployments.

Agent Engine source builds run ``compileall`` across installed packages.
CrewAI ships CLI template Python files containing Jinja placeholders such as
``{{folder_name}}``, which triggers ``SyntaxError`` during that step.

This helper repacks the installed CrewAI distribution into a local wheel after
removing Python template files under ``crewai/cli/templates``. The CrewAI CLI
scaffolding is not needed for this demo runtime.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.metadata
from pathlib import Path
import shutil
import tempfile
import zipfile


def _find_dist_info_dir(dist: importlib.metadata.Distribution) -> Path:
    for file in dist.files or []:
        if file.name == "WHEEL" and ".dist-info" in str(file):
            return Path(dist.locate_file(file)).parent
    raise RuntimeError("Could not locate CrewAI dist-info directory.")


def _clean_templates(package_root: Path) -> list[str]:
    templates_root = package_root / "cli" / "templates"
    if not templates_root.exists():
        return []

    removed: list[str] = []
    for py_file in templates_root.rglob("*.py"):
        removed.append(str(py_file.relative_to(package_root)))
        py_file.unlink()

    for pycache_dir in templates_root.rglob("__pycache__"):
        if pycache_dir.is_dir():
            shutil.rmtree(pycache_dir)

    for path in sorted(templates_root.rglob("*"), reverse=True):
        if path.is_dir() and ("{{" in path.name or "}}" in path.name):
            removed.append(str(path.relative_to(package_root)))
            shutil.rmtree(path)

    return removed


def _first_tag(dist_info_dir: Path) -> str:
    wheel_file = dist_info_dir / "WHEEL"
    for line in wheel_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("Tag: "):
            return line.split(": ", 1)[1].strip()
    raise RuntimeError("Could not find a wheel tag in CrewAI WHEEL metadata.")


def _hash_file(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"sha256={encoded}", len(data)


def build_patched_wheel(output_dir: str | Path) -> Path:
    dist = importlib.metadata.distribution("crewai")
    package_root = Path(dist.locate_file("crewai"))
    dist_info_dir = _find_dist_info_dir(dist)
    wheel_tag = _first_tag(dist_info_dir)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dist_name = dist.metadata["Name"].replace("-", "_")
    version = dist.version
    wheel_name = f"{dist_name}-{version}-{wheel_tag}.whl"
    wheel_path = output_dir / wheel_name

    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        staging_package = staging_root / package_root.name
        staging_dist_info = staging_root / dist_info_dir.name

        shutil.copytree(package_root, staging_package)
        shutil.copytree(dist_info_dir, staging_dist_info)

        removed = _clean_templates(staging_package)
        if removed:
            print("Removed CrewAI template files:")
            for item in removed:
                print(f"  - {item}")
        else:
            print("No CrewAI template files needed patching.")

        record_path = staging_dist_info / "RECORD"
        records: list[list[str]] = []
        for path in sorted(staging_root.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(staging_root).as_posix()
            if rel_path == f"{staging_dist_info.name}/RECORD":
                continue
            file_hash, size = _hash_file(path)
            records.append([rel_path, file_hash, str(size)])

        records.append([f"{staging_dist_info.name}/RECORD", "", ""])
        with record_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerows(records)

        with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(staging_root.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(staging_root).as_posix())

    print(f"Patched CrewAI wheel written to {wheel_path}")
    return wheel_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a patched CrewAI wheel for Agent Engine deployments."
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "vendor"),
        help="Directory where the patched wheel should be written.",
    )
    args = parser.parse_args()

    build_patched_wheel(args.output_dir)


if __name__ == "__main__":
    main()
