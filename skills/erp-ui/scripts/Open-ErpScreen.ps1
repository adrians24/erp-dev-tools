[CmdletBinding(DefaultParameterSetName = 'Alias')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Alias')]
    [string] $Screen,

    [Parameter(Mandatory, ParameterSetName = 'Id')]
    [string] $ScreenId,

    [System.Collections.IDictionary] $Keys = @{},

    [string] $Company,

    [string] $Branch,

    [string] $BaseUrl,

    [string] $Session,

    [ValidateRange(10, 300)]
    [int] $TimeoutSeconds = 90,

    [switch] $NewTab,

    [switch] $BuildUrlOnly
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ErpUi.Common.ps1')
$profileModule = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\scripts\ErpDevTools.Profile.ps1'))
. $profileModule
$machineProfile = Get-ErpDevToolsProfile -Name local
if (!$PSBoundParameters.ContainsKey('Company')) {
    $Company = [Environment]::GetEnvironmentVariable('VISMA_ERP_COMPANY', 'Process')
    if ([string]::IsNullOrWhiteSpace($Company)) {
        $Company = Get-ErpDevToolsProfileValue -Profile $machineProfile -Name erpCompany -Required -ProfileName local
    }
}
if (!$PSBoundParameters.ContainsKey('BaseUrl')) {
    $BaseUrl = [Environment]::GetEnvironmentVariable('VISMA_ERP_UI_BASE_URL', 'Process')
    if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
        $BaseUrl = Get-ErpDevToolsProfileValue -Profile $machineProfile -Name erpUiBaseUrl -Required -ProfileName local
    }
}
$expectedLocalUser = [Environment]::GetEnvironmentVariable('VISMA_ERP_UI_USER', 'Process')
if ([string]::IsNullOrWhiteSpace($expectedLocalUser)) {
    $expectedLocalUser = Get-ErpDevToolsProfileValue -Profile $machineProfile -Name erpUser -Required -ProfileName local
}

$navigationTimer = [System.Diagnostics.Stopwatch]::StartNew()
function Write-ErpNavigationStage([string] $Message) {
    Write-Verbose ('[{0,6:N1}s] {1}' -f $navigationTimer.Elapsed.TotalSeconds, $Message)
}

Write-ErpNavigationStage 'Resolving ERP screen, session, and target URL.'
$definition = Resolve-ErpScreenDefinition -Screen $Screen -ScreenId $ScreenId
$resolvedSession = Resolve-ErpUiSessionName -Session $Session
$targetUrl = New-ErpScreenUrl -BaseUrl $BaseUrl -Company $Company -ScreenId $definition.ScreenId -Keys $Keys

if ($BuildUrlOnly) {
    [pscustomobject]@{
        session = $resolvedSession
        screen = $definition.Alias
        screenId = $definition.ScreenId
        title = $definition.Title
        keyHints = $definition.KeyHints
        company = $Company
        branch = $Branch
        keys = $Keys
        url = $targetUrl
        ready = $false
        browserOpened = $false
        elapsedSeconds = [Math]::Round($navigationTimer.Elapsed.TotalSeconds, 3)
    } | ConvertTo-Json -Depth 5
    exit 0
}

Write-ErpNavigationStage "Checking Playwright session '$resolvedSession'."
$sessionExists = Test-ErpUiSession -Session $resolvedSession
$browserOpened = -not $sessionExists
if ($sessionExists -and $Branch) {
    Write-ErpNavigationStage "Checking whether the active ERP branch already matches '$Branch'."
    $branchProbeCode = @'
async (page) => JSON.stringify(await page.evaluate(() => {
  const selector = document.querySelector('#reactComponentDataContainer');
  let companies = [];
  try { companies = JSON.parse(selector?.dataset.companiesbranches || '[]'); } catch {}
  const companyId = selector?.dataset.odpcompanyid || null;
  const branchId = selector?.dataset.branchid || null;
  const company = companies.find(x => String(x.companyid) === String(companyId));
  const branch = company?.branches?.find(x => String(x.branchid) === String(branchId));
  return {
    branchId,
    branchName: branch?.branchname || document.querySelector('#branchName')?.textContent?.trim() || null,
    availableBranches: (company?.branches || []).map(x => ({ id: String(x.branchid), name: x.branchname }))
  };
}))
'@
    $resetForBranch = $true
    try {
        $branchProbe = ConvertFrom-PlaywrightCodeResult -Response (Invoke-ErpPlaywright -Session $resolvedSession -Arguments @('run-code', $branchProbeCode))
        $requestedBranch = @($branchProbe.availableBranches | Where-Object {
            [string]$_.id -eq [string]$Branch -or
            ([string]$_.name).Equals([string]$Branch, [System.StringComparison]::OrdinalIgnoreCase)
        } | Select-Object -First 1)
        if ($requestedBranch.Count -eq 0) {
            $available = @($branchProbe.availableBranches | ForEach-Object { "$($_.name) ($($_.id))" }) -join ', '
            throw "ERP branch '$Branch' is unavailable for '$Company'. Available: $(if ($available) { $available } else { '<none>' })."
        }
        $resetForBranch = [string]$branchProbe.branchId -ne [string]$requestedBranch[0].id
    }
    catch {
        if ($_.Exception.Message -like "ERP branch '$Branch' is unavailable*") { throw }
        Write-ErpNavigationStage 'The existing session has no usable ERP branch context.'
    }

    if ($resetForBranch) {
        Write-ErpNavigationStage 'Resetting the browser session so the requested branch is selected during local login.'
        $null = Invoke-ErpPlaywright -Session $resolvedSession -Arguments @('close')
        $sessionExists = $false
        $browserOpened = $true
    }
}
if ($sessionExists) {
    $navigationCommand = if ($NewTab) { 'tab-new' } else { 'goto' }
    Write-ErpNavigationStage "Reusing the session with '$navigationCommand'."
    $null = Invoke-ErpPlaywright -Session $resolvedSession -Arguments @($navigationCommand, $targetUrl)
}
else {
    Write-ErpNavigationStage 'Opening a new browser session.'
    $null = Invoke-ErpPlaywright -Session $resolvedSession -Arguments @('open', $targetUrl)
}

$expectedKeys = [ordered]@{}
foreach ($key in @($Keys.Keys | Sort-Object)) {
    if ($null -ne $Keys[$key]) {
        $expectedKeys[[string]$key] = [string]$Keys[$key]
    }
}

$configuration = @{
    targetUrl = $targetUrl
    loginUrl = Get-ErpLoginUrl -BaseUrl $BaseUrl -TargetUrl $targetUrl
    logoutUrl = $BaseUrl.TrimEnd('/') + '/Frames/Logout.aspx'
    company = $Company
    expectedLocalUser = $expectedLocalUser
    branch = $Branch
    screenId = $definition.ScreenId
    expectedKeys = $expectedKeys
    timeoutMilliseconds = $TimeoutSeconds * 1000
} | ConvertTo-Json -Compress
$encoded = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($configuration))

Write-ErpNavigationStage 'Verifying login, company, branch, screen, and record keys.'
$code = @'
async (page) => {
  const c = await page.evaluate(encoded => JSON.parse(atob(encoded)), '__ERP_UI_CONFIGURATION__');
  const resolveLoginCompanyOption = async () => {
    const company = page.locator('#cmbCompany');
    const options = await company.locator('option').evaluateAll(items => items.map(x => ({
      text: (x.textContent || '').trim(),
      value: x.value
    })));
    if (!c.branch) {
      const option = options.find(x => x.text === c.company);
      if (!option) throw new Error(`ERP company '${c.company}' is unavailable on the login page.`);
      return option.text;
    }
    const expectedLabels = [String(c.branch), `${c.company} - ${c.branch}`];
    const branch = options.find(x =>
      expectedLabels.some(label => x.text.toLowerCase() === label.toLowerCase()) ||
      (x.value.endsWith(`;${c.branch}`) && (x.text === c.company || x.text.startsWith(`${c.company} - `)))
    );
    if (!branch) throw new Error(`ERP branch '${c.branch}' is unavailable for '${c.company}' on the login page.`);
    return branch.text;
  };
  const login = async (companyOptionLabel) => {
    let company = page.locator('#cmbCompany');
    await company.waitFor({ state: 'visible', timeout: c.timeoutMilliseconds });
    const user = page.getByRole('textbox', { name: 'My Username' });
    if (await user.count()) {
      const value = await user.inputValue();
      if (value !== c.expectedLocalUser) throw new Error(`Unexpected local ERP user '${value}'.`);
    }
    const selected = await company.locator('option:checked').textContent();
    if ((selected || '').trim() !== companyOptionLabel) {
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: c.timeoutMilliseconds }),
        company.selectOption({ label: companyOptionLabel })
      ]);
      company = page.locator('#cmbCompany');
      await company.waitFor({ state: 'visible', timeout: c.timeoutMilliseconds });
    }
    if ((await company.locator('option:checked').textContent() || '').trim() !== companyOptionLabel) {
      throw new Error(`Could not select ERP company/branch '${companyOptionLabel}'.`);
    }
    await page.getByRole('button', { name: 'Sign In', exact: true }).click();
    await page.locator('iframe[name=main]').waitFor({ state: 'attached', timeout: c.timeoutMilliseconds });
  };
  const onLogin = async () => await page.locator('#cmbCompany').count() > 0;
  const waitReady = async () => {
    await page.locator('iframe[name=main]').waitFor({ state: 'attached', timeout: c.timeoutMilliseconds });
    const deadline = Date.now() + c.timeoutMilliseconds;
    let title = await page.title();
    while (title === 'Local Visma Net' && Date.now() < deadline) {
      await page.waitForTimeout(1000);
      title = await page.title();
    }
    if (title === 'Local Visma Net') throw new Error(`ERP screen did not finish loading within ${c.timeoutMilliseconds / 1000} seconds.`);
    return title;
  };

  let loginPerformed = false;
  if (await onLogin()) {
    await login(await resolveLoginCompanyOption());
    loginPerformed = true;
  }
  if (loginPerformed) {
    // Local login strips record keys, so restore the exact target once after authentication.
    await page.goto(c.targetUrl, { waitUntil: 'domcontentloaded' });
  }

  await waitReady();
  const readLocation = async () => await page.evaluate((state) => {
    const current = new URL(location.href);
    const keys = {};
    for (const name of state.keyNames) keys[name] = current.searchParams.get(name);
    const selector = document.querySelector('#reactComponentDataContainer');
    let companies = [];
    try { companies = JSON.parse(selector?.dataset.companiesbranches || '[]'); } catch {}
    const companyId = selector?.dataset.odpcompanyid || null;
    const branchId = selector?.dataset.branchid || null;
    const company = companies.find(x => String(x.companyid) === String(companyId) || x.name === state.company);
    const branch = company?.branches?.find(x => String(x.branchid) === String(branchId));
    return {
      company: current.searchParams.get('CompanyID'),
      screenId: current.searchParams.get('ScreenId'),
      keys,
      branchId,
      branchName: branch?.branchname || document.querySelector('#branchName')?.textContent?.trim() || null,
      availableBranches: (company?.branches || []).map(x => ({ id: String(x.branchid), name: x.branchname })),
      selectorServiceUrl: selector?.dataset.selectorserviceurl || null,
      companyId
    };
  }, { keyNames: Object.keys(c.expectedKeys), company: c.company });
  let current = await readLocation();
  if (current.company !== c.company) {
    await page.goto(c.logoutUrl, { waitUntil: 'domcontentloaded' });
    await page.goto(c.loginUrl, { waitUntil: 'domcontentloaded' });
    await login(await resolveLoginCompanyOption());
    await page.goto(c.targetUrl, { waitUntil: 'domcontentloaded' });
    await waitReady();
    current = await readLocation();
  }

  const actualCompany = current.company;
  const actualScreen = current.screenId;
  if (actualCompany !== c.company) throw new Error(`Wrong ERP company '${actualCompany || '<missing>'}', expected '${c.company}'.`);
  if (actualScreen !== c.screenId) throw new Error(`Wrong ERP screen '${actualScreen || '<missing>'}', expected '${c.screenId}'.`);
  let expectedBranch = null;
  if (c.branch) {
    expectedBranch = current.availableBranches.find(x => x.id === String(c.branch) || x.name.toLowerCase() === String(c.branch).toLowerCase());
    if (!expectedBranch) {
      const available = current.availableBranches.map(x => `${x.name} (${x.id})`).join(', ');
      throw new Error(`ERP branch '${c.branch}' is unavailable for '${c.company}'. Available: ${available || '<none>'}.`);
    }
    if (current.branchId !== expectedBranch.id) {
      throw new Error(`Wrong ERP branch '${current.branchName || current.branchId || '<missing>'}', expected '${expectedBranch.name}'. Reset the named Playwright session and retry.`);
    }
    if (current.branchId !== expectedBranch.id) throw new Error(`Wrong ERP branch '${current.branchName || current.branchId || '<missing>'}', expected '${expectedBranch.name}'.`);
  }
  for (const [name, expected] of Object.entries(c.expectedKeys)) {
    const actual = current.keys[name];
    if (actual !== expected) throw new Error(`Wrong ERP record key '${name}=${actual || '<missing>'}', expected '${expected}'.`);
  }
  const frame = page.frame({ name: 'main' });
  if (!frame) throw new Error('ERP main iframe is unavailable after readiness completed.');

  return JSON.stringify({
    title: await page.title(),
    url: page.url(),
    company: actualCompany,
    screenId: actualScreen,
    branch: current.branchName,
    branchId: current.branchId,
    keys: current.keys,
    iframeUrl: frame.url(),
    ready: true
  });
}
'@
$code = $code.Replace('__ERP_UI_CONFIGURATION__', $encoded)

$response = Invoke-ErpPlaywright -Session $resolvedSession -Arguments @('run-code', $code)
$result = ConvertFrom-PlaywrightCodeResult -Response $response
Write-ErpNavigationStage 'ERP screen is ready.'
[pscustomobject]@{
    session = $resolvedSession
    screen = $definition.Alias
    screenId = $result.screenId
    title = $result.title
    company = $result.company
    branch = $result.branch
    branchId = $result.branchId
    keys = $result.keys
    url = $result.url
    iframeUrl = $result.iframeUrl
    ready = $result.ready
    browserOpened = $browserOpened
    elapsedSeconds = [Math]::Round($navigationTimer.Elapsed.TotalSeconds, 3)
} | ConvertTo-Json -Depth 5
