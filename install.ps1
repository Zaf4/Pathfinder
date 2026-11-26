# Pathfinder installer for Windows 10/11.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Zaf4/Pathfinder/master/install.ps1 | iex"
#
# Installs uv (a small Python manager) and Pathfinder into your user folder, then adds
# Pathfinder to the Start menu, the desktop and Settings > Apps. No administrator rights,
# Python, conda or git needed. Run it again to update.
#
# (ASCII only, and no `exit`: this runs through `iex`, where `exit` would close the
# user's PowerShell window.)

function Install-Pathfinder {
    $ErrorActionPreference = 'Stop'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    $Repo   = 'https://github.com/Zaf4/Pathfinder'
    $Branch = if ($env:PATHFINDER_BRANCH) { $env:PATHFINDER_BRANCH } else { 'master' }
    $Source = if ($env:PATHFINDER_SOURCE) { $env:PATHFINDER_SOURCE } else { "jsl-pathfinder @ $Repo/archive/refs/heads/$Branch.zip" }
    $Py     = '3.13'
    $Raw    = "https://raw.githubusercontent.com/Zaf4/Pathfinder/$Branch"

    function Step($text) { Write-Host ''; Write-Host "==> $text" -ForegroundColor Cyan }
    function Fail($text) {
        Write-Host ''
        Write-Host "Something went wrong: $text" -ForegroundColor Red
        Write-Host 'If this keeps happening, please report it at https://github.com/Zaf4/Pathfinder/issues'
        if (-not $env:PATHFINDER_NO_PAUSE) { Read-Host 'Press Enter to close' | Out-Null }
        throw "Pathfinder install failed: $text"
    }

    Write-Host 'Installing Pathfinder...' -ForegroundColor White

    $LocalBin = Join-Path $HOME '.local\bin'
    $env:Path = "$LocalBin;$env:Path"

    Step '1/3  Getting uv (Python manager)'
    $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if ($uv) {
        Write-Host 'uv is already installed.'
    } else {
        $env:UV_NO_MODIFY_PATH = '1'
        # run in a child PowerShell so nothing in uv's installer can end this script
        & powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex" | Out-Null
        $uv = Join-Path $LocalBin 'uv.exe'
        if (-not (Test-Path $uv)) { Fail 'could not download uv. Check your internet connection.' }
    }

    Step '2/3  Installing Pathfinder (first time takes a minute)'
    $ErrorActionPreference = 'Continue'   # uv writes progress to stderr; that is not an error
    & $uv tool install --force --refresh-package jsl-pathfinder --managed-python --python $Py $Source
    $code = $LASTEXITCODE
    $BinDir = (& $uv tool dir --bin).Trim()
    $ToolDir = (& $uv tool dir).Trim()
    $ErrorActionPreference = 'Stop'
    if ($code -ne 0) { Fail 'installing Pathfinder failed (see the messages above).' }
    $Exe = Join-Path $BinDir 'pathfinder.exe'
    if (-not (Test-Path $Exe)) { Fail 'the pathfinder program is missing after install.' }

    Step '3/3  Adding Pathfinder to the Start menu and desktop'
    $Home2 = Join-Path $env:LOCALAPPDATA 'Pathfinder'
    New-Item -ItemType Directory -Force -Path $Home2 | Out-Null
    $Ico = Join-Path $Home2 'Pathfinder.ico'
    $found = Get-ChildItem -Path (Join-Path $ToolDir 'jsl-pathfinder') -Recurse -Filter 'AppIcon.ico' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { Copy-Item $found.FullName $Ico -Force }
    else { try { Invoke-WebRequest "$Raw/src/pathfinder/gui/assets/AppIcon.ico" -OutFile $Ico -UseBasicParsing } catch { } }

    $shell = New-Object -ComObject WScript.Shell
    $Programs = [Environment]::GetFolderPath('Programs')
    $Desktop  = [Environment]::GetFolderPath('Desktop')
    foreach ($dir in @($Programs, $Desktop)) {
        if (-not $dir) { continue }
        $lnk = $shell.CreateShortcut((Join-Path $dir 'Pathfinder.lnk'))
        $lnk.TargetPath = $Exe
        $lnk.WorkingDirectory = $HOME
        $lnk.Description = 'Morris Water Maze search strategy analysis'
        if (Test-Path $Ico) { $lnk.IconLocation = "$Ico,0" }
        $lnk.Save()
    }

    # Settings > Apps entry so it can be removed like any other program
    $Uninstaller = Join-Path $Home2 'uninstall.ps1'
    try { Invoke-WebRequest "$Raw/uninstall.ps1" -OutFile $Uninstaller -UseBasicParsing } catch { }
    $Version = ''
    $ErrorActionPreference = 'Continue'
    $line = (& $uv tool list 2>$null) | Where-Object { $_ -match '^jsl-pathfinder ' } | Select-Object -First 1
    $ErrorActionPreference = 'Stop'
    if ($line) { $Version = ($line -split ' ')[1].TrimStart('v') }
    $Key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Pathfinder'
    New-Item -Path $Key -Force | Out-Null
    $props = @{
        DisplayName     = 'Pathfinder'
        DisplayVersion  = $Version
        Publisher       = 'Pathfinder (Snyder Lab method, community build)'
        DisplayIcon     = $Ico
        InstallLocation = $Home2
        URLInfoAbout    = $Repo
        UninstallString = "powershell -NoProfile -ExecutionPolicy ByPass -File `"$Uninstaller`""
    }
    foreach ($k in $props.Keys) { Set-ItemProperty -Path $Key -Name $k -Value $props[$k] }
    Set-ItemProperty -Path $Key -Name NoModify -Value 1 -Type DWord
    Set-ItemProperty -Path $Key -Name NoRepair -Value 1 -Type DWord

    Write-Host ''
    Write-Host 'Pathfinder is installed.' -ForegroundColor Green
    Write-Host '  Open it from the Start menu or the Pathfinder icon on your desktop.'
    Write-Host '  Your results will be saved in the "Pathfinder Results" folder in your user folder.'
    Write-Host '  To update later, use Help > Check for Updates (or run this same command again).'

    if (-not $env:PATHFINDER_NO_OPEN) { Start-Process -FilePath $Exe -WorkingDirectory $HOME }
}

try { Install-Pathfinder } catch { Write-Host $_ -ForegroundColor Red }
