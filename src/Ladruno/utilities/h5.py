from __future__ import annotations
from pathlib import Path
from typing import Optional
import subprocess
from datetime import datetime
from pathlib import Path


class H5RepairTool:
    def __init__(
        self,
        directory: Path,
        pattern: str = "results.part-*.mpco",
        verbose: bool = False,
    ) -> None:
        
        self.directory: Path = Path(directory)
        self.pattern: str = pattern
        self.files: list[Path] = sorted(self.directory.glob(pattern))
        self.status: dict[Path, str] = {}
        self.verbose: bool = verbose          # ← store it!

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _is_verbose(self, override: Optional[bool]) -> bool:
        """Return override if given, else fall back to self.verbose."""
        return self.verbose if override is None else override

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def scan(self, verbose: Optional[bool] = None) -> None:
        """Scan all files and store their status internally."""
        verbose = self._is_verbose(verbose)
        self.status.clear()

        for f in self.files:
            try:
                with h5py.File(f, "r"):
                    self.status[f] = "OK"
            except OSError as e:
                msg = str(e)
                if "file is already open for write" in msg:
                    self.status[f] = "FLAGGED"
                else:
                    self.status[f] = f"ERROR: {msg}"

            if verbose:
                print(f"{f.name:<30} → {self.status[f]}")

    def print_report(self, verbose: Optional[bool] = None) -> None:
        if not self._is_verbose(verbose):
            return

        print("File Status Report:")
        for f, stat in self.status.items():
            print(f"{f.name:<30} →  {stat}")

        counts = {"OK": 0, "FLAGGED": 0, "ERROR": 0}
        for s in self.status.values():
            counts["OK" if s == "OK" else "FLAGGED" if s == "FLAGGED" else "ERROR"] += 1

        print("\nSummary:")
        for k, v in counts.items():
            print(f"{k:<8}: {v}")

    def fix_flagged(self, verbose: Optional[bool] = None) -> None:
        verbose = self._is_verbose(verbose)

        for f, stat in self.status.items():
            if stat != "FLAGGED":
                continue

            if verbose:
                print(f"Fixing: {f.name}")

            result = subprocess.run(["h5clear", "-s", "-i", str(f)], capture_output=True)
            if result.returncode == 0:
                if verbose:
                    print(f"  → Cleared flag on {f.name}")
                self.status[f] = "OK"
            else:
                if verbose:
                    print(f"  ✗ Failed to clear {f.name}")
                    print(result.stderr.decode())

    def run_full_check_and_fix(self, verbose: Optional[bool] = None) -> None:
        """Scan, print report, and attempt to fix any flagged files."""
        verbose = self._is_verbose(verbose)
        self.scan(verbose)
        self.print_report(verbose)
        self.fix_flagged(verbose)
        