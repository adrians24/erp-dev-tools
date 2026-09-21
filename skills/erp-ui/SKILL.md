---
name: erp-ui
description: Navigate, inspect, test, or screenshot local and internal Visma.net ERP screens using playwright-cli.
---

# ERP UI

Use the scripts in [scripts](scripts/) for local session setup, direct navigation, readiness, and recovery. They assign a stable Playwright session to the current worktree, reuse it during the task, verify the company and screen, and emit JSON. Close the session when the task is complete unless the user wants it left open.

Resolve `$erpUiRoot` to the directory containing this `SKILL.md`, using its location in the skill catalog. Plugin installation paths vary; do not reconstruct a personal skill path.

```powershell
& (Join-Path $erpUiRoot 'scripts\Open-ErpScreen.ps1') `
    -Screen sales-order `
    -Keys @{ OrderType = 'SO'; OrderNbr = '001234' }
```

Use `Get-ErpScreens.ps1 -Search <text>` to search [the catalog](references/screens.json), `-ScreenId` for an uncatalogued screen, and `-BuildUrlOnly` to validate navigation inputs without opening a browser. Pass `-Branch <name-or-id>` when branch identity matters; the helper resolves the company branch catalog and verifies the result. Reusing the active branch keeps the session. Changing branches resets that named browser session and selects the requested branch during fresh local login because the legacy selector service leaves inconsistent ASP.NET state. Save or discard pending UI edits before changing branches. The helper also verifies every supplied record key in the final URL. It navigates the current tab by default; pass `-NewTab` when the existing tab may be useful or contain unsaved state. Use `-Verbose` for elapsed stage diagnostics, `Get-ErpUiContext.ps1` to inspect the current session, `Wait-ErpScreenReady.ps1` after an action that reloads the screen, and `Reset-ErpUiSession.ps1` only when expiry or corrupted session state requires a fresh login.

After setup, use `playwright-cli -s=<session>` for screen interaction. A snapshot supplies current control refs. Refs become stale after page loads and ASP.NET postbacks; refresh them before further interaction. Screen fields live in an iframe, while navigation and company controls belong to the shell.

## Choose the environment

Default to local unless the user requests internal or the session already establishes that target. Confirm the displayed company before entering data.

- For local login, company switching, or warmup, read [references/local-session.md](references/local-session.md). Local site, company, user, and coordination lock come from the machine profile.
- For internal instance discovery, mock login, or authenticated navigation, read [references/internal-session.md](references/internal-session.md).
- For screen lookup, ambiguous controls, data entry, or session recovery, read [references/screen-interaction.md](references/screen-interaction.md).

The helpers verify the configured local development user during login. For internal instances, use an already authenticated named session and follow [references/internal-session.md](references/internal-session.md); do not apply the local login flow to internal authentication.

## Parallel agents and writes

The default session is isolated by worktree, so separate worktrees do not change each other's tabs or company selection. An explicit `-Session` overrides it. Browser isolation does not isolate the configured ERP site, its deployed binaries, or ERP database writes. Run a task-owned PowerShell script through `Invoke-ErpEnvironmentExclusive.ps1` before redeploying or restarting the legacy site, changing shared setup, or saving shared records. Its mutex name comes from the machine profile and must match cooperating E2E and Oracle runners. Do not nest the wrapper around a runner that already acquires that mutex. Keep general navigation read-only unless the task authorizes the write, and keep scenario-specific write automation in its owning repository.

## Verify the requested result

The shell can appear before its screen is ready. Wait for the title to change from the shell title to the requested screen and for its content to appear; first local loads can take 30-90 seconds. Use bounded waits that leave room for progress updates. Investigate a stalled load before repeating navigation or data entry.

For screenshots, run `playwright-cli screenshot` after readiness and inspect the saved image. The default output is beneath the working directory's `.playwright-cli`; return the reported absolute path as a clickable link.

For edits, a successful save usually adds record keys to the URL. Verify the requested values persisted by reopening the record; use a targeted API or SQL check only when the UI cannot establish the result. Recovery retries must not repeat a save or action whose outcome is uncertain without checking the record first.
