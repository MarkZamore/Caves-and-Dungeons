param(
    [Parameter(Mandatory)][string]$Run,
    [Parameter(Mandatory)][string]$Label,
    [Parameter(Mandatory)][string]$World,
    [Parameter(Mandatory)][long]$Seed,
    [switch]$Reopen
)
$ErrorActionPreference = 'Stop'
$runRoot = (Resolve-Path -LiteralPath $Run).Path
if ($Label -notmatch '^[a-zA-Z0-9-]+$' -or $World -notmatch '^CAD-QA-[a-zA-Z0-9-]+$') {
    throw 'Use a disposable CAD QA label and world.'
}
$fixture = Join-Path $runRoot 'fixture'
$evidence = Join-Path $fixture "evidence/$Label"
$agent = Join-Path $runRoot 'probe/cad-native-client-checks-1.0.0.jar'
$deadline = [DateTime]::UtcNow.AddMinutes(10)
while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-Path -LiteralPath "$evidence/exit.json") {
        throw "Client exited before checking $Label"
    }
    if ((Test-Path -LiteralPath "$evidence/run.json") -and (Test-Path -LiteralPath "$evidence/console.log") -and
        (Select-String -LiteralPath "$evidence/console.log" -Pattern 'Sound engine started' -Quiet)) {
        $child = Get-Content -LiteralPath "$evidence/run.json" -Raw | ConvertFrom-Json
        $gameRoot = (Resolve-Path -LiteralPath $child.GameDirectory).Path
        if (!$gameRoot.StartsWith($fixture + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'QA game directory is outside the fixture.'
        }
        $mode = if ($Reopen) { 'load-existing' } else { 'world-generation' }
        @(
            "gameDirectory=$($gameRoot.Replace('\', '/'))"
            "output=$($evidence.Replace('\', '/'))/worldgen.jsonl"
            "inputSnapshot=$($fixture.Replace('\', '/'))/source-snapshot.json"
            "world=$World"
            "mode=$mode"
            "language=ru_ru"
            "seed=$Seed"
            "expectedGenerator=net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator"
            "verifyStarterBunker=true"
        ) | Set-Content -LiteralPath "$evidence/checks.properties"
        java -cp $agent dev.lanminecraft.cadqa.AttachClientChecks $child.ProcessId $agent "$evidence/checks.properties"
        if ($LASTEXITCODE -ne 0) { throw "Attach failed for $Label" }
        return
    }
    Start-Sleep -Seconds 4
}
throw "Client readiness timed out for $Label"
