# Workspace Customization Rules

These rules configure behavioral constraints and commands for the agent working within this repository.

---

Name:
    Local Virtual Environment Interpreter Enforcer
Rule:
    Always invoke python scripts, command-line tools, and tests using the absolute path of the local virtual environment executables inside `.venv_new` to prevent package and dependency resolution errors.
    - Python: `c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe`
    - Pytest: `c:\dev\canadian-grant-intelligence\.venv_new\Scripts\pytest.exe`
    - Pip: `c:\dev\canadian-grant-intelligence\.venv_new\Scripts\pip.exe`
    Example: `c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe scripts/validate_skill.py --config configs/canadian_grants.json`

---

Name:
    GitHub CLI OneDrive Sync Snag Resolution
Rule:
    When running any GitHub CLI (`gh`) commands in a OneDrive-synchronized workspace, local remote resolution will fail with "no git remotes found". You MUST bypass local remote detection by appending the explicit repository flag `-R <owner>/<repo>` (specifically `-R 4mayAi/canadian-grant-intelligence`) to all `gh` commands.
    Example: `gh workflow list -R 4mayAi/canadian-grant-intelligence`
