from __future__ import annotations
from pathlib import Path
import re

PATH = Path("tools/run_staking_accrual_once.py")
lines = PATH.read_text(encoding="utf-8").splitlines()

# Find a line that contains "finally:" (possibly with spaces) - Python: no \b after ':'
finally_idx = None
for i, line in enumerate(lines):
    if re.match(r"^\s*finally:\s*$", line):
        finally_idx = i
        break

# If no clean line, try "contains finally:" and normalize it
if finally_idx is None:
    for i, line in enumerate(lines):
        if "finally:" in line:
            finally_idx = i
            # normalize to a clean finally line, preserving indentation
            indent = re.match(r"^(\s*)", line).group(1)
            lines[i] = f"{indent}finally:"
            break

if finally_idx is None:
    raise SystemExit("No finally: found (even as substring)")

# Find __main__
main_idx = None
for i, line in enumerate(lines):
    if re.match(r'^\s*if __name__\s*==\s*"__main__":\s*$', line):
        main_idx = i
        break
if main_idx is None:
    raise SystemExit("No __main__ guard found")
if main_idx <= finally_idx:
    raise SystemExit("__main__ appears before finally (unexpected)")

indent_finally = re.match(r"^(\s*)", lines[finally_idx]).group(1)
indent1 = indent_finally + "    "
indent2 = indent1 + "    "

# Build a VALID finally block (structure must be correct)
finally_body = [
    f"{indent1}# Release advisory lock safely (and clean broken transaction if needed)",
    f"{indent1}try:",
    f"{indent2}conn.rollback()",
    f"{indent1}except Exception:",
    f"{indent2}pass",
    f"{indent1}try:",
    f"{indent2}c.execute(text(\"SELECT pg_advisory_unlock(912345678)\"))",
    f"{indent1}except Exception:",
    f"{indent2}try:",
    f"{indent2}    with engine.connect() as c2:",
    f"{indent2}        c2.execute(text(\"SELECT pg_advisory_unlock(912345678)\"))",
    f"{indent2}except Exception:",
    f"{indent2}    pass",
]

# Rebuild file:
# Keep everything up to finally line (inclusive), then our finally body, then the __main__ block and after.
before = lines[: finally_idx + 1]
after = lines[main_idx:]
new_lines = before + finally_body + [""] + after

# Ensure module-level imports are not indented (safety)
fixed = []
for line in new_lines:
    if re.match(r"^\s+(import|from)\s+", line):
        fixed.append(re.sub(r"^\s+", "", line))
    else:
        fixed.append(line)

text = "\n".join(fixed) + "\n"

# Ensure import json exists (only if missing)
if not re.search(r"(?m)^\s*import\s+json\s*$", text):
    if re.search(r"(?m)^\s*import\s+os\s*$", text):
        text = re.sub(r"(?m)^(\s*import\s+os\s*)$", r"\1\nimport json", text)
    else:
        text = "import json\n" + text

PATH.write_text(text, encoding="utf-8", newline="\n")

print("Patched OK. Head:")
for i, l in enumerate(text.splitlines()[:25], start=1):
    print(f"{i:04d}: {l}")