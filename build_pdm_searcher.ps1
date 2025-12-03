$sourceFile = "backend\PdmSearcher\Program.cs"
if (!(Test-Path $sourceFile)) {
    Write-Host "Source file not found: $sourceFile"
    exit 1
}
$code = Get-Content $sourceFile -Raw

$outputDir = "backend\PdmSearcher"
if (!(Test-Path $outputDir)) { New-Item -ItemType Directory -Force -Path $outputDir }

$frameworkPath = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319"
$assemblies = @(
    "$frameworkPath\System.Core.dll",
    "$frameworkPath\Microsoft.CSharp.dll",
    "$frameworkPath\System.dll"
)
$params = New-Object System.CodeDom.Compiler.CompilerParameters
$params.GenerateExecutable = $true
$params.OutputAssembly = "$outputDir\PdmSearcher.exe"
$params.ReferencedAssemblies.AddRange($assemblies)

$provider = New-Object Microsoft.CSharp.CSharpCodeProvider
$results = $provider.CompileAssemblyFromSource($params, $code)

if ($results.Errors.HasErrors) {
    $results.Errors | ForEach-Object { Write-Host $_.ErrorText }
    exit 1
}
else {
    Write-Host "Build Success: $outputDir\PdmSearcher.exe"
}
