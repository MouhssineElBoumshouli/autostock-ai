param(
    [ValidateSet("Initialize", "BackupRestore")]
    [string]$Action
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$envPath = Join-Path $repoRoot ".env.atlas-morocco"
$composePath = Join-Path $repoRoot "compose.morocco.yml"
$preparePath = Join-Path $PSScriptRoot "prepare.ps1"
$project = "autostock-atlas-morocco"
$database = "autostock_atlas_morocco_demo"
$filestoreVolume = "autostock_atlas_morocco_filestore"
$image = "autostock-ai-odoo:19.0"
$proofAttachmentName = "AutoStock local restore proof"
$proofAttachmentBytes = "autostock-local-independent-restore-proof-v1"

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

function Get-ContainerName([string]$ContainerId) {
    if (-not $ContainerId) { throw "Expected Moroccan container is missing." }
    return (Get-DockerOutput @("inspect", "--format", "{{.Name}}", $ContainerId)).TrimStart("/")
}

function Get-VolumeFileHash([string]$Volume, [string]$RelativePath) {
    $mount = "type=volume,source=$Volume,target=/data,readonly"
    $output = Get-DockerOutput @("run", "--rm", "--entrypoint", "sha256sum", "--mount", $mount, $image, "/data/filestore/$database/$RelativePath")
    return (($output -split "\s+")[0]).Trim()
}

function Get-FilestoreTreeHash([string]$Volume) {
    $mount = "type=volume,source=$Volume,target=/data,readonly"
    $python = @'
import hashlib
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
digest = hashlib.sha256()
for path in sorted(item for item in root.rglob("*") if item.is_file()):
    digest.update(path.relative_to(root).as_posix().encode() + b"\0")
    digest.update(hashlib.sha256(path.read_bytes()).digest())
print(digest.hexdigest())
'@
    return Get-DockerOutput @("run", "--rm", "--entrypoint", "python3", "--mount", $mount, $image, "-c", $python, "/data/filestore/$database")
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

function Initialize-Target {
    Write-Host "Starting only the isolated Moroccan services."
    Invoke-Prepare "Start"

    $success = $false
    try {
        Write-Host "Stopping only Moroccan Odoo while the clean database is initialized."
        Invoke-Compose @("stop", "web")
        $exists = Invoke-Psql "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_database WHERE datname='$database') THEN 'true' ELSE 'false' END" "postgres"

        if ($exists -eq "false") {
            Write-Host "Creating the clean Moroccan Odoo database and installing AutoStock."
            Invoke-Compose @("run", "--rm", "--no-deps", "web", "odoo", "--database=$database", "--init=autostock_ai", "--stop-after-init", "--without-demo=true", "--log-level=warn")
        }
        elseif ($exists -ne "true") {
            throw "Could not determine whether the Moroccan target database exists."
        }

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

    Invoke-Prepare "Status"
    Write-Host "PASS: clean Moroccan target initialized and marked. No showroom dataset was imported."
}

function Remove-RestoreResources([string]$Container, [string]$PostgresRestoreVolume, [string]$FilestoreRestoreVolume, [string]$Network) {
    & docker rm -f $Container *> $null
    & docker volume rm $PostgresRestoreVolume *> $null
    & docker volume rm $FilestoreRestoreVolume *> $null
    & docker network rm $Network *> $null
}

function Assert-RestoreResourcesRemoved([string]$Container, [string]$PostgresRestoreVolume, [string]$FilestoreRestoreVolume, [string]$Network) {
    $containers = @((Get-DockerOutput @("ps", "-aq", "--filter", "name=^/$Container$")) -split "[\r\n]+" | Where-Object { $_ })
    $volumeNames = @((Get-DockerOutput @("volume", "ls", "-q")) -split "[\r\n]+" | Where-Object { $_ })
    $networkNames = @((Get-DockerOutput @("network", "ls", "--format", "{{.Name}}")) -split "[\r\n]+" | Where-Object { $_ })
    if ($containers.Count -or $PostgresRestoreVolume -in $volumeNames -or $FilestoreRestoreVolume -in $volumeNames -or $Network -in $networkNames) {
        throw "Disposable restore verifier resources were not fully removed."
    }
}

function Backup-And-Restore {
    Invoke-Prepare "Start"
    $source = Assert-CleanInitializedTarget

    $dbContainerId = Get-ComposeOutput @("ps", "-q", "db")
    $webContainerId = Get-ComposeOutput @("ps", "-q", "web")
    $dbContainerName = Get-ContainerName $dbContainerId
    $webContainerName = Get-ContainerName $webContainerId
    $postgresSystemIdentifier = Invoke-Psql "SELECT system_identifier FROM pg_control_system()" "postgres"
    if ($postgresSystemIdentifier -notmatch "^[0-9]{10,}$") { throw "PostgreSQL cluster identity is missing or malformed." }

    $stamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")
    $backupDir = Join-Path $repoRoot ".showroom/morocco-backups/$stamp"
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
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
        $source = Assert-CleanInitializedTarget

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
        Invoke-Docker @("run", "--detach", "--name", $restoreContainer, "--network", $restoreNetwork, "--env", "POSTGRES_USER=$postgresUser", "--env", "POSTGRES_PASSWORD=$restorePassword", "--env", "POSTGRES_DB=postgres", "--mount", "type=volume,source=$restorePostgresVolume,target=/var/lib/postgresql/data", "postgres:16")

        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            & docker exec $restoreContainer pg_isready -U $postgresUser -d postgres *> $null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) { throw "Disposable restore PostgreSQL did not become ready." }

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

        if ($moduleState -ne "installed") { throw "Restored AutoStock module is not installed." }
        if ($restoredMarker -ne $targetUuid) { throw "Restored target UUID marker does not match." }
        if ($fixtureTable -ne "true") { throw "Restored fixture table is missing." }
        if ($restoredAttachmentCount -ne $source.attachment_count) { throw "Restored attachment count differs from source." }
        if ($restoredStore -ne $source.proof_store_fname) { throw "Restored proof attachment path differs from source." }

        $restoredAttachmentHash = Get-VolumeFileHash $restoreFilestoreVolume $restoredStore
        $restoredTreeHash = Get-FilestoreTreeHash $restoreFilestoreVolume
        if ($restoredAttachmentHash -ne $sourceAttachmentHash) { throw "Restored proof attachment bytes differ." }
        if ($restoredTreeHash -ne $sourceTreeHash) { throw "Restored filestore tree differs." }

        Write-Host "Removing only the disposable restore verifier."
        Remove-RestoreResources $restoreContainer $restorePostgresVolume $restoreFilestoreVolume $restoreNetwork
        Assert-RestoreResourcesRemoved $restoreContainer $restorePostgresVolume $restoreFilestoreVolume $restoreNetwork

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
            cleanup_scope = $restoreProject
            restore_resources_removed = $true
        }
        [System.IO.File]::WriteAllText($evidencePath, (ConvertTo-Json -InputObject $evidence -Depth 10), [System.Text.UTF8Encoding]::new($false))

        $restoreArgs = @("-m", "scripts.moroccan_showroom.restore_contract", "--evidence-json", $evidencePath, "--backup-manifest-json", $manifestPath, "--signing-key-file", $signingKeyPath, "--expected-target-uuid", $targetUuid)
        Invoke-Python $restoreArgs

        Write-Host "PASS: real Moroccan target database + filestore backup restored and independently verified."
        Write-Host "Private backup artifacts remain under .showroom/morocco-backups/$stamp."
        Write-Host "No showroom dataset was imported and no app connection was changed."
    }
    finally {
        Remove-RestoreResources $restoreContainer $restorePostgresVolume $restoreFilestoreVolume $restoreNetwork
        if ($webStopped) {
            try { Invoke-Compose @("start", "web") }
            catch { Write-Warning "Moroccan Odoo could not be restarted automatically; the database backup remains unchanged." }
        }
    }

    Invoke-Prepare "Status"
}

switch ($Action) {
    "Initialize" { Initialize-Target }
    "BackupRestore" { Backup-And-Restore }
}
