# Session Log: Background Task Popup Investigation

Date: 2026-10-13
Time: 04:55 AM UTC
Title: Investigation of Black Screen Popups from Background Schedulers

## Session Content
- Investigated user report of an intermittent black console screen popping up during work.
- Queried Windows Task Scheduler for non-Microsoft scheduled tasks and active triggers.
- Identified task `GHA_Pipeline_Scheduler` running under root path `\`.
  - Action: `powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\dev\canadian-grant-intelligence\scratch\local_scheduler.ps1`
  - Trigger: Repeats every 1 hour (`PT1H`).
  - Last Run Time: `2026-10-12 9:55:04 PM PDT` and `2026-10-12 10:00:00 PM PDT`, matching the exact timestamp of the user's reported popup event.
  - Root Cause: `powershell.exe` with `-WindowStyle Hidden` still briefly creates and maps a console window via `conhost.exe` before hiding itself, and any downstream console calls (e.g. `gh workflow run`) also briefly interact with the console subsystem.
- Also identified `GeminiQuestradeBot_MorningBrief` running daily at 07:00 AM via batch file (`run_morning_brief.bat`).
- Identified `Resume_Pipeline_Schedulers_Oct1_2026` which ran on Oct 1, 2026 to enable the above schedulers.
- User requested a breakdown of all scheduled tasks on a timer. Compiled table of active timed tasks (both developer pipelines and background system updaters).
- Investigated `GHA_Pipeline_Scheduler` purpose:
  - Backed by `C:\dev\canadian-grant-intelligence\scratch\local_scheduler.ps1` and registered via `register_task.ps1`.
  - Created to dispatch critical GitHub Actions workflow runs via `gh workflow run` across two repositories (`4mayAi/canadian-grant-intelligence` for grants, mining, trade compliance, clusters scrapers and `emurira/credit-spread-automation-v4` for CSSv4 trading/lifecycle runs) at exact UTC hours, bypassing native GitHub Actions cron schedule jitter/delays.
- Investigated `GoogleUserPEH` (`RunPlatformExperienceHelper_Metrics`):
  - Component installed by Google Chrome (`platform_experience_helper.exe`).
  - Enabled by Chrome's default "Help improve Chrome's features and performance" (usage stats & crash reporting) setting opted into during browser installation/setup.
  - Provided instructions to disable Chrome metrics reporting via settings, registry, or disabling the tasks.

## Summary:
- Diagnosed the cause of the black screen flash as the hourly `GHA_Pipeline_Scheduler` Windows Scheduled Task executing `local_scheduler.ps1`.
- Verified the execution timestamp matched within seconds of the user's interaction.
- Explained the architecture, triggering mechanism, and rationale behind `GHA_Pipeline_Scheduler` and `GoogleUserPEH` Chrome metrics tasks.
- Successfully disabled `GHA_Pipeline_Scheduler` via `Disable-ScheduledTask` and verified its state is `Disabled`.

## Issues:
- Issue 1: Windows Task Scheduler launches `powershell.exe` in an interactive logon session with `-WindowStyle Hidden`, causing a transient console window flash every hour. (Resolved by disabling the task).

## Next Steps:
- None required. Task is disabled and will no longer fire or pop up console windows. If background GitHub Actions workflow execution is needed in the future, can re-enable with a silent VBScript/WScript launcher.
