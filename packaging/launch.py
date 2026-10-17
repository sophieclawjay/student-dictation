"""PyInstaller entry point for both the desktop and its pipe-enabled worker."""

import multiprocessing

if __name__ == "__main__":
    # PyInstaller intercepts resource-tracker/spawn helpers here before argument
    # parsing. Native inference dependencies can start multiprocessing helpers.
    multiprocessing.freeze_support()
    from student_dictation.__main__ import main

    raise SystemExit(main())
