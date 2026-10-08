$ErrorActionPreference = "Stop"
$fontsDir = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Fonts"
$regPath = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
$fonts = @(
  @{
    Display = "Atkinson Hyperlegible Regular"
    File = "AtkinsonHyperlegible-Regular.otf"
    Url = "https://raw.githubusercontent.com/googlefonts/atkinson-hyperlegible/main/fonts/otf/AtkinsonHyperlegible-Regular.otf"
  },
  @{
    Display = "Atkinson Hyperlegible Bold"
    File = "AtkinsonHyperlegible-Bold.otf"
    Url = "https://raw.githubusercontent.com/googlefonts/atkinson-hyperlegible/main/fonts/otf/AtkinsonHyperlegible-Bold.otf"
  }
)

New-Item -ItemType Directory -Force -Path $fontsDir | Out-Null
if (-not (Test-Path $regPath)) { New-Item -Path $regPath -Force | Out-Null }

foreach ($font in $fonts) {
  $dest = Join-Path $fontsDir $font.File
  if (-not (Test-Path $dest)) {
    Write-Host "Baixando $($font.Display) do repositório oficial..."
    $tmp = Join-Path $env:TEMP $font.File
    Invoke-WebRequest -Uri $font.Url -OutFile $tmp -UseBasicParsing
    Copy-Item $tmp $dest -Force
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  }
  New-ItemProperty -Path $regPath -Name "$($font.Display) (OpenType)" -Value $dest -PropertyType String -Force | Out-Null
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class FontBroadcast {
  [DllImport("user32.dll", SetLastError=true)]
  public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@ -ErrorAction SilentlyContinue
[FontBroadcast]::SendMessage([IntPtr]0xffff, 0x001D, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null

Write-Host "Fonte instalada para o usuário atual: Atkinson Hyperlegible (Regular + Bold)"
Write-Host "Feche e abra novamente o navegador se ele já estava aberto."
exit 0
