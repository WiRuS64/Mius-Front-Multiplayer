# Small driver for one running test game: drive.ps1 -Game <test copy> -ProcId <pid> -Do "key:27;shot:name;click:0.5,0.5;wait:2"
param([Parameter(Mandatory=$true)][string]$Game, [int]$ProcId, [string]$Do, [string]$Out = "$PSScriptRoot\runs\drive")
. "$Game\_mp_research\tools\auto.ps1"
$script:Game = $Game
New-Item -ItemType Directory -Force $Out | Out-Null
$script:Shots = $Out
$p = Get-Process -Id $ProcId
foreach ($d in $Do.Split(";")) {
    $k, $v = $d.Split(":", 2)
    switch ($k) {
        "key"   { Press-Key $p ([int]$v) }
        "shot"  { Save-Shot $p $v }
        "click" { $x, $y = $v.Split(","); Click-Game $p ([double]$x) ([double]$y) | Out-Null }
        "wait"  { Start-Sleep -Milliseconds ([int]([double]$v * 1000)) }
        "cmd"   { Send-Command $p $v }
    }
}
