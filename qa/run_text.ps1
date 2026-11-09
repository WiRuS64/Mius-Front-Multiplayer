# The mod's texts in the game's language and font: starts one game, takes the game's own frames of the main
# menu, the multiplayer panel, the join screen and the lobby, and checks the module's log ("text:" lines).
#   run_text.ps1 [-Game <test copy>] [-Lang ru|en|""] [-Tag name] [-ListFonts]
# -Lang "" leaves the choice to the game (root\engine.txt); ru / en set MP_LANG.
param([string]$Game = "$env:USERPROFILE\Desktop\миус тесты", [string]$Lang = "", [string]$Tag = "text",
      [switch]$ListFonts)
$ErrorActionPreference = "Continue"
$Game = (Resolve-Path $Game).Path
. "$Game\_mp_research\tools\auto.ps1"
$script:Game = $Game
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = "$PSScriptRoot\runs\$Tag-$stamp"
New-Item -ItemType Directory -Force $runDir | Out-Null
$script:Shots = $runDir
if (Get-Process starter_x64 -ErrorAction SilentlyContinue) { "A game instance is already running; not touching it. RESULT: SKIP"; exit 2 }

$env_ = @{}
if ($Lang) { $env_["MP_LANG"] = $Lang }
if ($ListFonts) { $env_["MP_LIST_FONTS"] = "1" }
# the join below makes the mod remember 127.0.0.1:1 as the last host; put the old file back afterwards
$lastHost = "$Game\users\mp_last_host.txt"
$lastHostWas = if (Test-Path $lastHost) { [IO.File]::ReadAllBytes($lastHost) } else { $null }
$p = Start-Game "" $env_
"game pid $($p.Id)"
$log = Get-MpLog $p "opgame"
try {
    Check "the menu program is up" ([bool](Wait-Log $log 'render pipeline reached' 90))
    Start-Sleep 8
    [void](Save-Shot $p "1_main")
    Check "the module chose a language" ([bool](Wait-Log $log 'text: language' 20))
    Check "the game's fonts were read" ([bool](Wait-Log $log "text: the game's font \w+ loaded" 5))
    Check "no font failed to load" (-not (Select-String -Path $log -Pattern "could NOT be read|fonts not found" -Quiet))
    # the panel and the join screen: clicks at fractions of the window, as the mod's own test_menu.ps1 does
    "click MULTIPLAYER: $(Click-Game $p 0.5 0.129)"   # the entry in the main menu
    Check "the main menu entry opens the panel" ([bool](Wait-Log $log 'multiplayer menu opened' 8))
    Start-Sleep 1
    [void](Save-Shot $p "2_panel")
    "click JOIN A GAME: $(Click-Game $p 0.56 0.609)"
    Start-Sleep 1
    [void](Save-Shot $p "3_join")
    Send-Command $p "connect 127.0.0.1:1"; Start-Sleep 12
    [void](Save-Shot $p "4_lobby")
    Check "the frames were captured" ((Get-ChildItem "$runDir\*.png").Count -eq 4)
} finally {
    Stop-Game $p
    Start-Sleep 2
    if ($lastHostWas) { [IO.File]::WriteAllBytes($lastHost, $lastHostWas) } else { Remove-Item $lastHost -ErrorAction SilentlyContinue }
    Copy-Item $log $runDir -ErrorAction SilentlyContinue
    Select-String -Path $log -Pattern 'text:' | ForEach-Object { $_.Line } | Select-Object -First 400 | Set-Content "$runDir\text_lines.txt" -Encoding utf8
    Show-Results
    "run folder: $runDir"
}
