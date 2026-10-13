param(
  [Parameter(Mandatory=$true)][string]$Name,
  [Parameter(Mandatory=$true)][uri]$Url,
  [int]$MaxBytes = 1048576,
  [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http

$root = '[project root]\research\template-batch-02'
$cache = Join-Path $root 'cache'
$ledger = Join-Path $root 'acquisition.jsonl'
if ($Name -notmatch '^[A-Za-z0-9._-]+$') { throw 'Name must be a simple cache alias.' }
if ($MaxBytes -lt 1 -or $MaxBytes -gt 5242880) { throw 'MaxBytes must be between 1 and 5 MiB.' }
New-Item -ItemType Directory -Force -Path $cache | Out-Null

$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.AllowAutoRedirect = $false
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
$client.DefaultRequestHeaders.AcceptEncoding.ParseAdd('identity')
$stamp = [DateTimeOffset]::UtcNow.ToString('o')
$status = $null
$bytes = [byte[]]@()
$redirect = $false
$location = $null
$errorClass = $null
$sizeLimited = $false
$cachePath = $null
$sha256 = $null
$response = $null

try {
  $response = $client.GetAsync($Url, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
  $status = [int]$response.StatusCode
  $redirect = $status -ge 300 -and $status -lt 400
  if ($redirect -and $response.Headers.Location) { $location = $response.Headers.Location.ToString() }
  if ($status -eq 200) {
    $length = $response.Content.Headers.ContentLength
    if ($null -ne $length -and $length -gt $MaxBytes) {
      $sizeLimited = $true
    } else {
      $inputStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
      $memory = [System.IO.MemoryStream]::new()
      $buffer = [byte[]]::new(65536)
      while (($n = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
        if ($memory.Length + $n -gt $MaxBytes) { $sizeLimited = $true; break }
        $memory.Write($buffer, 0, $n)
      }
      $inputStream.Dispose()
      if (-not $sizeLimited) { $bytes = $memory.ToArray() }
      $memory.Dispose()
    }
  }
} catch {
  $errorClass = $_.Exception.GetType().Name
} finally {
  if ($response) { $response.Dispose() }
  $client.Dispose()
  $handler.Dispose()
}

if ($bytes.Length -gt 0) {
  $sha256 = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
  $fileName = "$Name.bin"
  $fullPath = Join-Path $cache $fileName
  $stream = [System.IO.File]::Open($fullPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
  try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
  $cachePath = "cache/$fileName"
}

$record = [ordered]@{
  retrieved_utc = $stamp
  url = $Url.AbsoluteUri
  http_status = $status
  bytes = $bytes.Length
  sha256 = $sha256
  redirect_observed = $redirect
  location_header = $location
  size_limit_exceeded = $sizeLimited
  cache_path = $cachePath
  error_class = $errorClass
}
Add-Content -LiteralPath $ledger -Value (ConvertTo-Json -InputObject $record -Depth 4 -Compress)
[pscustomobject]@{name=$Name;http_status=$status;bytes=$bytes.Length;redirect=$redirect;size_limit_exceeded=$sizeLimited;cache_path=$cachePath;sha256=$sha256;error_class=$errorClass}
