# Local sessions

| Purpose | URL |
|---|---|
| Screen | `<erpUiBaseUrl>/Main?ScreenId=<SCREENID>` |
| Login with return | `<erpUiBaseUrl>/Frames/Login.aspx?ReturnUrl=<encoded-screen-path>` |

After loading, the app adds `CompanyID` and record keys to the URL.

## Login and company

The local development site prefills the configured `erpUser` and has no password field. The native company select is `#cmbCompany`; the default company comes from `erpCompany` in the machine profile unless another company is requested.

Selecting a company causes a full ASP.NET postback. Take a fresh snapshot, verify the selected option, then click Sign In using the new ref. A warning about a non-unique company key is a known local-data issue; it need not block another company's login. If it names the requested company, investigate rather than silently choosing a different target.

The top-right Select company / Select branch controls use react-select. Fill the combobox to filter options; selecting a branch triggers the switch. Re-authentication can silently retain the old company. Verify the top-right label and URL `CompanyID` after switching. If needed, sign out and log in fresh:

```powershell
playwright-cli goto "<erpUiBaseUrl>/Frames/Logout.aspx"
playwright-cli goto "<erpUiBaseUrl>/Frames/Login.aspx?ReturnUrl=<encoded-screen-path>"
```

## Warmup

First load can take 30–90 seconds. The title changes from `Local Visma Net` to the screen name when the iframe loads. A bounded check:

```powershell
playwright-cli run-code "async (page) => { for (let i = 0; i < 6 && (await page.title()) === 'Local Visma Net'; i++) await page.waitForTimeout(5000); return { title: await page.title(), url: page.url() }; }"
```

Allow the remaining warmup time if needed. If still stalled after roughly 90 seconds, a single reload and another bounded readiness check can distinguish warmup from a failed load. Do not reload unsaved work without accounting for its loss.
