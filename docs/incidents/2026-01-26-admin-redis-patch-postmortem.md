# Incident Postmortem  2026-01-26  admin Redis patch broke main.py

## Summary
- Goal: Add private ACK/ECHO fallback + make admin login explicitly require Redis.
- Impact: main.py failed to compile (IndentationError / SyntaxError), deploy risk.
- Final status: Fixed via PR flow + branch protection enabled.
- Patch applied via tools/patch_admin_acks_redis.py  IndentationError line ~127

## Contributing Factors
- PowerShell output encoding made debugging messages look corrupted.

## What Went Well
- git bisect with py_compile quickly identified first bad commit.
- Rescue branch preserved forensic state.
- Branch protection prevented further direct damage to main.

## What Went Wrong
- Patching Python with regex without a formatter/AST guarantees.

## Action Items
1. Add CI: py_compile + tests on PR.
2. Refactor admin:status to a helper function.
3. Replace regex patching with AST-based editing or manual targeted diffs.
4. Keep branch protection always-on; avoid temporarily lowering approvals.

## References
- Repo: BOT_FACTORY
- Service: tease-production (Railway)
- Health endpoint: /health (200 OK)