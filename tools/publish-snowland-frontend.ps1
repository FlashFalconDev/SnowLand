#requires -Version 5.1
[CmdletBinding(DefaultParameterSetName = 'Publish')]
param(
    [string]$Worktree,
    [Parameter(Mandatory = $true, ParameterSetName = 'Publish')]
    [Parameter(Mandatory = $true, ParameterSetName = 'Status')]
    [string]$ApiBase,
    [Parameter(ParameterSetName = 'Publish')][switch]$BuildOnly,
    [Parameter(ParameterSetName = 'Publish')][switch]$SkipBuild,
    [Parameter(ParameterSetName = 'Publish')][switch]$SkipInstall,
    [Parameter(ParameterSetName = 'Publish')][switch]$DryRun,
    [Parameter(Mandatory = $true, ParameterSetName = 'Status')][guid]$RequestId,
    [Parameter(Mandatory = $true, ParameterSetName = 'Token')][switch]$NewToken,
    [ValidateNotNullOrEmpty()][string]$TokenTarget = 'SnowLandFrontendPublish'
)

$ErrorActionPreference = 'Stop'

function Initialize-CredentialManager {
    if ('SnowLandPublishCredentials' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class SnowLandPublishCredentials {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct Credential {
        public UInt32 Flags, Type;
        public string TargetName, Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public UInt32 CredentialBlobSize;
        public IntPtr CredentialBlob;
        public UInt32 Persist, AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias, UserName;
    }

    [DllImport("advapi32.dll", EntryPoint = "CredReadW", ExactSpelling = true, SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CredRead(string target, UInt32 type, UInt32 flags, out IntPtr credential);
    [DllImport("advapi32.dll", EntryPoint = "CredWriteW", ExactSpelling = true, SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CredWrite(ref Credential credential, UInt32 flags);
    [DllImport("advapi32.dll")]
    private static extern void CredFree(IntPtr credential);

    public static string Read(string target) {
        IntPtr pointer;
        if (!CredRead(target, 1, 0, out pointer)) {
            int error = Marshal.GetLastWin32Error();
            if (error == 1168) return null; // ERROR_NOT_FOUND
            throw new Win32Exception(error);
        }
        try {
            Credential credential = (Credential)Marshal.PtrToStructure(pointer, typeof(Credential));
            return Marshal.PtrToStringUni(credential.CredentialBlob, (int)credential.CredentialBlobSize / 2);
        } finally {
            CredFree(pointer);
        }
    }

    public static void Save(string target, string token) {
        Credential credential = new Credential {
            Type = 1, TargetName = target, UserName = "SnowLandFrontendPublish", Persist = 2,
            CredentialBlobSize = (UInt32)(token.Length * 2), CredentialBlob = Marshal.StringToCoTaskMemUni(token)
        };
        try {
            if (!CredWrite(ref credential, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());
        } finally {
            Marshal.ZeroFreeCoTaskMemUnicode(credential.CredentialBlob);
        }
    }
}
'@
}

function New-PublisherToken {
    Initialize-CredentialManager
    if ($null -ne [SnowLandPublishCredentials]::Read($TokenTarget)) {
        throw 'The Credential Manager target already exists. Use a new -TokenTarget for rotation.'
    }
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = New-Object byte[] 32
        $random.GetBytes($bytes)
        $newToken = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
        [SnowLandPublishCredentials]::Save($TokenTarget, $newToken)
        [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($newToken))).Replace('-', '').ToLowerInvariant()
    } finally {
        $random.Dispose()
        $sha.Dispose()
    }
}

function Get-DistFiles([IO.DirectoryInfo]$Root) {
    $directories = [Collections.Generic.Stack[IO.DirectoryInfo]]::new()
    $directories.Push($Root)
    while ($directories.Count) {
        $directory = $directories.Pop()
        if ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'dist contains a linked directory.' }
        foreach ($item in Get-ChildItem -LiteralPath $directory.FullName -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'dist contains a linked file or directory.' }
            if ($item.PSIsContainer) { $directories.Push($item) } else { $item }
        }
    }
}

function New-BuildArchive([IO.DirectoryInfo]$Dist, [string]$ZipPath) {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $files = @(Get-DistFiles $Dist | Sort-Object FullName)
    if ($files.Count -gt 3000 -or ($files | Measure-Object Length -Sum).Sum -gt 1GB) { throw 'dist exceeds the file count or expanded size limit.' }
    $index = $files | Where-Object Name -CEQ 'index.html' | Where-Object DirectoryName -EQ $Dist.FullName
    if (!$index -or $index.Length -gt 4MB) { throw 'dist must have a root index.html of at most 4 MiB.' }
    $html = [IO.File]::ReadAllText($index.FullName, [Text.UTF8Encoding]::new($false, $true))
    $html = $html -replace '(?s)<!--.*?-->', ''
    if ($html -notmatch '(?is)<meta(?=\s)(?=[^>]*\sname\s*=\s*(["'']?)application-name\1(?=\s|/?>))(?=[^>]*\scontent\s*=\s*(["'']?)SnowLand\2(?=\s|/?>))[^>]*>') {
        throw 'dist/index.html is missing the SnowLand application-name marker.'
    }

    $allowed = '.html', '.js', '.css', '.png', '.jpg', '.jpeg', '.webp', '.svg'
    $hashes = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    $archive = [IO.Compression.ZipFile]::Open($ZipPath, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in $files) {
            $name = $file.FullName.Substring($Dist.FullName.Length + 1).Replace('\', '/')
            if ($file.Length -gt 100MB -or $name.Length -gt 500 -or $name -cne $name.Trim() -or
                $name -match '[\\:<>|?*\x00-\x1f]|(^|/)\.|[ .](/|$)' -or
                $name -match '^(static|media|private_course_media|private_frontend_releases|admin|api|booking|control)(/|$)' -or
                ($name -cne '_redirects' -and $file.Extension -notin $allowed) -or $hashes.ContainsKey($name)) {
                throw 'dist contains a disallowed file, path, collision or size.'
            }
            $source = $file.OpenRead()
            try {
                $header = New-Object byte[] 4
                $length = $source.Read($header, 0, 4)
                $signature = [BitConverter]::ToString($header, 0, $length)
                if ($signature -match '^(50-4B-(03-04|05-06|07-08)|4D-5A|7F-45-4C-46|23-21|FE-ED-FA-(CE|CF)|(CE|CF)-FA-ED-FE|CA-FE-BA-(BE|BF)|(BE|BF)-BA-FE-CA)') {
                    throw 'dist contains a nested ZIP or executable.'
                }
                $source.Position = [Math]::Max(0, $source.Length - 65557)
                $tail = New-Object byte[] ($source.Length - $source.Position)
                [void]$source.Read($tail, 0, $tail.Length)
                $tailText = [Text.Encoding]::ASCII.GetString($tail)
                $end = $tailText.LastIndexOf("PK$([char]5)$([char]6)", [StringComparison]::Ordinal)
                if ($end -ge 0 -and $end + 22 -le $tail.Length -and $end + 22 + [BitConverter]::ToUInt16($tail, $end + 20) -eq $tail.Length) {
                    throw 'dist contains a nested ZIP.'
                }
                $source.Position = 0
                $hashes.Add($name, (Get-FileHash -InputStream $source -Algorithm SHA256).Hash)
                $source.Position = 0
                $entry = $archive.CreateEntry($name, [IO.Compression.CompressionLevel]::Optimal)
                $entry.LastWriteTime = [DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
                $destination = $entry.Open()
                try { $source.CopyTo($destination) } finally { $destination.Dispose() }
            } finally {
                $source.Dispose()
            }
        }
    } finally {
        $archive.Dispose()
    }

    if ((Get-Item -LiteralPath $ZipPath).Length -gt 768MB) { throw 'ZIP exceeds 768 MiB.' }
    $archive = [IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        if ($archive.Entries.Count -ne $hashes.Count) { throw 'ZIP entry count does not match dist.' }
        foreach ($entry in $archive.Entries) {
            $source = $entry.Open()
            try {
                if ((Get-FileHash -InputStream $source -Algorithm SHA256).Hash -ne $hashes[$entry.FullName]) {
                    throw 'ZIP entry failed round-trip integrity verification.'
                }
            } finally { $source.Dispose() }
        }
    } finally { $archive.Dispose() }
    $hashes.Count
}

function Get-JobStatus($Response, [guid]$Key) {
    try {
        $body = $Response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
        if ($body.request_id -eq $Key.ToString() -and $body.deployment.status -cin @(
                'queued', 'backing_up', 'publishing', 'invalidating', 'cleaning', 'succeeded', 'failed')) {
            return $body.deployment.status
        }
    } catch { return $null }
}

function New-PublisherHttpClient([TimeSpan]$Timeout, [bool]$Loopback, [string]$Token) {
    $handler = [Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $handler.UseCookies = $false
    if ($Loopback) { $handler.UseProxy = $false }
    $client = [Net.Http.HttpClient]::new($handler)
    try {
        $client.Timeout = $Timeout
        $client.DefaultRequestHeaders.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $Token)
        return $client
    } catch {
        $client.Dispose()
        throw 'Could not initialize the publishing HTTP client.'
    }
}

function Wait-PublisherJob($Http, [string]$Url, [guid]$Key, [string]$InitialStatus) {
    $lastStatus = $InitialStatus
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalMinutes -lt 20) {
        $result = $null
        try { $result = $Http.GetAsync($Url).GetAwaiter().GetResult() } catch {
            # A transport failure is safe to retry for GET only.
        }
        if ($result) {
            try {
                $code = [int]$result.StatusCode
                if ($code -eq 200) {
                    $status = Get-JobStatus $result $Key
                    if ($status -and $status -ne $lastStatus) { Write-Host "Job $Key $status"; $lastStatus = $status }
                    if ($status -eq 'succeeded') { return }
                    if ($status -eq 'failed') { throw "Publication job $Key failed. Review its status before submitting again." }
                } elseif ($code -eq 404 -and !$lastStatus -and $timer.Elapsed.TotalSeconds -ge 30) {
                    throw "Job $Key was not found. Check the API origin and request state before submitting again."
                } elseif ($code -lt 500 -and $code -notin @(404, 429)) {
                    throw "Job lookup returned HTTP $code for $Key."
                }
            } finally { $result.Dispose() }
        }
        Start-Sleep -Seconds 2
    }
    throw "Timed out waiting for $Key. Resume with -RequestId $Key."
}

try {
    if ($NewToken) { New-PublisherToken; exit 0 }
    $base = $null
    if (![Uri]::TryCreate($ApiBase, [UriKind]::Absolute, [ref]$base) -or $base.UserInfo -or
        $ApiBase -notmatch '^https?://[^/\\?#]+/?$' -or
        ($base.Scheme -ne 'https' -and $ApiBase -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?/?$')) {
        throw 'ApiBase must be an HTTPS origin or an HTTP origin on 127.0.0.1 or localhost.'
    }
    $origin = $base.GetLeftPart([UriPartial]::Authority)
    $endpoint = "$origin/api/admin/flashfalcon/frontend-releases/cli"

    if ($PSCmdlet.ParameterSetName -eq 'Publish') {
        if ($BuildOnly -and ($DryRun -or $SkipBuild)) { throw 'Use -BuildOnly by itself or with -SkipInstall.' }
        if (!$Worktree) { $Worktree = Split-Path -Parent $PSScriptRoot }
        $root = (Resolve-Path -LiteralPath $Worktree).Path
        $frontend = Join-Path $root 'snowland-frontend'
        $artifactRoot = Join-Path $root 'tmp/snowland-frontend-publish'
        [void][IO.Directory]::CreateDirectory($artifactRoot)
        try {
            $buildLock = [IO.File]::Open((Join-Path $artifactRoot 'build.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
        } catch [IO.IOException] {
            throw 'Cannot lock this worktree for build and packaging. Check for another running publish script.'
        }
        try {
            if (!$SkipBuild) {
                Push-Location -LiteralPath $frontend
                $buildToken = $env:SNOWLAND_FRONTEND_CLI_TOKEN
                try {
                    Remove-Item Env:SNOWLAND_FRONTEND_CLI_TOKEN -ErrorAction SilentlyContinue
                    if (!$SkipInstall) {
                        & npm.cmd ci
                        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
                    }
                    & npm.cmd run build
                    if ($LASTEXITCODE -ne 0) { throw 'npm run build failed.' }
                } finally {
                    Pop-Location
                    if ($null -ne $buildToken) { $env:SNOWLAND_FRONTEND_CLI_TOKEN = $buildToken }
                }
            }
            if ($BuildOnly) { exit 0 }

            $RequestId = [guid]::NewGuid()
            $artifacts = Join-Path $artifactRoot $RequestId.ToString()
            [void][IO.Directory]::CreateDirectory($artifacts)
            $zipPath = Join-Path $artifacts 'archive.zip'
            $count = New-BuildArchive (Get-Item -LiteralPath (Join-Path $frontend 'dist')) $zipPath
        } finally { $buildLock.Dispose() }
        $digest = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        Write-Host "ZIP files: $count SHA-256: $digest"
        Write-Host "ZIP: $zipPath"
        if ($DryRun) { exit 0 }
        @{request_id = $RequestId.ToString(); api_base = $origin; archive_sha256 = $digest} | ConvertTo-Json |
            Set-Content -LiteralPath (Join-Path $artifacts 'request.json') -Encoding UTF8
        Write-Host "Request ID: $RequestId"
    }

    $credential = $env:SNOWLAND_FRONTEND_CLI_TOKEN
    if (!$credential) {
        Initialize-CredentialManager
        $credential = [SnowLandPublishCredentials]::Read($TokenTarget)
    }
    if ($credential -cnotmatch '^[!-~]{1,512}\z') { throw 'A valid publishing token was not found.' }
    Add-Type -AssemblyName System.Net.Http
    $jobUrl = "$endpoint/jobs/$RequestId/"
    $status = $null
    if ($PSCmdlet.ParameterSetName -eq 'Publish') {
        $http = New-PublisherHttpClient ([TimeSpan]::FromMinutes(10)) $base.IsLoopback $credential
        try {
            $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Post, "$endpoint/publish/")
            $response = $null
            try {
                $request.Headers.Add('Idempotency-Key', $RequestId.ToString())
                $request.Content = [Net.Http.MultipartFormDataContent]::new()
                $archiveContent = [Net.Http.StreamContent]::new([IO.File]::OpenRead($zipPath))
                $archiveContent.Headers.ContentType = [Net.Http.Headers.MediaTypeHeaderValue]::new('application/zip')
                $request.Content.Add($archiveContent, 'archive', 'snowland.zip')
                try { $response = $http.SendAsync($request).GetAwaiter().GetResult() } catch {
                    Write-Host 'Upload response unavailable. Checking the same request ID.'
                }
                if ($response) {
                    $code = [int]$response.StatusCode
                    if ($code -eq 202) {
                        $status = Get-JobStatus $response $RequestId
                        if ($status) { Write-Host "Job $RequestId $status" }
                    } elseif ($code -eq 409) {
                        $conflict = $null
                        try { $conflict = ($response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json).code } catch {}
                        if ($conflict -cin @('idempotency_conflict', 'publication_in_progress')) { throw "HTTP 409 $conflict" }
                        throw 'HTTP 409 publication conflict.'
                    } elseif ($code -lt 500 -and $code -ne 408) {
                        throw "Upload returned HTTP $code."
                    }
                }
            } finally {
                $request.Dispose()
                if ($response) { $response.Dispose() }
            }
        } finally { $http.Dispose() }
    }

    # Give polling its own short per-request timeout. HttpClient settings freeze after the POST.
    $pollHttp = New-PublisherHttpClient ([TimeSpan]::FromSeconds(15)) $base.IsLoopback $credential
    try {
        Wait-PublisherJob $pollHttp $jobUrl $RequestId $status
    } finally { $pollHttp.Dispose() }
    exit 0
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
