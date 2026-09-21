[CmdletBinding()]
param(
    [string] $Session,
    [string] $ExpectedScreenId,
    [string] $ExpectedCompany,
    [string] $ExpectedBranch,
    [ValidateRange(5, 300)][int] $TimeoutSeconds = 90
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ErpUi.Common.ps1')

$resolvedSession = Resolve-ErpUiSessionName -Session $Session
if (-not (Test-ErpUiSession -Session $resolvedSession)) {
    throw "ERP UI session '$resolvedSession' is not open. Use Open-ErpScreen.ps1 first."
}

$configuration = @{
    expectedScreenId = $ExpectedScreenId
    expectedCompany = $ExpectedCompany
    expectedBranch = $ExpectedBranch
    timeoutMilliseconds = $TimeoutSeconds * 1000
} | ConvertTo-Json -Compress
$encoded = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($configuration))

$code = @'
async (page) => {
  const c = await page.evaluate(encoded => JSON.parse(atob(encoded)), '__ERP_UI_CONFIGURATION__');
  await page.locator('iframe[name=main]').waitFor({ state: 'attached', timeout: c.timeoutMilliseconds });
  const deadline = Date.now() + c.timeoutMilliseconds;
  let title = await page.title();
  while (title === 'Local Visma Net' && Date.now() < deadline) {
    await page.waitForTimeout(1000);
    title = await page.title();
  }
  const current = await page.evaluate(() => {
    const url = new URL(location.href);
    return { company: url.searchParams.get('CompanyID'), screenId: url.searchParams.get('ScreenId') };
  });
  const company = current.company;
  const screenId = current.screenId;
  const branch = await page.evaluate(() => {
    const selector = document.querySelector('#reactComponentDataContainer');
    return { id: selector?.dataset.branchid || null, name: document.querySelector('#branchName')?.textContent?.trim() || null };
  });
  if (title === 'Local Visma Net') throw new Error('ERP screen did not become ready before the timeout.');
  if (c.expectedCompany && company !== c.expectedCompany) throw new Error(`Wrong ERP company '${company || '<missing>'}', expected '${c.expectedCompany}'.`);
  if (c.expectedScreenId && screenId !== c.expectedScreenId) throw new Error(`Wrong ERP screen '${screenId || '<missing>'}', expected '${c.expectedScreenId}'.`);
  if (c.expectedBranch && branch.id !== String(c.expectedBranch) && (branch.name || '').toLowerCase() !== String(c.expectedBranch).toLowerCase()) throw new Error(`Wrong ERP branch '${branch.name || branch.id || '<missing>'}', expected '${c.expectedBranch}'.`);
  const frame = page.frame({ name: 'main' });
  return JSON.stringify({ title, url: page.url(), company, screenId, branch: branch.name, branchId: branch.id, iframeUrl: frame ? frame.url() : null, ready: Boolean(frame) });
}
'@
$code = $code.Replace('__ERP_UI_CONFIGURATION__', $encoded)

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
    ready = $result.ready
} | ConvertTo-Json -Depth 4
