"""Preserve installed dependency license texts alongside packaged distributions."""

from __future__ import annotations

import importlib.metadata
import shutil
from pathlib import Path


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "build" / "third-party-licenses"
    destination.mkdir(parents=True, exist_ok=True)
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name", "unknown")
        target = destination / name
        target.mkdir(exist_ok=True)
        (target / "METADATA.txt").write_text(
            f"Name: {name}\nVersion: {distribution.version}\n"
            f"License: {distribution.metadata.get('License-Expression', '')}\n"
            f"License metadata: {distribution.metadata.get('License', '')}\n"
            f"Home: {distribution.metadata.get('Home-Page', '')}\n",
            encoding="utf-8",
        )
        for entry in distribution.files or []:
            if any(
                part.lower().startswith(("license", "copying", "notice", "copyright"))
                for part in entry.parts
            ):
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    # Preserve subpaths because Qt ships many distinct license files.
                    relative = Path(*[part for part in entry.parts if part not in {"..", "."}])
                    output = target / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, output)
    print(f"Dependency notices collected in {destination}")


if __name__ == "__main__":
    main()
