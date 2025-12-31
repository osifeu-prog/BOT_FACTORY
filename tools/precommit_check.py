from __future__ import annotations

import os
import subprocess
from pathlib import Path

def git_root() -> Path:
    out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    return Path(out)

def staged_files() -> list[Path]:
    out = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], text=True
    )
    root = git_root()
    files: list[Path] = []
    for line in out.splitlines():
        p = (root / line).resolve()
        if p.is_file():
            files.append(p)
    return files

def is_binary(p: Path) -> bool:
    try:
        data = p.read_bytes()
    except Exception:
        return True
    return b"\x00" in data[:4096]

def has_conflict_markers_by_line(data: bytes) -> bool:
    # Build markers WITHOUT embedding them in source code
    m1 = (b"<" * 7)  # <<<<<<<
    m2 = (b"=" * 7)  # =======
    m3 = (b">" * 7)  # >>>>>>>
    for line in data.splitlines():
        # Check only at line start (real merge-conflict markers are at line start)
        if line.startswith(m1) or line.startswith(m2) or line.startswith(m3):
            return True
    return False

def main() -> int:
    bad: list[tuple[Path, str]] = []

    for p in staged_files():
        if is_binary(p):
            continue
        data = p.read_bytes()

        # UTF-8 BOM
        if data.startswith(b"\xef\xbb\xbf"):
            bad.append((p, "UTF-8 BOM detected (EF BB BF). Save as UTF-8 without BOM."))

        # Merge conflict markers (line-start only)
        if has_conflict_markers_by_line(data):
            bad.append((p, "Merge conflict markers detected at line start."))

        # CRLF
        if b"\r\n" in data:
            bad.append((p, "CRLF line endings detected. Use LF only."))

    if bad:
        print("\n❌ Pre-commit checks failed:\n")
        for p, msg in bad:
            rel = os.path.relpath(str(p), str(git_root()))
            print(f"- {rel}: {msg}")
        print("\nFix the files and re-commit.\n")
        return 1

    print("✅ Pre-commit checks passed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())