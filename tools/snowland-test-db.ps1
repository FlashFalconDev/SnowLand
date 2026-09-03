[CmdletBinding()]
param(
    [ValidateSet('setup', 'start', 'status', 'stop')]
    [string]$Action = 'status'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $PSScriptRoot 'docker-compose.test-db.yml'
$LocalEnvFile = Join-Path $RepoRoot '.env.local'
$ProjectName = 'snowland-test-db'
$ContainerName = 'snowland-test-mysql'

function New-RandomSecret {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    } finally {
        $generator.Dispose()
    }
    return ([Convert]::ToBase64String($bytes)).TrimEnd('=').Replace('+', 'A').Replace('/', 'B')
}

function Initialize-LocalEnv {
    if (Test-Path -LiteralPath $LocalEnvFile) {
        return
    }

    $dbPassword = New-RandomSecret
    $rootPassword = New-RandomSecret
    $lines = @(
        '# SnowLand local database only. Generated automatically; never commit this file.'
        'SNOWLAND_TEST_MYSQL_IMAGE=mysql:8.0'
        'SNOWLAND_TEST_DB_NAME=test_snowland'
        'SNOWLAND_TEST_DB_HOST=127.0.0.1'
        'SNOWLAND_TEST_DB_PORT=3308'
        'SNOWLAND_TEST_DB_USER=snowland_test'
        "SNOWLAND_TEST_DB_PASSWORD=$dbPassword"
        "SNOWLAND_TEST_MYSQL_ROOT_PASSWORD=$rootPassword"
        'SNOWLAND_TEST_DB_COLLATION=utf8mb4_unicode_ci'
    )
    [IO.File]::WriteAllLines($LocalEnvFile, $lines, (New-Object Text.UTF8Encoding($false)))
    Write-Host 'Created SnowLand .env.local with local-only random passwords (values not printed).'
}

function Import-LocalEnv {
    Initialize-LocalEnv
    foreach ($line in [IO.File]::ReadAllLines($LocalEnvFile)) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }
        if ($trimmed -notmatch '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            throw "Invalid environment line in .env.local: $trimmed"
        }
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), 'Process')
    }
}

function Assert-SafeConfiguration {
    if ($env:SNOWLAND_TEST_DB_NAME -ne 'test_snowland') {
        throw 'SnowLand local database name must be test_snowland.'
    }
    if ($env:SNOWLAND_TEST_DB_HOST -notin @('127.0.0.1', 'localhost', '::1')) {
        throw 'SnowLand local database host must be loopback.'
    }
    if ($env:SNOWLAND_TEST_DB_PORT -ne '3308') {
        throw 'SnowLand local database port must be 3308.'
    }
}

function Invoke-Compose {
    param([Parameter(Mandatory = $true)][string[]]$ArgumentList)
    & docker compose --project-name $ProjectName --env-file $LocalEnvFile -f $ComposeFile @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($ArgumentList -join ' ')"
    }
}

function Wait-ForHealthyDatabase {
    $deadline = [DateTime]::UtcNow.AddSeconds(150)
    do {
        $health = & docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $ContainerName 2>$null
        if ($LASTEXITCODE -eq 0 -and ($health | Out-String).Trim() -eq 'healthy') {
            Write-Host 'SnowLand local MySQL database is healthy.'
            return
        }
        Start-Sleep -Seconds 3
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'SnowLand local MySQL database did not become healthy within 150 seconds.'
}

Import-LocalEnv
Assert-SafeConfiguration

switch ($Action) {
    'setup' {
        Write-Host 'SnowLand .env.local is ready.'
    }
    'start' {
        Invoke-Compose -ArgumentList @('up', '-d')
        Wait-ForHealthyDatabase
    }
    'status' {
        Invoke-Compose -ArgumentList @('ps')
    }
    'stop' {
        Invoke-Compose -ArgumentList @('stop')
    }
}
