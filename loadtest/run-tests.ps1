# Helios Load Test Runner Scripts
# Quick scripts to run different test scenarios

param(
    [Parameter(Position=0)]
    [ValidateSet("mixed", "read", "write", "ramp", "wave", "spike", "help")]
    [string]$Pattern = "help",
    
    [string]$Host = "http://localhost:8000",
    [int]$Users = 50,
    [int]$SpawnRate = 5,
    [string]$Duration = "10m",
    [switch]$Headless,
    [string]$CsvOutput = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocustDir = Join-Path $ScriptDir "locustfiles"

function Show-Help {
    Write-Host @"

Helios Load Test Runner
=======================

Usage: .\run-tests.ps1 <pattern> [options]

Patterns:
  mixed   - Realistic mix of all user types (default behavior)
  read    - Read-heavy traffic (browsers + searchers)
  write   - Write-heavy traffic (buyers + admins)
  ramp    - Gradual ramp up/down pattern
  wave    - Sinusoidal wave pattern
  spike   - Flash-sale spike pattern
  help    - Show this help

Options:
  -Host <url>       Target API URL (default: http://localhost:8000)
  -Users <n>        Number of users (default: 50)
  -SpawnRate <n>    Users per second (default: 5)
  -Duration <time>  Test duration, e.g. 10m, 1h (default: 10m)
  -Headless         Run without web UI
  -CsvOutput <path> Output CSV results to path

Examples:
  .\run-tests.ps1 mixed                          # Interactive mixed traffic
  .\run-tests.ps1 ramp -Headless -Duration 20m  # Headless ramp pattern
  .\run-tests.ps1 spike -Users 100 -CsvOutput results/spike

"@
}

function Get-LocustFile {
    param([string]$Pattern)
    
    switch ($Pattern) {
        "mixed"  { return "locustfile.py" }
        "read"   { return "read_heavy.py" }
        "write"  { return "write_heavy.py" }
        "ramp"   { return "ramp_pattern.py" }
        "wave"   { return "wave_pattern.py" }
        "spike"  { return "spike_pattern.py" }
        default  { return "locustfile.py" }
    }
}

if ($Pattern -eq "help") {
    Show-Help
    exit 0
}

$LocustFile = Get-LocustFile -Pattern $Pattern
$FullPath = Join-Path $LocustDir $LocustFile

if (-not (Test-Path $FullPath)) {
    Write-Error "Locust file not found: $FullPath"
    exit 1
}

Write-Host "`n🚀 Starting Helios Load Test" -ForegroundColor Cyan
Write-Host "   Pattern: $Pattern"
Write-Host "   File: $LocustFile"
Write-Host "   Host: $Host"
Write-Host "   Users: $Users"
Write-Host "   Spawn Rate: $SpawnRate/sec"
Write-Host "   Duration: $Duration"
Write-Host ""

# Build command
$cmd = @(
    "locust",
    "-f", $FullPath,
    "--host=$Host"
)

if ($Headless) {
    $cmd += "--headless"
    $cmd += "-u", $Users
    $cmd += "-r", $SpawnRate
    $cmd += "-t", $Duration
}

if ($CsvOutput) {
    $cmd += "--csv=$CsvOutput"
}

# Set PYTHONPATH for imports
$env:PYTHONPATH = $LocustDir

Write-Host "Running: $($cmd -join ' ')" -ForegroundColor DarkGray
Write-Host ""

& $cmd[0] $cmd[1..($cmd.Length-1)]
