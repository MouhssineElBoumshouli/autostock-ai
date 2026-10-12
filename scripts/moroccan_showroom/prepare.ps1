param(
    [ValidateSet("Prepare", "Start", "Status", "DryRun")]
    [string]$Action = "Prepare",
    [int]$Seed = 36036
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$envPath = Join-Path $repoRoot ".env.atlas-morocco"
$composePath = Join-Path $repoRoot "compose.morocco.yml"
$project = "autostock-atlas-morocco"
$expectedVolumes = @(
    "autostock_atlas_morocco_postgres",
    "autostock_atlas_morocco_filestore"
)
$expectedNetwork = "autostock-atlas-morocco-private"
$legacyVolumes = @(
    "autostock_ai_showroom_postgres",
    "autostock_ai_showroom_filestore"
)
$legacyProject = "autostock-showroom-demo"

function New-RandomHex([int]$ByteCount) {
    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([System.BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant())
}

function Get-ComposeArgs {
    return @(
        "compose",
        "--project-name", $project,
        "--file", $composePath,
        "--env-file", $envPath
    )
}

function Invoke-Compose([string[]]$Arguments) {
    & docker @((Get-ComposeArgs) + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed with exit code $LASTEXITCODE."
    }
}

function Assert-NewEnvironmentIsolated {
    $configJson = & docker @((Get-ComposeArgs) + @("config", "--format", "json"))
    if ($LASTEXITCODE -ne 0) { throw "Unable to validate the Moroccan Compose configuration." }
    $config = ($configJson -join [Environment]::NewLine) | ConvertFrom-Json
    if ($config.name -ne $project) { throw "Compose project identity does not match the Moroccan target." }

    $volumeNames = @($config.volumes.PSObject.Properties | ForEach-Object { $_.Value.name })
    foreach ($volume in $expectedVolumes) {
        if ($volume -notin $volumeNames) { throw "Expected isolated volume is missing: $volume" }
    }
    foreach ($volume in $legacyVolumes) {
        if ($volume -in $volumeNames) { throw "Refusing to attach legacy Atlas volume: $volume" }
    }
    if ($config.services.db.ports -or $config.services.db.ports_published) {
        throw "PostgreSQL must not publish a host port."
    }
    if ($config.services.web.ports[0].published -ne "8070") {
        throw "Odoo must bind only on the isolated localhost port 8070."
    }
    if ($config.services.web.ports[0].host_ip -ne "127.0.0.1") {
        throw "Odoo must bind to localhost only."
    }
    $mountSources = @($config.services.web.volumes | ForEach-Object { $_.source })
    if ($mountSources -contains ".showroom") {
        throw "The Moroccan environment must not mount the existing showroom directory."
    }

    $uuidLine = Get-Content -LiteralPath $envPath | Where-Object { $_ -like "ATLAS_MOROCCO_TARGET_UUID=*" }
    if (@($uuidLine).Count -ne 1) { throw "Private target UUID is missing or duplicated." }
    $targetUuid = ($uuidLine -split "=", 2)[1]
    try { $null = [guid]::ParseExact($targetUuid, "D") }
    catch { throw "Private target UUID is malformed." }

    foreach ($volume in $expectedVolumes) {
        $labelsJson = & docker volume inspect --format '{{json .Labels}}' $volume 2>$null
        if ($LASTEXITCODE -eq 0) {
            $labels = ($labelsJson -join [Environment]::NewLine) | ConvertFrom-Json
            if ($labels."com.docker.compose.project" -ne $project -or
                $labels."com.autostock.target-uuid" -ne $targetUuid) {
                throw "Refusing to reuse volume $volume with a different project or target UUID."
            }
        }
    }
    $networkLabelsJson = & docker network inspect --format '{{json .Labels}}' $expectedNetwork 2>$null
    if ($LASTEXITCODE -eq 0) {
        $networkLabels = ($networkLabelsJson -join [Environment]::NewLine) | ConvertFrom-Json
        if ($networkLabels."com.docker.compose.project" -ne $project -or
            $networkLabels."com.autostock.target-uuid" -ne $targetUuid) {
            throw "Refusing to reuse an existing network with a different target identity."
        }
    }
    $targetContainers = & docker ps -aq --filter "label=com.docker.compose.project=$project"
    if ($LASTEXITCODE -ne 0) { throw "Could not verify existing target containers." }
    foreach ($containerId in @($targetContainers | Where-Object { $_ })) {
        $labelsJson = & docker inspect --format '{{json .Config.Labels}}' $containerId
        if ($LASTEXITCODE -ne 0) { throw "Could not inspect a target container." }
        $labels = ($labelsJson -join [Environment]::NewLine) | ConvertFrom-Json
        if ($labels."com.autostock.target-uuid" -ne $targetUuid) {
            throw "Refusing to reuse a target container with a different UUID."
        }
    }

    $legacyContainer = & docker ps -a --filter "label=com.docker.compose.project=$legacyProject" --format "{{.Names}}"
    if ($LASTEXITCODE -ne 0) { throw "Could not verify the legacy Compose project inventory." }
    # Listing legacy names is read-only. This script never starts, stops,
    # connects to, or modifies those containers.
    if (@($legacyContainer | Where-Object { $_ }).Count -gt 0) {
        Write-Host "Legacy Atlas containers remain separate; no connection will be made."
    }
}

switch ($Action) {
    "Prepare" {
        if (Test-Path -LiteralPath $envPath) {
            throw "Refusing to overwrite existing private credentials at .env.atlas-morocco."
        }
        $targetUuid = [guid]::NewGuid().ToString()
        $lines = @(
            "POSTGRES_USER=atlas_morocco",
            "POSTGRES_PASSWORD=$(New-RandomHex 32)",
            "ODOO_MASTER_PASSWORD=$(New-RandomHex 32)",
            "ODOO_PORT=8070",
            "ATLAS_MOROCCO_TARGET_UUID=$targetUuid"
        )
        [System.IO.File]::WriteAllLines($envPath, $lines, [System.Text.UTF8Encoding]::new($false))
        Write-Host "Private Moroccan environment credentials and target UUID prepared."
        Write-Host "Secrets are stored in the ignored .env.atlas-morocco file and are not printed."
        Write-Host "No Docker, database, or application action was performed."
    }
    "Start" {
        if (-not (Test-Path -LiteralPath $envPath)) {
            throw "Run Prepare first to create the ignored Moroccan environment file."
        }
        Assert-NewEnvironmentIsolated
        Invoke-Compose @("up", "--detach", "--wait", "db", "web")
        Write-Host "The separate Moroccan Odoo/PostgreSQL services are running at http://127.0.0.1:8070."
        Write-Host "No database was initialized and no dataset was imported."
    }
    "Status" {
        if (-not (Test-Path -LiteralPath $envPath)) {
            throw "Moroccan private environment file is not prepared."
        }
        Assert-NewEnvironmentIsolated
        Invoke-Compose @("ps")
    }
    "DryRun" {
        Push-Location $repoRoot
        try {
            python -m scripts.moroccan_showroom.cli --seed $Seed
            if ($LASTEXITCODE -ne 0) { throw "The offline dataset dry run failed." }
        }
        finally {
            Pop-Location
        }
    }
}
