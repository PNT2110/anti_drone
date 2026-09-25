# Scope 18 — Test report

{
  "pytest": {
    "command": "PYTHONPATH=. pytest -q",
    "returncode": 0,
    "output": "........................................................................ [ 79%]\n...................                                                      [100%]\n91 passed, 1 skipped in 1.02s\n"
  },
  "compileall": {
    "command": "python -m compileall -q scripts src tests",
    "returncode": 0,
    "output": ""
  },
  "git_diff_check": {
    "command": "git diff --check",
    "returncode": 0,
    "output": ""
  }
}
