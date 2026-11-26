# Remove Pathfinder from Windows (keeps your "Pathfinder Results" folder and keeps uv).
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Zaf4/Pathfinder/2.1.0/uninstall.ps1 | iex"
#
# Also used by Settings > Apps > Pathfinder > Uninstall.

$env:Path = "$(Join-Path $HOME '.local\bin');$env:Path"
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if ($uv) {
    $ErrorActionPreference = 'Continue'
    & $uv tool uninstall jsl-pathfinder 2>$null | Out-Null
}
foreach ($dir in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
    if ($dir) { Remove-Item (Join-Path $dir 'Pathfinder.lnk') -Force -ErrorAction SilentlyContinue }
}
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Pathfinder' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $env:LOCALAPPDATA 'Pathfinder') -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'Pathfinder has been removed. Your "Pathfinder Results" folder was kept.' -ForegroundColor Green
