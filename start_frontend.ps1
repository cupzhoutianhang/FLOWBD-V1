param([int]$Port = 8510, [string]$Python = 'python')
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
# Source checks are on: suspect values are marked in place and listed in a
# closing declaration. They no longer turn the whole answer into a refusal.
$env:FLOWBD_STRICT_GROUNDING = '1'
$frontendEntry = Join-Path $PSScriptRoot 'frontend_app.py'
Push-Location $PSScriptRoot
try {
    & $Python -m streamlit run $frontendEntry --server.port $Port --server.headless true --browser.gatherUsageStats false --theme.primaryColor '#0071e3' --theme.backgroundColor '#f5f5f7' --theme.secondaryBackgroundColor '#ffffff' --theme.textColor '#1d1d1f'
} finally {
    Pop-Location
}
