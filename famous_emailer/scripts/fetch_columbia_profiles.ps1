param(
    [Parameter(Mandatory=$false)]
    [string] $NamesFile = "data/columbia_names.csv",
    [Parameter(Mandatory=$false)]
    [string] $OutputCsv = "data/columbia_contacts_ps.csv"
)

# PowerShell fetcher for Columbia profile pages.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/fetch_columbia_profiles.ps1 -NamesFile data/columbia_names.csv -OutputCsv data/columbia_contacts_ps.csv

if (-not (Test-Path $NamesFile)) {
    Write-Error "Names file not found: $NamesFile"
    exit 2
}

$userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

$rows = Import-Csv -Path $NamesFile

$results = @()

foreach ($r in $rows) {
    $name = $r.name
    $profile = $r.profile_url
    if (-not $profile) { continue }
    Write-Host "Fetching $profile"
    try {
        $resp = Invoke-WebRequest -Uri $profile -Headers @{ "User-Agent" = $userAgent } -TimeoutSec 15
        $content = $resp.Content
    } catch {
        Write-Warning "Failed to fetch $profile : $_"
        continue
    }

    # find mailto: occurrences
    $matches = Select-String -InputObject $content -Pattern 'mailto:([^\\"\']+)' -AllMatches
    if ($matches.Matches.Count -eq 0) {
        Write-Host "  no mailto found"
        continue
    }

    foreach ($m in $matches.Matches) {
        $email = $m.Groups[1].Value
        # clean query params if present
        if ($email -match '\?') {
            $email = $email.Split('?')[0]
        }
        $results += [PSCustomObject]@{
            name = $name
            email = $email
            profile_url = $profile
            source_url = $profile
        }
        Write-Host "  found $email"
    }
}

if ($results.Count -gt 0) {
    if (Test-Path $OutputCsv) {
        $results | Export-Csv -Path $OutputCsv -NoTypeInformation -Append
    } else {
        $results | Export-Csv -Path $OutputCsv -NoTypeInformation
    }
    Write-Host "Wrote $($results.Count) rows to $OutputCsv"
} else {
    Write-Host "No emails found."
}


