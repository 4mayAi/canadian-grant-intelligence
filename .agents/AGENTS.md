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

---

Name:
    Short Acronym Plural Keyword Rule
Rule:
    When adding short acronyms (<= 4 characters) to the `keywords` list in any pipeline configuration file (e.g., `canadian_grants.json` or `innovation_clusters.json`), you MUST explicitly include both the singular and plural forms (e.g., `"RFP"` and `"RFPs"`, `"SME"` and `"SMEs"`, `"BEV"` and `"BEVs"`). The generic engine enforces exact word boundaries `\b` for terms <= 4 characters, causing it to discard plural versions unless they are explicitly configured.

---

Name:
    Procedural Test Execution and PYTHONPATH Enforcer
Rule:
    Do NOT run a monolithic `pytest` command (e.g., `pytest tests/`) in the workspace. Several test files in the `tests/` directory contain procedural code calling `sys.exit()` at the module level, which aborts the pytest discovery process.
    Instead, execute test scripts individually using the local virtual environment Python interpreter (`.venv_new\Scripts\python.exe`) with the `PYTHONPATH` environment variable set to the absolute path of the workspace.
    Example:
    `$env:PYTHONPATH="c:\dev\canadian-grant-intelligence"; c:\dev\canadian-grant-intelligence\.venv_new\Scripts\python.exe c:\dev\canadian-grant-intelligence\tests\test_dashboard.py`

---

Name:
    Direct Government Search Feed Rule
Rule:
    When configuring direct, first-party government search Atom/RSS feeds (such as `gov.uk` search endpoints):
    1. Set `"skip_query_refactoring": true` to prevent the engine's query refactoring module from altering the query URL.
    2. Quote search keywords using literal double quotes (e.g., `%22critical+minerals%22` instead of `critical+minerals`) to force exact matching and filter out high-noise, unrelated announcements.

