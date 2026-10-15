param(
    [ValidateSet("Prepare", "Start", "Status", "RuntimeStatus", "DryRun")]
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

function Assert-WebServiceHealthy {
    $webContainerId = (& docker @((Get-ComposeArgs) + @("ps", "-q", "web")) | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0 -or -not $webContainerId) {
        throw "Moroccan Odoo web container is missing."
    }
    $stateJson = & docker inspect --format "{{json .State}}" $webContainerId
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect Moroccan Odoo runtime state." }
    $state = ($stateJson -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $state.Running -or $state.Restarting -or $state.Status -ne "running") {
        throw "Moroccan Odoo web container is not stably running."
    }
    if ($null -eq $state.Health -or $state.Health.Status -ne "healthy") {
        throw "Moroccan Odoo web health check is not healthy."
    }
}

function Invoke-IsolationContract(
    [string]$Mode,
    [object]$Evidence,
    [string]$TargetUuid,
    [string[]]$TargetContainerIds = @(),
    [switch]$AllowSharedWebImage
) {
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
        if ($AllowSharedWebImage) {
            $pythonArgs += "--allow-shared-web-image"
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

function Assert-NewEnvironmentIsolated([switch]$AllowSharedWebImage) {
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
        $command = @()
        if ($null -ne $service.command) {
            $command = @($service.command | ForEach-Object { [string]$_ })
        }
        $healthcheckTest = @()
        if ($null -ne $service.healthcheck -and $null -ne $service.healthcheck.test) {
            $healthcheckTest = @($service.healthcheck.test | ForEach-Object { [string]$_ })
        }
        $environmentKeys = @()
        if ($null -ne $service.environment) {
            $environmentKeys = @($service.environment.PSObject.Properties.Name)
        }
        $serviceEvidence[$serviceProperty.Name] = @{
            image = $service.image
            volumes = $mounts
            networks = $serviceNetworks
            ports = $ports
            command = $command
            healthcheck_test = $healthcheckTest
            environment_keys = $environmentKeys
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
            image = $container.Config.Image
            labels = $container.Config.Labels
            mounts = @($container.Mounts | ForEach-Object {
                @{ Type = $_.Type; Name = $_.Name; Source = $_.Source; Destination = $_.Destination; RW = [bool]$_.RW }
            })
            networks = @($container.NetworkSettings.Networks.PSObject.Properties.Name)
        }
        Invoke-IsolationContract -Mode "container" -Evidence $containerEvidence -TargetUuid $targetUuid -AllowSharedWebImage:$AllowSharedWebImage
    }

    if ($networkExists) {
        $attachedContainerIds = @()
        # Compose run --rm disconnects its short-lived Odoo helper containers
        # as it exits. Docker can briefly retain an endpoint in network inspect
        # while that removal is completing. Wait a bounded time for that stale
        # observation to settle; do not add unvalidated containers to the
        # allow-list, and still fail closed if any unmatched endpoint remains.
        for ($attempt = 0; $attempt -lt 6; $attempt++) {
            $networkJson = & docker network inspect $expectedNetwork
            if ($LASTEXITCODE -ne 0) { throw "Could not inspect the existing Moroccan network." }
            $network = (($networkJson -join [Environment]::NewLine) | ConvertFrom-Json)[0]
            $attachedContainerIds = @()
            if ($network.Containers) {
                $attachedContainerIds = @($network.Containers.PSObject.Properties.Name)
            }
            $unmatched = @($attachedContainerIds | Where-Object { $_ -notin $targetContainerIds })
            if ($unmatched.Count -eq 0 -or $attempt -eq 5) { break }
            Write-Host "Waiting for Docker to finish detaching a temporary Compose endpoint ($($unmatched.Count) unmatched)."
            Start-Sleep -Seconds 1
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
        # Permit only the exact previous shared web-image tag during this
        # pre-build migration check. Mounts, UUIDs, volumes and network remain strict.
        Assert-NewEnvironmentIsolated -AllowSharedWebImage
        Invoke-Compose @("up", "--detach", "--wait", "--build", "db", "web")
        # After the rebuild/recreate, require the dedicated Moroccan image strictly.
        Assert-NewEnvironmentIsolated
        Assert-WebServiceHealthy
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
    "RuntimeStatus" {
        if (-not (Test-Path -LiteralPath $envPath)) {
            throw "Moroccan private environment file is not prepared."
        }
        Assert-NewEnvironmentIsolated
        Assert-WebServiceHealthy
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
