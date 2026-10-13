$ErrorActionPreference='Stop'
$publish=Join-Path $PSScriptRoot 'publish'
New-Item -ItemType Directory -Path $publish -Force | Out-Null
$sdk=Get-Command dotnet -ErrorAction SilentlyContinue
if($sdk -and (& dotnet --list-sdks 2>$null)){
  dotnet publish "$PSScriptRoot\LeanControl.Launcher.csproj" -c Release -o $publish
}else{
  $csc=Get-ChildItem "$env:WINDIR\Microsoft.NET\Framework64" -Filter csc.exe -Recurse | Sort-Object FullName -Descending | Select-Object -First 1
  if(-not $csc){throw 'Instale o .NET 8 SDK ou habilite o compilador .NET Framework.'}
  & $csc.FullName /nologo /target:winexe /out:"$publish\Lean Control.exe" /reference:System.Windows.Forms.dll /reference:System.dll "$PSScriptRoot\Program.cs"
  Copy-Item "$PSScriptRoot\LeanControl.Launcher.json" $publish -Force
}
Write-Host "Launcher criado em $publish\Lean Control.exe"
