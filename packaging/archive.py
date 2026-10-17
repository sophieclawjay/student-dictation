"""Archive the whole app, including worker and dynamically loaded libraries."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dist = root / "dist"
    stem = f"student-dictation-{platform.system().lower()}-{platform.machine().lower()}"
    destination = dist / f"{stem}.zip"
    if sys.platform == "darwin":
        # ditto preserves executable permissions and the bundle's framework symlinks.
        subprocess.run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(dist / "Student Dictation.app"),
                str(destination),
            ],
            check=True,
        )
    else:
        source = dist / "StudentDictation"
        with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
            for path in source.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(dist))
    print(destination)


if __name__ == "__main__":
    main()
