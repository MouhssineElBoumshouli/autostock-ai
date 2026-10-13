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

function Invoke-IsolationContract([string]$Mode, [object]$Evidence, [string]$TargetUuid, [string[]]$TargetContainerIds = @()) {
    $evidencePath = Join-Path ([System.IO.Path]::GetTempPath()) ("autostock-morocco-" + [guid]::NewGuid().ToString("N") + ".json")
    try {
        $json = ConvertTo-Json -InputObject $Evidence -Depth 30
        [System.IO.File]::WriteAllText($evidencePath, $json, [System.Text.UTF8Encoding]::new($false))
        $pythonArgs = @(
            "-m", "scripts.moroccan_showroom.compose_contract",
            "--mode", $Mode,
            "--evidence-json", $evidencePath,
            "--repo-root", $repoRoot,
            "--target-uuid", $TargetUuid
        )
        foreach ($containerId in $TargetContainerIds) {
            $pythonArgs += @("--target-container-id", $containerId)
        }
        Push-Location $repoRoot
        try {
            & python @pythonArgs
            if ($LASTEXITCODE -ne 0) { throw "Moroccan $Mode isolation evidence was rejected." }
        }
        finally {
            Pop-Location
        }
    }
    finally {
        if (Test-Path -LiteralPath $evidencePath) {
            Remove-Item -LiteralPath $evidencePath -Force
        }
    }
}

function Assert-NewEnvironmentIsolated {
    $configJson = & docker @((Get-ComposeArgs) + @("config", "--format", "json"))
    if ($LASTEXITCODE -ne 0) { throw "Unable to validate the Moroccan Compose configuration." }
    $config = ($configJson -join [Environment]::NewLine) | ConvertFrom-Json

    $uuidLine = Get-Content -LiteralPath $envPath | Where-Object { $_ -like "ATLAS_MOROCCO_TARGET_UUID=*" }
    if (@($uuidLine).Count -ne 1) { throw "Private target UUID is missing or duplicated." }
    $targetUuid = ($uuidLine -split "=", 2)[1]
    try { $null = [guid]::ParseExact($targetUuid, "D") }
    catch { throw "Private target UUID is malformed." }

    # Send only the resource/mount contract to Python; resolved Compose config
    # also contains passwords, so never serialize the full object to a file.
    $serviceEvidence = @{}
    foreach ($serviceProperty in $config.services.PSObject.Properties) {
        $service = $serviceProperty.Value
        $mounts = @($service.volumes | ForEach-Object {
            @{
                type = $_.type
                source = $_.source
                target = $_.target
                read_only = [bool]$_.read_only
            }
        })
        $serviceNetworks = @{}
        foreach ($networkProperty in $service.networks.PSObject.Properties) {
            $serviceNetworks[$networkProperty.Name] = $null
        }
        # Compose omits ports for PostgreSQL. Do not pipe $null into
        # ForEach-Object: PowerShell would create a fake empty port entry.
        $ports = @()
        if ($null -ne $service.ports) {
            $ports = @($service.ports | ForEach-Object {
                if ($null -eq $_) { throw "Malformed Compose port entry." }
                @{ host_ip = $_.host_ip; published = $_.published; target = $_.target }
            })
        }
        $serviceEvidence[$serviceProperty.Name] = @{
            volumes = $mounts
            networks = $serviceNetworks
            ports = $ports
        }
    }
    $volumeEvidence = @{}
    foreach ($volumeProperty in $config.volumes.PSObject.Properties) {
        $volumeEvidence[$volumeProperty.Name] = @{ name = $volumeProperty.Value.name }
    }
    $networkEvidence = @{}
    foreach ($networkProperty in $config.networks.PSObject.Properties) {
        $networkEvidence[$networkProperty.Name] = @{
            name = $networkProperty.Value.name
            labels = $networkProperty.Value.labels
        }
    }
    $composeEvidence = @{
        name = $config.name
        services = $serviceEvidence
        volumes = $volumeEvidence
        networks = $networkEvidence
    }
    Invoke-IsolationContract -Mode "config" -Evidence $composeEvidence -TargetUuid $targetUuid

    foreach ($volume in $expectedVolumes) {
        $existingVolumes = & docker volume ls --format "{{.Name}}" --filter "name=$volume"
        if ($LASTEXITCODE -ne 0) { throw "Could not inspect Docker volumes." }
        if ($volume -in @($existingVolumes)) {
            $labelsJson = & docker volume inspect --format '{{json .Labels}}' $volume
            if ($LASTEXITCODE -ne 0) { throw "Could not inspect existing volume $volume." }
            $labels = ($labelsJson -join [Environment]::NewLine) | ConvertFrom-Json
            if ($labels."com.docker.compose.project" -ne $project -or
                $labels."com.autostock.target-uuid" -ne $targetUuid) {
                throw "Refusing to reuse volume $volume with a different project or target UUID."
            }
        }
    }
    $existingNetworks = & docker network ls --format "{{.Name}}" --filter "name=$expectedNetwork"
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect Docker networks." }
    $networkExists = $expectedNetwork -in @($existingNetworks)
    # Network inspect reports full container IDs, so collect full IDs here too.
    $targetContainers = & docker ps -aq --no-trunc --filter "label=com.docker.compose.project=$project"
    if ($LASTEXITCODE -ne 0) { throw "Could not verify existing target containers." }
    $targetContainerIds = @($targetContainers | Where-Object { $_ } | ForEach-Object { $_.Trim() })
    foreach ($containerId in $targetContainerIds) {
        $containerJson = & docker inspect $containerId
        if ($LASTEXITCODE -ne 0) { throw "Could not inspect a target container." }
        $container = (($containerJson -join [Environment]::NewLine) | ConvertFrom-Json)[0]
        $containerEvidence = @{
            name = $container.Name
            labels = $container.Config.Labels
            mounts = @($container.Mounts | ForEach-Object {
                @{ Type = $_.Type; Name = $_.Name; Source = $_.Source; Destination = $_.Destination; RW = [bool]$_.RW }
            })
            networks = @($container.NetworkSettings.Networks.PSObject.Properties.Name)
        }
        Invoke-IsolationContract -Mode "container" -Evidence $containerEvidence -TargetUuid $targetUuid
    }

    if ($networkExists) {
        $networkJson = & docker network inspect $expectedNetwork
        if ($LASTEXITCODE -ne 0) { throw "Could not inspect the existing Moroccan network." }
        $network = (($networkJson -join [Environment]::NewLine) | ConvertFrom-Json)[0]
        $attachedContainerIds = @()
        if ($network.Containers) {
            $attachedContainerIds = @($network.Containers.PSObject.Properties.Name)
        }
        $networkEvidence = @{
            name = $network.Name
            labels = $network.Labels
            container_ids = $attachedContainerIds
        }
        Invoke-IsolationContract -Mode "network" -Evidence $networkEvidence -TargetUuid $targetUuid -TargetContainerIds $targetContainerIds
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
        # Verify the actual newly running mounts/network as well as the rendered
        # Compose contract. A repeat Start follows the same fail-closed path.
        Assert-NewEnvironmentIsolated
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
