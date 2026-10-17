param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Initialize", "BackupRestore", "PostApplyRestore", "DiagnosePostApply", "Apply")]
    [string]$Action,
    [string]$BackupStamp,
    [string]$TypedTargetUuid
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$envPath = Join-Path $repoRoot ".env.atlas-morocco"
$composePath = Join-Path $repoRoot "compose.morocco.yml"
$preparePath = Join-Path $PSScriptRoot "prepare.ps1"
$project = "autostock-atlas-morocco"
$database = "autostock_atlas_morocco_demo"
$filestoreVolume = "autostock_atlas_morocco_filestore"
$image = "autostock-ai-odoo-morocco:19.0"
$proofAttachmentName = "AutoStock local restore proof"
$proofAttachmentBytes = "autostock-local-independent-restore-proof-v1"
$datasetVersion = "atlas-ma-2026.4"
$expectedForecastRequests = 90

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Moroccan environment is not prepared. Do not regenerate it; restore the existing .env.atlas-morocco first."
}

function Get-PrivateEnvValue([string]$Name) {
    $lines = @(Get-Content -LiteralPath $envPath | Where-Object { $_ -like "$Name=*" })
    if ($lines.Count -ne 1) { throw "Private environment value $Name is missing or duplicated." }
    $value = ($lines[0] -split "=", 2)[1]
    if (-not $value) { throw "Private environment value $Name is empty." }
    return $value
}

$postgresUser = Get-PrivateEnvValue "POSTGRES_USER"
$targetUuid = Get-PrivateEnvValue "ATLAS_MOROCCO_TARGET_UUID"
try { $null = [guid]::ParseExact($targetUuid, "D") }
catch { throw "Private Moroccan target UUID is malformed." }

function Get-ComposeArgs {
    return @("compose", "--project-name", $project, "--file", $composePath, "--env-file", $envPath)
}

function Invoke-Compose([string[]]$Arguments) {
    & docker @((Get-ComposeArgs) + $Arguments)
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed with exit code $LASTEXITCODE." }
}

function Get-ComposeOutput([string[]]$Arguments) {
    $output = & docker @((Get-ComposeArgs) + $Arguments)
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed with exit code $LASTEXITCODE." }
    return (($output -join [Environment]::NewLine).Trim())
}

function Invoke-Docker([string[]]$Arguments) {
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker failed with exit code $LASTEXITCODE." }
}

function Get-DockerOutput([string[]]$Arguments) {
    $output = & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker failed with exit code $LASTEXITCODE." }
    return (($output -join [Environment]::NewLine).Trim())
}

function Invoke-Python([string[]]$Arguments) {
    Push-Location $repoRoot
    try {
        & python @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Python safety check failed with exit code $LASTEXITCODE." }
    }
    finally { Pop-Location }
}

function Invoke-Prepare([string]$PrepareAction) {
    & $preparePath -Action $PrepareAction
    if ($LASTEXITCODE -ne 0) { throw "Moroccan $PrepareAction check failed." }
}

function Invoke-Psql([string]$Sql, [string]$DbName = $database) {
    return Get-ComposeOutput @("exec", "-T", "db", "psql", "-U", $postgresUser, "-d", $DbName, "-Atc", $Sql)
}

function Invoke-RestorePsql([string]$Container, [string]$Sql) {
    return Get-DockerOutput @("exec", $Container, "psql", "-U", $postgresUser, "-d", $database, "-Atc", $Sql)
}

function Invoke-OdooShell([string]$Code) {
    $args = (Get-ComposeArgs) + @("run", "--rm", "--no-deps", "-T", "web", "odoo", "shell", "--database=$database", "--no-http")
    $Code | & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Odoo shell target initialization failed." }
}

function Invoke-OdooMountedScript([string]$ScriptName, [string[]]$ExtraRunArgs = @()) {
    $mountedPath = "/mnt/atlas-morocco/$ScriptName"
    $code = "__file__ = '$mountedPath'" + [Environment]::NewLine +
        "exec(compile(open(__file__, encoding='utf-8').read(), __file__, 'exec'), globals(), globals())"
    $args = (Get-ComposeArgs) + @("run", "--rm", "--no-deps", "-T") + $ExtraRunArgs +
        @("web", "odoo", "shell", "--database=$database", "--no-http")
    $code | & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Odoo shell script $ScriptName failed." }
}

function Get-ContainerName([string]$ContainerId) {
    if (-not $ContainerId) { throw "Expected Moroccan container is missing." }
    return (Get-DockerOutput @("inspect", "--format", "{{.Name}}", $ContainerId)).TrimStart("/")
}

function Get-ExactTargetContainerId([string]$Service, [string]$ExpectedName) {
    $inspectJson = & docker inspect $ExpectedName 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $inspectJson) {
        throw "Expected Moroccan $Service container is missing."
    }
    $container = (($inspectJson -join [Environment]::NewLine) | ConvertFrom-Json)[0]
    if ($container.Name.TrimStart("/") -ne $ExpectedName -or
        $container.Config.Labels."com.docker.compose.project" -ne $project -or
        $container.Config.Labels."com.docker.compose.service" -ne $Service -or
        $container.Config.Labels."com.autostock.target-uuid" -ne $targetUuid) {
        throw "Expected Moroccan $Service container identity does not match the isolated target."
    }
    if (-not $container.Id) {
        throw "Expected Moroccan $Service container ID is missing."
    }
    return [string]$container.Id
}

function Assert-WebRuntimeReady {
    Write-Host "Verifying the dedicated Moroccan Odoo runtime dependencies."
    Invoke-Compose @(
        "run", "--rm", "--no-deps", "--entrypoint", "python3", "web",
        "-c", "import tzdata; import numpy; import sklearn"
    )
}

function Assert-ImporterPreviewClean {
    $previewPath = Join-Path $PSScriptRoot "odoo_preview.py"
    $previewBody = Get-Content -LiteralPath $previewPath -Raw
    # Odoo shell executes stdin without defining __file__. Keep the module's
    # future import first, then provide the real read-only mounted path.
    $futureImport = "from __future__ import annotations"
    if (-not $previewBody.Contains($futureImport)) { throw "Odoo preview future-import marker is missing." }
    $previewCode = $previewBody.Replace(
        $futureImport,
        $futureImport + [Environment]::NewLine + "__file__ = '/mnt/atlas-morocco/odoo_preview.py'"
    )
    Write-Host "Running the existing read-only Moroccan importer preflight."
    Invoke-OdooShell $previewCode
}

function Get-VolumeFileHash([string]$Volume, [string]$RelativePath) {
    $mount = "type=volume,source=$Volume,target=/data,readonly"
    $output = Get-DockerOutput @("run", "--rm", "--entrypoint", "sha256sum", "--mount", $mount, $image, "/data/filestore/$database/$RelativePath")
    return (($output -split "\s+")[0]).Trim()
}

function Get-FilestoreTreeHash([string]$Volume) {
    $mount = "type=volume,source=$Volume,target=/data,readonly"
    $scriptMount = "type=bind,source=$PSScriptRoot,target=/mnt/atlas-morocco,readonly"
    return Get-DockerOutput @(
        "run", "--rm", "--entrypoint", "python3",
        "--mount", $mount,
        "--mount", $scriptMount,
        $image,
        "/mnt/atlas-morocco/filestore_tree_hash.py",
        "/data/filestore/$database"
    )
}

function Assert-CleanInitializedTarget {
    if ((Invoke-Psql "SELECT state FROM ir_module_module WHERE name='autostock_ai' LIMIT 1") -ne "installed") {
        throw "AutoStock is not installed in the Moroccan target."
    }
    if ([int](Invoke-Psql "SELECT count(*) FROM res_company") -ne 1) {
        throw "The Moroccan target must contain exactly one company."
    }
    if ((Invoke-Psql "SELECT COALESCE(value, '') FROM ir_config_parameter WHERE key='autostock.morocco.target_uuid' LIMIT 1") -ne $targetUuid) {
        throw "Database target marker does not match the prepared Moroccan UUID."
    }

    $companyIdentity = Invoke-Psql "SELECT COALESCE(autostock_demo_target_uuid, '') || '|' || CASE WHEN autostock_demo_environment THEN 'true' ELSE 'false' END || '|' || COALESCE(autostock_demo_dataset_version, '') FROM res_company LIMIT 1"
    $identityParts = $companyIdentity -split "\|", 3
    if ($identityParts.Count -ne 3 -or $identityParts[0] -ne $targetUuid -or $identityParts[1] -ne "true") {
        throw "Company target marker does not match the prepared Moroccan environment."
    }
    if ($identityParts[2]) { throw "Dataset version is already set; local pre-import backup requires a clean target." }
    if ([int](Invoke-Psql "SELECT count(*) FROM autostock_morocco_fixture") -ne 0) {
        throw "Fixture records already exist; refusing a pre-import backup."
    }

    $proofStore = Invoke-Psql "SELECT COALESCE(store_fname, '') FROM ir_attachment WHERE name='$proofAttachmentName' ORDER BY id DESC LIMIT 1"
    if (-not $proofStore) { throw "The local restore-proof attachment is missing from the clean target." }

    return @{
        proof_store_fname = $proofStore
        attachment_count = [int](Invoke-Psql "SELECT count(*) FROM ir_attachment")
    }
}

function Get-TextSha256([string]$Text) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally { $sha.Dispose() }
}

function Get-FixtureRegistrySnapshot([string]$RestoreContainer = "") {
    # Keep the canonical registry representation on one PostgreSQL output line.
    # Multiline string_agg output can be normalized differently by PowerShell
    # across docker compose exec and docker exec even for identical rows.
    $serializeSql = "SELECT COALESCE(jsonb_agg(jsonb_build_array(dataset_version, fixture_key, entity, record_model, record_id, payload_sha256) ORDER BY fixture_key, id)::text, '[]') FROM autostock_morocco_fixture"
    if ($RestoreContainer) {
        $serialized = Invoke-RestorePsql $RestoreContainer $serializeSql
        $count = [int](Invoke-RestorePsql $RestoreContainer "SELECT count(*) FROM autostock_morocco_fixture")
        $forecastRequests = [int](Invoke-RestorePsql $RestoreContainer "SELECT count(*) FROM autostock_morocco_fixture WHERE entity='forecast_request'")
    }
    else {
        $serialized = Invoke-Psql $serializeSql
        $count = [int](Invoke-Psql "SELECT count(*) FROM autostock_morocco_fixture")
        $forecastRequests = [int](Invoke-Psql "SELECT count(*) FROM autostock_morocco_fixture WHERE entity='forecast_request'")
    }
    return @{
        count = $count
        forecast_requests = $forecastRequests
        sha256 = Get-TextSha256 $serialized
    }
}

function Assert-ImportedTarget {
    Assert-MarkedTargetIdentity
    $version = Invoke-Psql "SELECT COALESCE(autostock_demo_dataset_version, '') FROM res_company LIMIT 1"
    if ($version -ne $datasetVersion) {
        throw "Imported Moroccan dataset version does not match $datasetVersion."
    }
    $registry = Get-FixtureRegistrySnapshot
    if ($registry.count -le 0) {
        throw "Imported Moroccan fixture registry is empty."
    }
    if ($registry.forecast_requests -ne $expectedForecastRequests) {
        throw "Imported Moroccan forecast request registry count is incomplete."
    }
    $proofStore = Invoke-Psql "SELECT COALESCE(store_fname, '') FROM ir_attachment WHERE name='$proofAttachmentName' ORDER BY id DESC LIMIT 1"
    if (-not $proofStore) {
        throw "The local restore-proof attachment is missing from the imported Moroccan target."
    }
    return @{
        proof_store_fname = $proofStore
        attachment_count = [int](Invoke-Psql "SELECT count(*) FROM ir_attachment")
        dataset_version = $version
        fixture_registry_count = [int]$registry.count
        forecast_request_count = [int]$registry.forecast_requests
        fixture_registry_sha256 = [string]$registry.sha256
    }
}

function Assert-MarkedTargetIdentity {
    if ((Invoke-Psql "SELECT state FROM ir_module_module WHERE name='autostock_ai' LIMIT 1") -ne "installed") {
        throw "AutoStock is not installed in the Moroccan target."
    }
    if ([int](Invoke-Psql "SELECT count(*) FROM res_company") -ne 1) {
        throw "The Moroccan target must contain exactly one company."
    }
    if ((Invoke-Psql "SELECT COALESCE(value, '') FROM ir_config_parameter WHERE key='autostock.morocco.target_uuid' LIMIT 1") -ne $targetUuid) {
        throw "Database target marker does not match the prepared Moroccan UUID."
    }
    $companyIdentity = Invoke-Psql "SELECT COALESCE(autostock_demo_target_uuid, '') || '|' || CASE WHEN autostock_demo_environment THEN 'true' ELSE 'false' END FROM res_company LIMIT 1"
    $identityParts = $companyIdentity -split "\|", 2
    if ($identityParts.Count -ne 2 -or $identityParts[0] -ne $targetUuid -or $identityParts[1] -ne "true") {
        throw "Company target marker does not match the prepared Moroccan environment."
    }
    $proofStore = Invoke-Psql "SELECT COALESCE(store_fname, '') FROM ir_attachment WHERE name='$proofAttachmentName' ORDER BY id DESC LIMIT 1"
    if (-not $proofStore) {
        throw "The local restore-proof attachment is missing from the Moroccan target."
    }
}

function Resolve-ApprovedBackupDirectory([string]$Stamp) {
    if ($Stamp -notmatch "^[0-9]{8}-[0-9]{6}$") {
        throw "Apply requires an explicit backup stamp in yyyyMMdd-HHmmss form."
    }
    $root = [System.IO.Path]::GetFullPath((Join-Path $repoRoot ".showroom/morocco-backups"))
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $root $Stamp))
    $separators = [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $prefix = $root.TrimEnd($separators) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Backup directory escaped the private Moroccan backup root."
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        throw "Approved backup directory does not exist."
    }
    foreach ($name in @("database.dump", "filestore.tar", "backup-manifest.json", "backup-manifest.key", "restore-evidence.json")) {
        if (-not (Test-Path -LiteralPath (Join-Path $candidate $name) -PathType Leaf)) {
            throw "Approved backup directory is incomplete: missing $name."
        }
    }
    return $candidate
}

function Stage-ApplyEvidenceVolume([string]$BackupDir, [string]$Volume, [string]$Scope) {
    Invoke-Docker @("volume", "create", "--label", "com.autostock.apply-evidence=$Scope", $Volume)
    $sourceMount = "type=bind,source=$BackupDir,target=/source,readonly"
    $evidenceMount = "type=volume,source=$Volume,target=/evidence"
    Invoke-Docker @(
        "run", "--rm", "--user", "root", "--entrypoint", "sh",
        "--mount", $sourceMount,
        "--mount", $evidenceMount,
        $image,
        "-c",
        "cp /source/database.dump /source/filestore.tar /source/backup-manifest.json /source/backup-manifest.key /source/restore-evidence.json /evidence/ && chown -R odoo:odoo /evidence && chmod 0444 /evidence/database.dump /evidence/filestore.tar /evidence/backup-manifest.json /evidence/restore-evidence.json && chmod 0400 /evidence/backup-manifest.key"
    )
}

function Remove-OwnedApplyEvidenceVolume([string]$Volume, [string]$Scope) {
    $resource = Get-ExistingDockerResource "volume" $Volume
    if ($null -eq $resource) { return }
    if ($null -eq $resource.Labels -or $resource.Labels."com.autostock.apply-evidence" -ne $Scope) {
        throw "Refusing to remove Apply evidence volume $Volume because it is not owned by $Scope."
    }
    Invoke-Docker @("volume", "rm", $Volume)
}

function Initialize-Target {
    Write-Host "Starting only the isolated Moroccan services."
    Invoke-Prepare "Start"

    $success = $false
    try {
        Write-Host "Stopping only Moroccan Odoo while the clean database is initialized."
        Invoke-Compose @("stop", "web")
        Assert-WebRuntimeReady
        $exists = Invoke-Psql "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_database WHERE datname='$database') THEN 'true' ELSE 'false' END" "postgres"

        if ($exists -eq "false") {
            Write-Host "Creating the clean Moroccan Odoo database and installing AutoStock."
            Invoke-Compose @("run", "--rm", "--no-deps", "web", "odoo", "--database=$database", "--init=autostock_ai", "--stop-after-init", "--without-demo=true", "--log-level=warn")
        }
        elseif ($exists -ne "true") {
            throw "Could not determine whether the Moroccan target database exists."
        }

        # Refuse a dirty or foreign database before writing target markers.
        Assert-ImporterPreviewClean

        $markerScript = @"
import base64
import os

target_uuid = os.environ["AUTOSTOCK_DEMO_TARGET_UUID"]
companies = env["res.company"].search([])
if len(companies) != 1:
    raise RuntimeError("Moroccan target must contain exactly one company.")
company = env.ref("base.main_company")
if company.id != companies.id:
    raise RuntimeError("Bootstrap main company is not the only company.")

params = env["ir.config_parameter"]
stored_uuid = params.get_param("autostock.morocco.target_uuid")
company_uuid = company.autostock_demo_target_uuid
if bool(stored_uuid) != bool(company_uuid):
    raise RuntimeError("Database and company target markers are inconsistent.")
if stored_uuid and stored_uuid != target_uuid:
    raise RuntimeError("Database target marker belongs to another environment.")
if company_uuid and company_uuid != target_uuid:
    raise RuntimeError("Company target marker belongs to another environment.")
if company.autostock_demo_dataset_version:
    raise RuntimeError("Dataset version is already set; target is not a clean pre-import database.")
if env["autostock.morocco.fixture"].search_count([]):
    raise RuntimeError("Fixture records already exist; target is not clean.")

company.write({
    "autostock_demo_environment": True,
    "autostock_demo_target_uuid": target_uuid,
})
params.set_param("autostock.morocco.target_uuid", target_uuid)

proof_bytes = b"$proofAttachmentBytes"
proof = env["ir.attachment"].search([("name", "=", "$proofAttachmentName"), ("res_model", "=", False)], limit=1)
if proof:
    if base64.b64decode(proof.datas or b"") != proof_bytes:
        raise RuntimeError("Existing restore-proof attachment has unexpected contents.")
else:
    env["ir.attachment"].create({
        "name": "$proofAttachmentName",
        "type": "binary",
        "datas": base64.b64encode(proof_bytes),
        "mimetype": "text/plain",
    })

env.cr.commit()
"@
        Invoke-OdooShell $markerScript
        $null = Assert-CleanInitializedTarget
        Assert-ImporterPreviewClean
        $success = $true
    }
    finally {
        if ($success) {
            Write-Host "Restarting only Moroccan Odoo."
            Invoke-Compose @("start", "web")
        }
        else {
            Write-Warning "Initialization did not finish; Moroccan Odoo remains stopped for safety."
        }
    }

    Invoke-Prepare "RuntimeStatus"
    Write-Host "PASS: clean Moroccan target initialized and marked. No showroom dataset was imported."
}

function Get-ExistingDockerResource([string]$Kind, [string]$Name) {
    switch ($Kind) {
        "container" {
            $names = @((Get-DockerOutput @("ps", "-aq", "--filter", "name=^/$Name$")) -split "[\r\n]+" | Where-Object { $_ })
            if ($names.Count -eq 0) { return $null }
            if ($names.Count -ne 1) { throw "Unexpected duplicate verifier container name $Name." }
            $json = Get-DockerOutput @("inspect", $Name)
            return (($json | ConvertFrom-Json)[0])
        }
        "volume" {
            $names = @((Get-DockerOutput @("volume", "ls", "--format", "{{.Name}}")) -split "[\r\n]+" | Where-Object { $_ -eq $Name })
            if ($names.Count -eq 0) { return $null }
            if ($names.Count -ne 1) { throw "Unexpected duplicate verifier volume name $Name." }
            $json = Get-DockerOutput @("volume", "inspect", $Name)
            return (($json | ConvertFrom-Json)[0])
        }
        "network" {
            $names = @((Get-DockerOutput @("network", "ls", "--format", "{{.Name}}")) -split "[\r\n]+" | Where-Object { $_ -eq $Name })
            if ($names.Count -eq 0) { return $null }
            if ($names.Count -ne 1) { throw "Unexpected duplicate verifier network name $Name." }
            $json = Get-DockerOutput @("network", "inspect", $Name)
            return (($json | ConvertFrom-Json)[0])
        }
        default { throw "Unsupported Docker resource kind $Kind." }
    }
}

function Remove-OwnedRestoreResource([string]$Kind, [string]$Name, [string]$RestoreProject) {
    $resource = Get-ExistingDockerResource $Kind $Name
    if ($null -eq $resource) { return }

    $labels = if ($Kind -eq "container") { $resource.Config.Labels } else { $resource.Labels }
    if ($null -eq $labels -or $labels."com.autostock.restore-proof" -ne $RestoreProject) {
        throw "Refusing to remove $Kind $Name because it is not owned by restore project $RestoreProject."
    }

    switch ($Kind) {
        "container" { Invoke-Docker @("rm", "-f", $Name) }
        "volume" { Invoke-Docker @("volume", "rm", $Name) }
        "network" { Invoke-Docker @("network", "rm", $Name) }
    }
}

function Remove-RestoreResources(
    [string]$Container,
    [string]$PostgresRestoreVolume,
    [string]$FilestoreRestoreVolume,
    [string]$Network,
    [string]$RestoreProject
) {
    Remove-OwnedRestoreResource "container" $Container $RestoreProject
    Remove-OwnedRestoreResource "volume" $PostgresRestoreVolume $RestoreProject
    Remove-OwnedRestoreResource "volume" $FilestoreRestoreVolume $RestoreProject
    Remove-OwnedRestoreResource "network" $Network $RestoreProject
}

function Assert-RestoreResourcesRemoved([string]$Container, [string]$PostgresRestoreVolume, [string]$FilestoreRestoreVolume, [string]$Network) {
    $containers = @((Get-DockerOutput @("ps", "-aq", "--filter", "name=^/$Container$")) -split "[\r\n]+" | Where-Object { $_ })
    $volumeNames = @((Get-DockerOutput @("volume", "ls", "-q")) -split "[\r\n]+" | Where-Object { $_ })
    $networkNames = @((Get-DockerOutput @("network", "ls", "--format", "{{.Name}}")) -split "[\r\n]+" | Where-Object { $_ })
    if ($containers.Count -or $PostgresRestoreVolume -in $volumeNames -or $FilestoreRestoreVolume -in $volumeNames -or $Network -in $networkNames) {
        throw "Disposable restore verifier resources were not fully removed."
    }
}

function Backup-And-Restore([bool]$PostApply = $false) {
    if ($PostApply) {
        # The imported target already exists. Do not rebuild or recreate it before
        # capturing the post-import recovery point.
        Invoke-Prepare "RuntimeStatus"
        Assert-WebRuntimeReady
        Write-Host "Verifying the committed imported registry before taking the post-import backup."
        Invoke-OdooMountedScript "odoo_verify.py"
        $source = Assert-ImportedTarget
    }
    else {
        Invoke-Prepare "Start"
        $source = Assert-CleanInitializedTarget
    }

    $dbContainerId = Get-ExactTargetContainerId "db" "autostock-atlas-morocco-db-1"
    $webContainerId = Get-ExactTargetContainerId "web" "autostock-atlas-morocco-web-1"
    $dbContainerName = Get-ContainerName $dbContainerId
    $webContainerName = Get-ContainerName $webContainerId
    $postgresSystemIdentifier = Invoke-Psql "SELECT system_identifier FROM pg_control_system()" "postgres"
    if ($postgresSystemIdentifier -notmatch "^[0-9]{10,}$") { throw "PostgreSQL cluster identity is missing or malformed." }

    $stamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")
    $backupDir = Join-Path $repoRoot ".showroom/morocco-backups/$stamp"
    New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop | Out-Null
    $dumpPath = Join-Path $backupDir "database.dump"
    $filestorePath = Join-Path $backupDir "filestore.tar"
    $manifestPath = Join-Path $backupDir "backup-manifest.json"
    $signingKeyPath = Join-Path $backupDir "backup-manifest.key"
    $evidencePath = Join-Path $backupDir "restore-evidence.json"

    $restoreSuffix = [guid]::NewGuid().ToString("N").Substring(0, 12)
    $restoreProject = "autostock-restore-proof-local-$restoreSuffix"
    $restoreContainer = "$restoreProject-db"
    $restorePostgresVolume = "$restoreProject-postgres"
    $restoreFilestoreVolume = "$restoreProject-filestore"
    $restoreNetwork = "$restoreProject-private"
    $restorePassword = (& python -c "import secrets; print(secrets.token_hex(32))").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $restorePassword) { throw "Could not generate verifier database credentials." }

    $webStopped = $false
    try {
        Write-Host "Stopping only Moroccan Odoo to take a consistent target backup."
        Invoke-Compose @("stop", "web")
        $webStopped = $true
        if ($PostApply) {
            $source = Assert-ImportedTarget
        }
        else {
            $source = Assert-CleanInitializedTarget
            Assert-ImporterPreviewClean
        }

        Write-Host "Creating private database and filestore backup artifacts under ignored .showroom/."
        $containerDumpPath = "/tmp/autostock-morocco-$restoreSuffix.dump"
        Invoke-Docker @("exec", $dbContainerId, "pg_dump", "-U", $postgresUser, "-Fc", $database, "-f", $containerDumpPath)
        Invoke-Docker @("cp", "$($dbContainerId):$containerDumpPath", $dumpPath)
        Invoke-Docker @("exec", $dbContainerId, "rm", "-f", $containerDumpPath)

        $sourceVolumeMount = "type=volume,source=$filestoreVolume,target=/data,readonly"
        $backupMount = "type=bind,source=$backupDir,target=/backup"
        Invoke-Docker @("run", "--rm", "--user", "root", "--entrypoint", "sh", "--mount", $sourceVolumeMount, "--mount", $backupMount, $image, "-c", "cd /data && tar -cf /backup/filestore.tar .")

        $sourceAttachmentHash = Get-VolumeFileHash $filestoreVolume $source.proof_store_fname
        $sourceTreeHash = Get-FilestoreTreeHash $filestoreVolume

        $createArgs = @("-m", "scripts.moroccan_showroom.local_backup", "create", "--database-path", $dumpPath, "--filestore-path", $filestorePath, "--manifest-path", $manifestPath, "--signing-key-path", $signingKeyPath, "--target-uuid", $targetUuid, "--postgres-system-identifier", $postgresSystemIdentifier, "--container-name", $dbContainerName, "--container-name", $webContainerName)
        Invoke-Python $createArgs
        $validateArgs = @("-m", "scripts.moroccan_showroom.local_backup", "validate", "--manifest-path", $manifestPath, "--signing-key-path", $signingKeyPath, "--target-uuid", $targetUuid, "--postgres-system-identifier", $postgresSystemIdentifier, "--container-name", $dbContainerName, "--container-name", $webContainerName)
        Invoke-Python $validateArgs

        Write-Host "Restoring the exact backup into a new no-port verifier."
        Invoke-Docker @("network", "create", "--label", "com.autostock.restore-proof=$restoreProject", $restoreNetwork)
        Invoke-Docker @("volume", "create", "--label", "com.autostock.restore-proof=$restoreProject", $restorePostgresVolume)
        Invoke-Docker @("volume", "create", "--label", "com.autostock.restore-proof=$restoreProject", $restoreFilestoreVolume)
        Invoke-Docker @("run", "--detach", "--name", $restoreContainer, "--label", "com.autostock.restore-proof=$restoreProject", "--network", $restoreNetwork, "--env", "POSTGRES_USER=$postgresUser", "--env", "POSTGRES_PASSWORD=$restorePassword", "--env", "POSTGRES_DB=postgres", "--mount", "type=volume,source=$restorePostgresVolume,target=/var/lib/postgresql/data", "postgres:16")

        $ready = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            $pidOne = & docker exec $restoreContainer cat /proc/1/comm 2>$null
            $pidOneOk = $LASTEXITCODE -eq 0 -and (($pidOne -join "").Trim() -eq "postgres")
            if ($pidOneOk) {
                & docker exec $restoreContainer pg_isready -U $postgresUser -d postgres *> $null
                if ($LASTEXITCODE -eq 0) { $ready = $true; break }
            }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) { throw "Disposable restore PostgreSQL did not reach its final ready process." }

        $portBindings = Get-DockerOutput @("inspect", "--format", "{{json .HostConfig.PortBindings}}", $restoreContainer)
        if ($portBindings -notin @("null", "{}")) { throw "Disposable restore PostgreSQL unexpectedly publishes a host port." }

        Invoke-Docker @("cp", $dumpPath, "$($restoreContainer):/tmp/database.dump")
        Invoke-Docker @("exec", $restoreContainer, "createdb", "-U", $postgresUser, $database)
        Invoke-Docker @("exec", $restoreContainer, "pg_restore", "-U", $postgresUser, "-d", $database, "--no-owner", "--no-privileges", "/tmp/database.dump")

        $restoreFilestoreMount = "type=volume,source=$restoreFilestoreVolume,target=/data"
        $backupReadOnlyMount = "type=bind,source=$backupDir,target=/backup,readonly"
        Invoke-Docker @("run", "--rm", "--user", "root", "--entrypoint", "sh", "--mount", $restoreFilestoreMount, "--mount", $backupReadOnlyMount, $image, "-c", "cd /data && tar -xf /backup/filestore.tar")

        $moduleState = Invoke-RestorePsql $restoreContainer "SELECT state FROM ir_module_module WHERE name='autostock_ai' LIMIT 1"
        $restoredMarker = Invoke-RestorePsql $restoreContainer "SELECT COALESCE(autostock_demo_target_uuid, '') FROM res_company WHERE autostock_demo_environment IS TRUE LIMIT 1"
        $fixtureTable = Invoke-RestorePsql $restoreContainer "SELECT CASE WHEN to_regclass('public.autostock_morocco_fixture') IS NULL THEN 'false' ELSE 'true' END"
        $restoredAttachmentCount = [int](Invoke-RestorePsql $restoreContainer "SELECT count(*) FROM ir_attachment")
        $restoredStore = Invoke-RestorePsql $restoreContainer "SELECT COALESCE(store_fname, '') FROM ir_attachment WHERE name='$proofAttachmentName' ORDER BY id DESC LIMIT 1"
        $restoredDatasetVersion = Invoke-RestorePsql $restoreContainer "SELECT COALESCE(autostock_demo_dataset_version, '') FROM res_company LIMIT 1"
        $restoredRegistry = Get-FixtureRegistrySnapshot $restoreContainer

        if ($moduleState -ne "installed") { throw "Restored AutoStock module is not installed." }
        if ($restoredMarker -ne $targetUuid) { throw "Restored target UUID marker does not match." }
        if ($fixtureTable -ne "true") { throw "Restored fixture table is missing." }
        if ($restoredAttachmentCount -ne $source.attachment_count) { throw "Restored attachment count differs from source." }
        if ($restoredStore -ne $source.proof_store_fname) { throw "Restored proof attachment path differs from source." }
        if ($PostApply) {
            if ($restoredDatasetVersion -ne $source.dataset_version) { throw "Restored dataset version differs from source." }
            if ($restoredRegistry.count -ne $source.fixture_registry_count) { throw "Restored fixture registry count differs from source." }
            if ($restoredRegistry.forecast_requests -ne $source.forecast_request_count) { throw "Restored forecast request registry count differs from source." }
        }
        elseif ($restoredDatasetVersion) {
            throw "Pre-import restore unexpectedly contains a dataset version."
        }

        $restoredAttachmentHash = Get-VolumeFileHash $restoreFilestoreVolume $restoredStore
        $restoredTreeHash = Get-FilestoreTreeHash $restoreFilestoreVolume
        if ($restoredAttachmentHash -ne $sourceAttachmentHash) { throw "Restored proof attachment bytes differ." }
        if ($restoredTreeHash -ne $sourceTreeHash) { throw "Restored filestore tree differs." }

        Write-Host "Removing only the disposable restore verifier."
        Remove-RestoreResources $restoreContainer $restorePostgresVolume $restoreFilestoreVolume $restoreNetwork $restoreProject
        Assert-RestoreResourcesRemoved $restoreContainer $restorePostgresVolume $restoreFilestoreVolume $restoreNetwork

        # Re-check the exact artifacts after they were used for restore.
        Invoke-Python $validateArgs

        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        $evidence = @{
            restore_project = $restoreProject
            published_ports = @()
            restore_postgres_volume = $restorePostgresVolume
            restore_filestore_volume = $restoreFilestoreVolume
            restore_database = $database
            backup_database_sha256 = $manifest.database_sha256
            backup_filestore_sha256 = $manifest.filestore_sha256
            pg_restore_succeeded = $true
            module_state = $moduleState
            marker_uuid = $restoredMarker
            fixture_table_exists = $true
            source_attachment_sha256 = $sourceAttachmentHash
            restored_attachment_sha256 = $restoredAttachmentHash
            source_filestore_tree_sha256 = $sourceTreeHash
            restored_filestore_tree_sha256 = $restoredTreeHash
            source_attachment_count = [int]$source.attachment_count
            restored_attachment_count = $restoredAttachmentCount
            proof_attachment_present = $true
            backup_stage = if ($PostApply) { "post-import" } else { "pre-import" }
            dataset_version = if ($PostApply) { $source.dataset_version } else { "" }
            source_fixture_registry_count = if ($PostApply) { [int]$source.fixture_registry_count } else { 0 }
            restored_fixture_registry_count = if ($PostApply) { [int]$restoredRegistry.count } else { 0 }
            source_forecast_request_count = if ($PostApply) { [int]$source.forecast_request_count } else { 0 }
            restored_forecast_request_count = if ($PostApply) { [int]$restoredRegistry.forecast_requests } else { 0 }
            cleanup_scope = $restoreProject
            restore_resources_removed = $true
        }
        [System.IO.File]::WriteAllText($evidencePath, (ConvertTo-Json -InputObject $evidence -Depth 10), [System.Text.UTF8Encoding]::new($false))

        $restoreArgs = @(
            "-m", "scripts.moroccan_showroom.restore_contract",
            "--evidence-json", $evidencePath,
            "--backup-manifest-json", $manifestPath,
            "--signing-key-file", $signingKeyPath,
            "--expected-target-uuid", $targetUuid,
            "--sign-evidence"
        )
        Invoke-Python $restoreArgs

        if ($PostApply) {
            Write-Host "PASS: imported Moroccan dataset database + filestore backup restored and independently verified."
            Write-Host "Verified $($source.fixture_registry_count) registry entries and $($source.forecast_request_count) forecast requests from the exact signed database dump."
        }
        else {
            Write-Host "PASS: real Moroccan target database + filestore backup restored and independently verified."
            Write-Host "No showroom dataset was imported."
        }
        Write-Host "Private backup artifacts remain under .showroom/morocco-backups/$stamp."
        Write-Host "No application connection was changed. Legacy USD Atlas remains separate."
    }
    finally {
        try {
            Remove-RestoreResources $restoreContainer $restorePostgresVolume $restoreFilestoreVolume $restoreNetwork $restoreProject
        }
        finally {
            if ($webStopped) {
                try { Invoke-Compose @("start", "web") }
                catch { Write-Warning "Moroccan Odoo could not be restarted automatically; the database backup remains unchanged." }
            }
        }
    }

    Invoke-Prepare "RuntimeStatus"
}

function Diagnose-PostApply {
    Write-Host "Inspecting the imported Moroccan target without changing it."
    Invoke-Prepare "Status"
    Assert-MarkedTargetIdentity
    Assert-WebRuntimeReady
    Invoke-OdooMountedScript "odoo_diagnose.py"
    Write-Host "PASS: diagnostic completed read-only; no database mutation or cleanup was attempted."
}

function Apply-Dataset {
    if (-not $TypedTargetUuid -or $TypedTargetUuid -ne $targetUuid) {
        throw "Apply requires typing the exact prepared target UUID."
    }
    $backupDir = Resolve-ApprovedBackupDirectory $BackupStamp

    Write-Host "Starting and re-checking only the isolated Moroccan target."
    Invoke-Prepare "Start"
    Assert-MarkedTargetIdentity
    Assert-WebRuntimeReady

    $dbContainerId = Get-ComposeOutput @("ps", "-q", "db")
    $webContainerId = Get-ComposeOutput @("ps", "-q", "web")
    $dbContainerName = Get-ContainerName $dbContainerId
    $webContainerName = Get-ContainerName $webContainerId
    $postgresSystemIdentifier = Invoke-Psql "SELECT system_identifier FROM pg_control_system()" "postgres"
    if ($postgresSystemIdentifier -notmatch "^[0-9]{10,}$") {
        throw "PostgreSQL cluster identity is missing or malformed."
    }

    $manifestPath = Join-Path $backupDir "backup-manifest.json"
    $signingKeyPath = Join-Path $backupDir "backup-manifest.key"
    $evidencePath = Join-Path $backupDir "restore-evidence.json"
    $validateArgs = @(
        "-m", "scripts.moroccan_showroom.local_backup", "validate",
        "--manifest-path", $manifestPath,
        "--signing-key-path", $signingKeyPath,
        "--target-uuid", $targetUuid,
        "--postgres-system-identifier", $postgresSystemIdentifier,
        "--container-name", $dbContainerName,
        "--container-name", $webContainerName
    )
    $restoreArgs = @(
        "-m", "scripts.moroccan_showroom.restore_contract",
        "--evidence-json", $evidencePath,
        "--backup-manifest-json", $manifestPath,
        "--signing-key-file", $signingKeyPath,
        "--expected-target-uuid", $targetUuid
    )

    Write-Host "Re-validating the exact signed backup and independent restore evidence."
    Invoke-Python $validateArgs
    Invoke-Python $restoreArgs
    Write-Host "Running a final read-only importer preflight before mutation."
    Assert-ImporterPreviewClean

    $applyEvidenceScope = "autostock-apply-evidence-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
    $applyEvidenceVolume = "$applyEvidenceScope-private"
    $success = $false
    $cleanupOk = $false
    try {
        Write-Host "Stopping only Moroccan Odoo for the guarded dataset transaction."
        Invoke-Compose @("stop", "web")
        Assert-MarkedTargetIdentity

        # Re-check private evidence after stopping web and immediately before writes.
        Invoke-Python $validateArgs
        Invoke-Python $restoreArgs

        Write-Host "Staging read-only Apply evidence in a disposable labeled Docker volume."
        Stage-ApplyEvidenceVolume $backupDir $applyEvidenceVolume $applyEvidenceScope

        $evidenceMount = $applyEvidenceVolume + ":/mnt/atlas-backup:ro"
        $extraArgs = @(
            "--volume", $evidenceMount,
            "--env", "AUTOSTOCK_MOROCCO_TYPED_TARGET_UUID=$TypedTargetUuid",
            "--env", "AUTOSTOCK_MOROCCO_POSTGRES_SYSTEM_IDENTIFIER=$postgresSystemIdentifier",
            "--env", "AUTOSTOCK_MOROCCO_DB_CONTAINER_NAME=$dbContainerName",
            "--env", "AUTOSTOCK_MOROCCO_WEB_CONTAINER_NAME=$webContainerName"
        )

        Write-Host "Applying atlas-ma-2026.4 through the guarded Odoo ORM importer."
        Invoke-OdooMountedScript "odoo_apply.py" $extraArgs

        Write-Host "Verifying the committed fixture registry in a separate read-only Odoo process."
        Invoke-OdooMountedScript "odoo_verify.py"
        $success = $true
    }
    finally {
        try {
            Remove-OwnedApplyEvidenceVolume $applyEvidenceVolume $applyEvidenceScope
            $cleanupOk = $true
        }
        finally {
            if ($success -and $cleanupOk) {
                Write-Host "Restarting only Moroccan Odoo after verified Apply."
                Invoke-Compose @("start", "web")
            }
            else {
                Write-Warning "Apply did not finish with verified cleanup; Moroccan Odoo remains stopped for safety."
            }
        }
    }

    Invoke-Prepare "RuntimeStatus"
    Write-Host "PASS: atlas-ma-2026.4 imported and registry-verified on the isolated Moroccan target."
    Write-Host "No application connection was changed. Legacy USD Atlas remains separate."
}

switch ($Action) {
    "Initialize" { Initialize-Target }
    "BackupRestore" { Backup-And-Restore $false }
    "PostApplyRestore" { Backup-And-Restore $true }
    "DiagnosePostApply" { Diagnose-PostApply }
    "Apply" { Apply-Dataset }
}
