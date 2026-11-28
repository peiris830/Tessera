<#
.SYNOPSIS
    Build and deploy one Tessera stack with SAM.

.DESCRIPTION
    Services upload their code to the artifacts bucket from the shared stack. Its name contains
    the AWS account ID, so it isn't committed in samconfig.toml: this script reads it from SSM
    (/tessera/<env>/artifacts/bucket-name) and passes it to `sam deploy`.
    Everything else (stack name, region, parameters) comes from each folder's samconfig.toml,
    and `sam deploy` still shows the change set and asks before applying it.

.EXAMPLE
    $env:AWS_PROFILE = "tessera-dev"
    .\scripts\deploy.ps1 shared       # infra/shared (only inline code, so no build or bucket needed)
    .\scripts\deploy.ps1 catalogue    # services/catalogue: sam build, then sam deploy
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("shared", "catalogue")]
    [string]$Stack,

    [ValidateSet("dev")]
    [string]$Environment = "dev"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    # Run a native command and stop if it fails ($ErrorActionPreference doesn't cover exe exit codes).
    param([string]$Description, [scriptblock]$Command)
    Write-Host "==> $Description" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed (exit code $LASTEXITCODE)" }
}

Invoke-Checked "Checking AWS identity" { aws sts get-caller-identity --query Arn --output text }

if ($Stack -eq "shared") {
    Push-Location (Join-Path $repo "infra\shared")
    try { Invoke-Checked "sam deploy (shared)" { sam deploy } }
    finally { Pop-Location }
    return
}

$bucket = aws ssm get-parameter --name "/tessera/$Environment/artifacts/bucket-name" `
    --query Parameter.Value --output text
if ($LASTEXITCODE -ne 0 -or -not $bucket) {
    throw "Artifacts bucket parameter not found: deploy the shared stack first (.\scripts\deploy.ps1 shared)"
}

Push-Location (Join-Path $repo "services\$Stack")
try {
    Invoke-Checked "sam build ($Stack; Docker must be running)" { sam build }
    Invoke-Checked "sam deploy ($Stack -> s3://$bucket)" { sam deploy --s3-bucket $bucket }
}
finally { Pop-Location }
