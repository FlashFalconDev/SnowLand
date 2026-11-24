param([string]$Python = '.venv\Scripts\python.exe')

$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..\snowland')
try {
    $env:DJANGO_SECRET_KEY = [guid]::NewGuid().ToString('N')
    $env:DJANGO_DEBUG = '1'
    $env:AWS_EC2_METADATA_DISABLED = 'true'
    $env:EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    $env:PYTHONUTF8 = '1'
    $env:MYSQL_ROOT_PASSWORD = [guid]::NewGuid().ToString('N')
    $env:MYSQL_PASSWORD = [guid]::NewGuid().ToString('N')
    $env:MYSQL_DATABASE = 'snowland_order_cleanup_isolated'
    $env:MYSQL_USER = 'archive_test'
    $env:Mysql_NAME = $env:MYSQL_DATABASE
    $env:Mysql_HOST = '127.0.0.1'
    $suffix = [guid]::NewGuid().ToString('N').Substring(0, 12)
    $container = "snowland-order-archive-$suffix"
    docker run --detach --rm --name $container --publish 127.0.0.1::3306 --tmpfs /var/lib/mysql -e MYSQL_ROOT_PASSWORD -e MYSQL_PASSWORD -e MYSQL_DATABASE -e MYSQL_USER mysql:8.0 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Unable to start isolated MySQL' }
    try {
        $published = docker port $container 3306/tcp
        if ($published -cnotmatch '^127\.0\.0\.1:([0-9]+)$') { throw 'MySQL port is not on loopback' }
        $env:Mysql_PORT = $Matches[1]
        $probe = Join-Path $PSScriptRoot 'verify-snowland-order-archive-mysql.py'
        & $Python $probe $env:Mysql_PORT
        if ($LASTEXITCODE -ne 0) { throw 'Isolated archive rehearsal failed' }
    } finally {
        docker stop $container | Out-Null
    }
} finally {
    Pop-Location
}
