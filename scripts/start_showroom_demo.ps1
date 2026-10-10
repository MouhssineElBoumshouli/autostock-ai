[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
$showroomDatabase = "autostock_showroom_demo"
$showroomProject = "autostock-showroom-demo"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $repoRoot "compose.showroom.yml"
$showroomDirectory = Join-Path $repoRoot ".showroom"
$environmentFile = Join-Path $showroomDirectory ".env"
$odooConfigFile = Join-Path $showroomDirectory "odoo.conf"
$credentialsFile = Join-Path $showroomDirectory "credentials.txt"

function Get-ShowroomEnvironment {
    $values = @{}
    if (Test-Path -LiteralPath $environmentFile) {
        foreach ($line in Get-Content -LiteralPath $environmentFile) {
            if ($line -match '^([A-Z_]+)=(.*)$') {
                $values[$Matches[1]] = $Matches[2]
            }
        }
    }
    return $values
}

function Get-RandomPassword {
    $bytes = New-Object byte[] 36
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Write-ShowroomEnvironment($values) {
    $contents = @(
        "SHOWROOM_POSTGRES_USER=$($values.SHOWROOM_POSTGRES_USER)"
        "SHOWROOM_POSTGRES_PASSWORD=$($values.SHOWROOM_POSTGRES_PASSWORD)"
        "SHOWROOM_ADMIN_PASSWORD=$($values.SHOWROOM_ADMIN_PASSWORD)"
        "SHOWROOM_MASTER_PASSWORD=$($values.SHOWROOM_MASTER_PASSWORD)"
        "AUTOSTOCK_SHOWROOM_PORT=$($values.AUTOSTOCK_SHOWROOM_PORT)"
        ""
    ) -join "`n"
    [System.IO.File]::WriteAllText($environmentFile, $contents, (New-Object System.Text.UTF8Encoding($false)))
}

function Write-ShowroomConfiguration($values) {
    $contents = @(
        "[options]"
        "admin_passwd = $($values.SHOWROOM_MASTER_PASSWORD)"
        "dbfilter = ^$showroomDatabase`$"
        "addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons,/usr/lib/python3/dist-packages/addons"
        "http_interface = 0.0.0.0"
        ""
    ) -join "`n"
    [System.IO.File]::WriteAllText($odooConfigFile, $contents, (New-Object System.Text.UTF8Encoding($false)))

    $url = "http://localhost:$($values.AUTOSTOCK_SHOWROOM_PORT)/web?db=$showroomDatabase"
    $credentials = @(
        "AutoStock AI local showroom login"
        "URL=$url"
        "Database=$showroomDatabase"
        "Login=admin"
        "Password=$($values.SHOWROOM_ADMIN_PASSWORD)"
        ""
        "Local fictional demonstration data only. Keep this file private and do not commit it."
        ""
    ) -join "`n"
    [System.IO.File]::WriteAllText($credentialsFile, $credentials, (New-Object System.Text.UTF8Encoding($false)))
}

function Invoke-ShowroomCompose {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$CaptureOutput
    )
    $composeArguments = @(
        "compose", "--project-name", $showroomProject,
        "--env-file", $environmentFile,
        "--file", $composeFile
    ) + $Arguments
    if ($CaptureOutput) {
        $result = & docker @composeArguments
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            throw "Docker Compose failed with exit code $exitCode."
        }
        return ($result -join "`n").Trim()
    }
    & docker @composeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed with exit code $LASTEXITCODE."
    }
}

function Test-LocalPortAvailable([int]$port) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    try {
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

function Get-AvailableShowroomPort {
    foreach ($candidate in 8177..8190) {
        if (Test-LocalPortAvailable $candidate) {
            return $candidate
        }
    }
    throw "Ports 8177–8190 are in use. Stop an existing local service and try again. No other service was changed."
}

if (-not (Test-Path -LiteralPath $composeFile)) {
    throw "The showroom Compose file is missing: $composeFile"
}

if ($Stop) {
    if (Test-Path -LiteralPath $environmentFile) {
        Invoke-ShowroomCompose -Arguments @("down")
        Write-Host "Showroom services stopped. The showroom database and its dedicated volumes were retained."
    }
    else {
        Write-Host "The local showroom has not been configured yet. Nothing was changed."
    }
    return
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required. Install it, enable its WSL2 engine, and retry this command."
}
& docker info --format "{{.ServerVersion}}" *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running. Start Docker Desktop with its WSL2 engine, then retry."
}

New-Item -ItemType Directory -Path $showroomDirectory -Force | Out-Null
$environment = Get-ShowroomEnvironment
$requiredKeys = @(
    "SHOWROOM_POSTGRES_USER",
    "SHOWROOM_POSTGRES_PASSWORD",
    "SHOWROOM_ADMIN_PASSWORD",
    "SHOWROOM_MASTER_PASSWORD",
    "AUTOSTOCK_SHOWROOM_PORT"
)
$hasCompleteEnvironment = $true
foreach ($key in $requiredKeys) {
    if (-not $environment.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($environment[$key])) {
        $hasCompleteEnvironment = $false
    }
}

if (-not $hasCompleteEnvironment) {
    $volumeInspection = & docker volume inspect autostock_ai_showroom_postgres 2>$null
    if ($LASTEXITCODE -eq 0 -and $volumeInspection) {
        throw "The showroom database volume exists but its local credentials file is incomplete. Restore .showroom/.env from a private backup or remove the exact showroom database using your approved recovery procedure; this script will not replace credentials or delete data."
    }
    $environment = @{
        SHOWROOM_POSTGRES_USER = "autostock_showroom"
        SHOWROOM_POSTGRES_PASSWORD = Get-RandomPassword
        SHOWROOM_ADMIN_PASSWORD = Get-RandomPassword
        SHOWROOM_MASTER_PASSWORD = Get-RandomPassword
        AUTOSTOCK_SHOWROOM_PORT = Get-AvailableShowroomPort
    }
}

$runningServices = ""
if (Test-Path -LiteralPath $environmentFile) {
    try {
        $runningServices = Invoke-ShowroomCompose -Arguments @("ps", "--status", "running", "--services") -CaptureOutput
    }
    catch {
        $runningServices = ""
    }
}
if ($runningServices -notmatch '(^|\s)odoo(\s|$)' -and -not (Test-LocalPortAvailable ([int]$environment.AUTOSTOCK_SHOWROOM_PORT))) {
    $environment.AUTOSTOCK_SHOWROOM_PORT = Get-AvailableShowroomPort
}
Write-ShowroomEnvironment $environment
Write-ShowroomConfiguration $environment

if ($Reset) {
    $confirmation = Read-Host "This removes only the database '$showroomDatabase' from the dedicated local showroom PostgreSQL service. Type the database name to continue"
    if ($confirmation -cne $showroomDatabase) {
        throw "Reset cancelled. The showroom database and all other services were left untouched."
    }
    Invoke-ShowroomCompose -Arguments @("up", "-d", "--wait", "--wait-timeout", "60", "db")
    Invoke-ShowroomCompose -Arguments @("stop", "odoo")
    Invoke-ShowroomCompose -Arguments @(
        "exec", "-T", "db", "psql", "-U", $environment.SHOWROOM_POSTGRES_USER,
        "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$showroomDatabase' AND pid <> pg_backend_pid();"
    ) | Out-Null
    Invoke-ShowroomCompose -Arguments @(
        "exec", "-T", "db", "psql", "-U", $environment.SHOWROOM_POSTGRES_USER,
        "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", "DROP DATABASE IF EXISTS autostock_showroom_demo;"
    ) | Out-Null
}

Invoke-ShowroomCompose -Arguments @("up", "-d", "--wait", "--wait-timeout", "60", "db")
$databaseExists = Invoke-ShowroomCompose -Arguments @(
    "exec", "-T", "db", "psql", "-U", $environment.SHOWROOM_POSTGRES_USER,
    "-d", "postgres", "-tAc", "SELECT 1 FROM pg_database WHERE datname = 'autostock_showroom_demo';"
) -CaptureOutput
$databaseExists = $databaseExists.Trim()

if ($databaseExists -ne "1") {
    Write-Host "Installing Odoo 19, Inventory, Sales and AutoStock AI in the isolated showroom database..."
    Invoke-ShowroomCompose -Arguments @(
        "run", "--build", "--rm", "--no-deps", "odoo",
        "--database=autostock_showroom_demo",
        "--init=autostock_ai",
        "--stop-after-init",
        "--without-demo=true",
        "--log-level=warn"
    )
}
else {
    $addonState = Invoke-ShowroomCompose -Arguments @(
        "exec", "-T", "db", "psql", "-U", $environment.SHOWROOM_POSTGRES_USER,
        "-d", $showroomDatabase, "-tAc",
        "SELECT state FROM ir_module_module WHERE name = 'autostock_ai' LIMIT 1;"
    ) -CaptureOutput
    if ($addonState.Trim() -ne "installed") {
        Write-Host "Finishing AutoStock AI installation in the existing showroom database..."
        Invoke-ShowroomCompose -Arguments @(
            "run", "--build", "--rm", "--no-deps", "odoo",
            "--database=autostock_showroom_demo",
            "--init=autostock_ai",
            "--stop-after-init",
            "--without-demo=true",
            "--log-level=warn"
        )
    }
    else {
        Invoke-ShowroomCompose -Arguments @(
            "run", "--build", "--rm", "--no-deps", "odoo",
            "--database=autostock_showroom_demo",
            "--update=autostock_ai",
            "--stop-after-init",
            "--log-level=warn"
        )
    }
}

Invoke-ShowroomCompose -Arguments @("up", "-d", "odoo")
Write-Host "Preparing the fictional Atlas Auto Distribution showroom and real Odoo sales/delivery history..."
$seedSource = Get-Content -LiteralPath (Join-Path $repoRoot "scripts\seed_showroom_demo.py") -Raw
$seedComposeArguments = @(
    "compose", "--project-name", $showroomProject,
    "--env-file", $environmentFile,
    "--file", $composeFile,
    "run", "--rm", "-T", "--no-deps", "odoo", "odoo", "shell",
    "--database=autostock_showroom_demo", "--no-http"
)
$seedSource | & docker @seedComposeArguments
if ($LASTEXITCODE -ne 0) {
    throw "The guarded showroom seed failed with exit code $LASTEXITCODE. Its database and volumes were retained for diagnosis."
}
Invoke-ShowroomCompose -Arguments @("restart", "odoo")

$port = [int]$environment.AUTOSTOCK_SHOWROOM_PORT
$url = "http://localhost:$port/web?db=$showroomDatabase"
$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 4
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            $ready = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ready) {
    Invoke-ShowroomCompose -Arguments @("logs", "--tail", "80", "odoo")
    throw "Odoo did not become ready at $url. The isolated showroom data remains in place for diagnosis."
}

Write-Host ""
Write-Host "AutoStock AI showroom is ready."
Write-Host "  Open:       $url"
Write-Host "  Database:   $showroomDatabase"
Write-Host "  Login:      admin"
Write-Host "  Password:   saved privately in $credentialsFile"
Write-Host "  Stop later: .\scripts\start_showroom_demo.ps1 -Stop (keeps the database)"
Write-Host "  Reset only: .\scripts\start_showroom_demo.ps1 -Reset (asks for the exact database name)"
Start-Process $url
