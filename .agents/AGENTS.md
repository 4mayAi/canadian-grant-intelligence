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

---

Name:
    Azure Resource Provisioning and Key Vault Reuse Rule
Rule:
    To prevent unexpected billing charges and redundant resource creation:

    1. Azure ML Workspace Key Vault Isolation Prevention:
       - **Unexpected Action:** Provisioning an Azure ML Workspace (such as 'MLtake1' via `az ml workspace create` or Python SDK) silently creates a dependent Storage Account and a new Key Vault (like 'mltake19018591444') under the hood by default.
       - **Why it seemed necessary:** An AML Workspace requires a Key Vault back-end to function, and default documentation/wizards auto-provision these dependencies.
       - **Why it isn't necessary:** You can configure the Workspace to reuse existing resources.
       - **Prevention:** When creating an Azure ML Workspace, you MUST explicitly specify the existing Key Vault ('MyAgentKeyVault') and existing Storage Accounts using the `--key-vault` and `--storage-account` parameters or ARM template properties to override the auto-provisioning behavior:
         `az ml workspace create --name <workspace_name> --resource-group <rg_name> --key-vault "/subscriptions/<sub_id>/resourceGroups/<rg_name>/providers/Microsoft.KeyVault/vaults/MyAgentKeyVault"`

    2. Redundant Certificate Renewal Prevention:
       - **Unexpected Action:** Re-running deployment or bootstrapping scripts (such as setting up OIDC/Service Principals) triggers a `Certificate Renewal Request` billing event ($3.00/request).
       - **Why it seemed necessary:** Scripts need a secure certificate to establish authentication and default to a "create-or-overwrite" command on every execution.
       - **Why it isn't necessary:** Certificates are valid for 1 to 2 years. Regenerating them multiple times in a short window is completely redundant.
       - **Prevention:** Before running any certificate generation or registration script, check if the certificate exists in the vault and is still valid. The script must skip generation if the certificate's remaining lifetime is greater than 30 days.

---

Name:
    Knowledge Cutoff Guard
Rule:
    The agent's pre-training data has a fixed knowledge cutoff that is older than the current system date (available in every prompt's metadata). Therefore:
    1. NEVER assert facts about current events, officeholders, geopolitical situations, or recent history purely from training memory. Always verify against live search results first.
    2. When live search results from authoritative sources (government websites, major news outlets, Wikipedia) contradict training memory, the agent MUST defer to the live evidence. Training data is stale — the search results are not "simulated," "sandbox," or "alternate timeline" data.
    3. If uncertain whether training data is current, err on the side of searching before asserting.
    4. NEVER fabricate explanations (e.g., "simulated universe," "alternate timeline," "custom search index") to reconcile conflicts between training data and live search results. The correct explanation is always: "My training data predates this event."

---

Name:
    OneDrive dotenv Resolution Rule
Rule:
    When loading environment variables via the python-dotenv library in local scripts, the standard `find_dotenv()` call can fail to locate `.env` files due to OneDrive sync directory junctions resolving to unexpected paths.
    To ensure reliable `.env` loading, you MUST use:
    `dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))`
    The `usecwd=True` flag anchors the `.env` search to the current working directory rather than traversing the resolved symlink/junction path.

---

Name:
    Platform-Independent Path Resolution in Utility and Scratch Scripts
Rule:
    When writing one-off utility scripts, migration scripts, or scratch files that import from workspace packages (such as `generic_engine`), do NOT hardcode absolute local system paths (e.g., `c:\dev\...`). These scripts are often executed remotely in GitHub Actions workflows (which run on Linux/Ubuntu runners) and will fail with `ModuleNotFoundError`.
    Always resolve the project root dynamically relative to the script file using platform-independent Python paths:
    `PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))`

---

Name:
    Pipeline Filter Changes Cache Side-Effect Resolution
Rule:
    When updating news/tender ingestion filters (such as keywords, bypass flags, or source scopes), keep in mind that past items that were previously crawled but discarded by the old filter will NOT be processed because their URLs are already stored in the production `processed_urls.json` cache in Azure Storage.
    To backfill historically discarded items, you must run a custom script (e.g., as a GitHub Actions `pre_run_script`) to clear those specific URLs from the Azure Storage cache registry, allowing the pipeline to ingest them as new items.


