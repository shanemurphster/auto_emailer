Param(
    [string]$NamesFile = "michigan_names.txt",
    [string]$BaseUrl = "https://michigan.law.umich.edu/faculty-and-scholarship/our-faculty/",
    [string]$OutCsv = "data/michigan_contacts.csv",
    [string]$AppendTo = "data/law_contacts.csv",
    [int]$DelayMs = 800
)

function Slugify([string]$name) {
    $s = $name.ToLower().Trim()
    # replace non-alphanumeric with dash
    $s = -join ($s.ToCharArray() | ForEach-Object {
        if ($_ -match '[a-z0-9]') { $_ } else { '-' }
    })
    # collapse multiple dashes
    $s = $s -replace '-{2,}', '-'
    $s = $s.Trim('-')
    return $s
}

if (-not (Test-Path $NamesFile)) {
    Write-Error "Names file not found: $NamesFile"
    exit 1
}

$names = Get-Content -Path $NamesFile | Where-Object { $_.Trim() -ne "" }
Write-Output "Read $($names.Count) names from $NamesFile"

$results = @()
foreach ($name in $names) {
    $slug = Slugify $name
    $profileUrl = ($BaseUrl.TrimEnd('/') + '/' + $slug)
    Write-Output "Fetching $profileUrl"
    try {
        Start-Sleep -Milliseconds $DelayMs
        $resp = Invoke-WebRequest -Uri $profileUrl -Headers @{
            "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            "Accept" = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            "Referer" = "https://www.google.com/"
        } -UseBasicParsing -ErrorAction Stop
        $content = $resp.Content
        # regex to find mailto href
        $m = [regex]::Match($content, 'mailto:([A-Za-z0-9\.\!\#\$\%\&''\*\+\/=\?\^_`\{\|\}~-]+@[A-Za-z0-9\.-]+\.[A-Za-z]{2,})', 'IgnoreCase')
        if ($m.Success) {
            $email = $m.Groups[1].Value
            Write-Output "Found: $name -> $email"
            $results += ,@($name, $email, "University of Michigan", $profileUrl)
        } else {
            Write-Output "No email for: $name"
        }
    } catch {
        Write-Warning "Error fetching $profileUrl : $_"
    }
}

if ($results.Count -gt 0) {
    # write per-site CSV
    $header = "name,email,affiliation,source_url"
    $OutCsvDir = Split-Path $OutCsv -Parent
    if ($OutCsvDir -and -not (Test-Path $OutCsvDir)) { New-Item -ItemType Directory -Path $OutCsvDir | Out-Null }
    Set-Content -Path $OutCsv -Value $header
    foreach ($r in $results) {
        $line = "{0},{1},{2},{3}" -f $r[0], $r[1], $r[2], $r[3]
        Add-Content -Path $OutCsv -Value $line
    }

    # append to global CSV, avoiding duplicates by email
    $existing = @{}
    if (Test-Path $AppendTo) {
        Get-Content $AppendTo | Select-Object -Skip 1 | ForEach-Object {
            $parts = $_ -split ","
            if ($parts.Count -ge 2) { $existing[$parts[1].ToLower().Trim()] = $true }
        }
    } else {
        # write header if file doesn't exist
        Set-Content -Path $AppendTo -Value $header
    }
    foreach ($r in $results) {
        $emailKey = $r[1].ToLower().Trim()
        if (-not $existing.ContainsKey($emailKey)) {
            $line = "{0},{1},{2},{3}" -f $r[0], $r[1], $r[2], $r[3]
            Add-Content -Path $AppendTo -Value $line
            $existing[$emailKey] = $true
        } else {
            Write-Output "Skipping duplicate email: $($r[1])"
        }
    }
    Write-Output "Wrote $($results.Count) results to $OutCsv and appended new to $AppendTo"
} else {
    Write-Output "No results found."
}


