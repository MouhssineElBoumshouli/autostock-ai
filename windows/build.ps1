# Builds build\AutoStock-Setup.exe on Windows. Run from the repository's root:
#   powershell -ExecutionPolicy Bypass -File windows\build.ps1
# Needs: Python 3.12, Node.js, Inno Setup 6, and PostgreSQL 16 or newer installed (its programs are
# copied into the app; GitHub's Windows machines already have all of these).
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
New-Item -ItemType Directory -Force build | Out-Null

Write-Host "1/5 Website"
Push-Location frontend
npm ci --no-audit --no-fund
npm run build
Pop-Location

Write-Host "2/5 Python packages"
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt pyinstaller==6.16.0 tzdata

Write-Host "3/5 PostgreSQL's programs"
$pgBin = if ($env:PGBIN) { $env:PGBIN } else { (Get-ChildItem "C:\Program Files\PostgreSQL\*\bin" | Sort-Object FullName -Descending | Select-Object -First 1).FullName }
if (-not $pgBin -or -not (Test-Path "$pgBin\pg_ctl.exe")) { throw "PostgreSQL was not found. Install PostgreSQL 16 or newer first." }
$pgHome = Split-Path $pgBin -Parent
Remove-Item -Recurse -Force build\pgsql -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force build\pgsql | Out-Null
foreach ($part in "bin", "lib", "share") {
  Copy-Item -Recurse "$pgHome\$part" "build\pgsql\$part"
}
# Not needed to run a shop: the graphical admin tool, debug symbols, documentation.
Remove-Item -Recurse -Force build\pgsql\bin\pgAdmin*, build\pgsql\share\doc -ErrorAction SilentlyContinue
Get-ChildItem build\pgsql -Recurse -Include *.pdb | Remove-Item -Force
& "build\pgsql\bin\postgres.exe" --version

Write-Host "4/5 AutoStock.exe"
python -m PyInstaller --noconfirm --clean --distpath build\dist --workpath build\work windows\autostock.spec

Write-Host "5/5 Installer"
$version = if ($env:APP_VERSION) { $env:APP_VERSION } else { "1.0.0" }
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 was not found." }
& $iscc "/DAppVersion=$version" windows\installer.iss
if ($LASTEXITCODE -ne 0) { throw "The installer could not be built." }
Get-Item build\AutoStock-Setup.exe | Format-List Name, Length
