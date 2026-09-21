[CmdletBinding()]
param([string] $Session)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ErpUi.Common.ps1')

$resolvedSession = Resolve-ErpUiSessionName -Session $Session
if (-not (Test-ErpUiSession -Session $resolvedSession)) {
    throw "ERP UI session '$resolvedSession' is not open. Use Open-ErpScreen.ps1 first."
}

$code = @'
async (page) => {
  const current = await page.evaluate(() => {
    const url = new URL(location.href);
    return { company: url.searchParams.get('CompanyID'), screenId: url.searchParams.get('ScreenId') };
  });
  const frame = page.frame({ name: 'main' });
  const branch = await page.evaluate(() => {
    const selector = document.querySelector('#reactComponentDataContainer');
    return {
      id: selector?.dataset.branchid || null,
      name: document.querySelector('#branchName')?.textContent?.trim() || null
    };
  });
  return JSON.stringify({
    title: await page.title(),
    url: page.url(),
    company: current.company,
    screenId: current.screenId,
    branch: branch.name,
    branchId: branch.id,
    iframeUrl: frame ? frame.url() : null,
    loginVisible: await page.locator('#cmbCompany').count() > 0,
    ready: Boolean(frame) && (await page.title()) !== 'Local Visma Net'
  });
}
'@

$response = Invoke-ErpPlaywright -Session $resolvedSession -Arguments @('run-code', $code)
$result = ConvertFrom-PlaywrightCodeResult -Response $response
[pscustomobject]@{
    session = $resolvedSession
    title = $result.title
    url = $result.url
    company = $result.company
    screenId = $result.screenId
    branch = $result.branch
    branchId = $result.branchId
    iframeUrl = $result.iframeUrl
    loginVisible = $result.loginVisible
    ready = $result.ready
} | ConvertTo-Json -Depth 4
