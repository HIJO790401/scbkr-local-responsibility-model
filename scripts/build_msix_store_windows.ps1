param(
  [string]$IdentityName = "shenyao888pi.SCBKRResponsibilityChainLanguageModel",
  [string]$Publisher = "CN=FEB91682-9693-4284-BDDE-2EC33CF8EF23",
  [string]$PublisherDisplayName = "shenyao888pi",
  [string]$DisplayName = "SCBKR Responsibility Chain Language Model",
  [string]$Version = "2.3.0.0",
  [string]$ReleaseDir = "dist\scbkr-windows-desktop-rc",
  [string]$OutputDir = "dist\scbkr-windows-store-msix",
  [switch]$SkipDesktopBuild
)

$ErrorActionPreference = "Stop"

function Resolve-DistPath {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot
  )

  $distRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "dist"))
  $resolved = if ([System.IO.Path]::IsPathRooted($Path)) {
    [System.IO.Path]::GetFullPath($Path)
  } else {
    [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
  }
  $distPrefix = $distRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
  if (-not $resolved.StartsWith($distPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Store package paths must stay inside the repository dist directory: $resolved"
  }
  return $resolved
}

function ConvertTo-XmlText {
  param([Parameter(Mandatory = $true)][string]$Value)
  return [System.Security.SecurityElement]::Escape($Value)
}

function Save-LogoAsset {
  param(
    [Parameter(Mandatory = $true)]
    [System.Drawing.Image]$Source,
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [int]$Width,
    [Parameter(Mandatory = $true)]
    [int]$Height,
    [Parameter(Mandatory = $true)]
    [int]$LogoSize
  )

  $bitmap = New-Object System.Drawing.Bitmap($Width, $Height)
  try {
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
      $graphics.Clear([System.Drawing.Color]::Transparent)
      $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
      $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
      $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
      $x = [int](($Width - $LogoSize) / 2)
      $y = [int](($Height - $LogoSize) / 2)
      $graphics.DrawImage($Source, $x, $y, $LogoSize, $LogoSize)
    } finally {
      $graphics.Dispose()
    }
    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $bitmap.Dispose()
  }
}

if ($env:OS -ne "Windows_NT") {
  throw "The Microsoft Store MSIX build requires Windows."
}
if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
  throw "MSIX Version must contain four numeric parts, for example 2.3.0.0."
}
if ($IdentityName -notmatch '^[A-Za-z0-9.-]+$') {
  throw "IdentityName must be copied exactly from Partner Center and contain only letters, numbers, periods, or hyphens."
}
if ([string]::IsNullOrWhiteSpace($Publisher) -or $Publisher -notmatch '=') {
  throw "Publisher must be copied exactly from Partner Center, for example CN=..."
}

$repoRoot = (Resolve-Path -LiteralPath ".").Path
$releaseRoot = Resolve-DistPath -Path $ReleaseDir -RepoRoot $repoRoot
$outputRoot = Resolve-DistPath -Path $OutputDir -RepoRoot $repoRoot
$layoutRoot = Join-Path $outputRoot "layout"
$verifyRoot = Join-Path $outputRoot "verified-unpack"
$packagePath = Join-Path $outputRoot "SCBKR_Responsibility_Chain_Language_Model_${Version}_x64.msix"

if (-not $SkipDesktopBuild) {
  & (Join-Path $repoRoot "scripts\build_desktop_release_windows.ps1") -ReleaseDir $ReleaseDir
  if ($LASTEXITCODE -ne 0) {
    throw "The Windows desktop release build failed before MSIX packaging."
  }
}

$desktopExe = Join-Path $releaseRoot "desktop\scbkr_desktop.exe"
$sidecarExe = Join-Path $releaseRoot "scbkr-api.exe"
$iconPath = Join-Path $repoRoot "apps\desktop\src-tauri\icons\scbkr-app-icon.png"
foreach ($required in @($desktopExe, $sidecarExe, $iconPath)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw "Required Store package input is missing: $required"
  }
}

$sdkBins = @(Get-ChildItem -LiteralPath "C:\Program Files (x86)\Windows Kits\10\bin" -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' } |
  Sort-Object { [version]$_.Name } -Descending)
$makeAppx = $null
foreach ($sdkBin in $sdkBins) {
  $candidate = Join-Path $sdkBin.FullName "x64\makeappx.exe"
  if (Test-Path -LiteralPath $candidate) {
    $makeAppx = $candidate
    break
  }
}
if (-not $makeAppx) {
  throw "MakeAppx.exe was not found. Install the Windows SDK before building the Store package."
}

if (Test-Path -LiteralPath $outputRoot) {
  Remove-Item -LiteralPath $outputRoot -Recurse -Force
}
New-Item -ItemType Directory -Path (Join-Path $layoutRoot "Assets") -Force | Out-Null

Copy-Item -LiteralPath $desktopExe -Destination (Join-Path $layoutRoot "scbkr_desktop.exe")
Copy-Item -LiteralPath $sidecarExe -Destination (Join-Path $layoutRoot "scbkr-api.exe")

Add-Type -AssemblyName System.Drawing
$icon = [System.Drawing.Image]::FromFile($iconPath)
try {
  $assetsDir = Join-Path $layoutRoot "Assets"
  Save-LogoAsset -Source $icon -Path (Join-Path $assetsDir "StoreLogo.png") -Width 50 -Height 50 -LogoSize 46
  Save-LogoAsset -Source $icon -Path (Join-Path $assetsDir "Square44x44Logo.png") -Width 44 -Height 44 -LogoSize 40
  Save-LogoAsset -Source $icon -Path (Join-Path $assetsDir "Square150x150Logo.png") -Width 150 -Height 150 -LogoSize 136
  Save-LogoAsset -Source $icon -Path (Join-Path $assetsDir "Wide310x150Logo.png") -Width 310 -Height 150 -LogoSize 132
  Save-LogoAsset -Source $icon -Path (Join-Path $assetsDir "Square310x310Logo.png") -Width 310 -Height 310 -LogoSize 280
} finally {
  $icon.Dispose()
}

$identityXml = ConvertTo-XmlText $IdentityName
$publisherXml = ConvertTo-XmlText $Publisher
$publisherDisplayXml = ConvertTo-XmlText $PublisherDisplayName
$displayNameXml = ConvertTo-XmlText $DisplayName
$descriptionXml = ConvertTo-XmlText "Local responsibility-rule operating system with model-assisted SCBKR rule authoring."
$manifest = @"
<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:uap10="http://schemas.microsoft.com/appx/manifest/uap/windows10/10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  IgnorableNamespaces="uap uap10 rescap">
  <Identity Name="$identityXml" Publisher="$publisherXml" Version="$Version" ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>$displayNameXml</DisplayName>
    <PublisherDisplayName>$publisherDisplayXml</PublisherDisplayName>
    <Description>$descriptionXml</Description>
    <Logo>Assets\StoreLogo.png</Logo>
  </Properties>
  <Resources>
    <Resource Language="zh-tw" />
    <Resource Language="en-us" />
  </Resources>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Applications>
    <Application
      Id="SCBKR"
      Executable="scbkr_desktop.exe"
      uap10:RuntimeBehavior="packagedClassicApp"
      uap10:TrustLevel="mediumIL">
      <uap:VisualElements
        DisplayName="$displayNameXml"
        Description="$descriptionXml"
        BackgroundColor="transparent"
        Square150x150Logo="Assets\Square150x150Logo.png"
        Square44x44Logo="Assets\Square44x44Logo.png">
        <uap:DefaultTile
          ShortName="SCBKR"
          Wide310x150Logo="Assets\Wide310x150Logo.png"
          Square310x310Logo="Assets\Square310x310Logo.png" />
      </uap:VisualElements>
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
"@
$manifestPath = Join-Path $layoutRoot "AppxManifest.xml"
[System.IO.File]::WriteAllText($manifestPath, $manifest, (New-Object System.Text.UTF8Encoding($false)))

& $makeAppx pack /d $layoutRoot /p $packagePath /o
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $packagePath)) {
  throw "MakeAppx failed to create the Store MSIX package."
}
& $makeAppx unpack /p $packagePath /d $verifyRoot /o
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $verifyRoot "AppxManifest.xml"))) {
  throw "The generated MSIX could not be unpacked for verification."
}
foreach ($requiredPackageFile in @("scbkr_desktop.exe", "scbkr-api.exe")) {
  if (-not (Test-Path -LiteralPath (Join-Path $verifyRoot $requiredPackageFile))) {
    throw "The generated MSIX is missing a required runtime file: $requiredPackageFile"
  }
}

$package = Get-Item -LiteralPath $packagePath
$hash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash
$metadata = [ordered]@{
  product = "SCBKR Responsibility Chain Language Model"
  store_id = "9N1SMMBL6J4D"
  edition = "FREE"
  version = $Version
  architecture = "x64"
  identity_name = $IdentityName
  publisher = $Publisher
  publisher_display_name = $PublisherDisplayName
  package = $package.Name
  bytes = $package.Length
  sha256 = $hash
  built_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  makeappx = $makeAppx
  signed = $false
  signing_note = "Microsoft Store re-signs accepted MSIX packages. Sign separately only for local sideload testing."
  bundled_model = $false
  bundled_api_key = $false
  restricted_capability = "runFullTrust"
}
$metadata | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $outputRoot "STORE_PACKAGE_METADATA.json") -Encoding UTF8

Write-Host "SCBKR Microsoft Store MSIX created and unpack-verified." -ForegroundColor Green
Write-Host "Package: $packagePath"
Write-Host "SHA-256: $hash"
