# MiusPlayer-Port 2.2.2

Two-player multiplayer (versus) for **Graviteam Tactics: Mius-Front**, ported to the current Steam build.

This is [VampyrCat/MiusPlayer](https://github.com/VampyrCat/MiusPlayer) "release 2" (mpmod1, network version 20,
CC0). The original targets a different compile of build 3598 than the one Steam ships now, so on the current game
many of its hooks were switched off: the shared Start button, hit sync, the crash guard. Battles never left
deployment. This port fixes that, one sync bug, one crash between two PCs and trenches dug twice in operation battles, and
shows the ping to the other player.

| | |
|---|---|
| Version | **2.2.2** (= MiusPlayer release 2 + port to Steam `public` + static-emplacement fix + ping display + vehicle render-handle crash fix + no second stamping of the other game's trenches) |
| Game | Graviteam Tactics: Mius-Front, Steam app 312980, branch `public`, buildid 15814271 (GRAVITECH3 6.00, assembly 3598, compiled 2024-09-24) |
| Not for | the Steam `public_beta` branch (untested), other stores (untested) |
| `basic_network.codelib` SHA-256 | `9c813cda8229ee1423857b084ce334cb393ed65698a864093ce432b24f229657` |
| License | CC0 1.0, like the original |

**Русский:** порт мультиплеер-мода MiusPlayer (релиз 2) на текущую Steam-версию игры (ветка `public`, buildid
15814271). Установка как у оригинала: папку `mpmod1` положить в папку игры и запустить
`mpmod1\Enable_Multiplayer.bat`. У обоих игроков должен быть один и тот же файл (SHA-256 выше). В 2.2.0 справа от
верхней строки мультиплеера показывается пинг до другого игрока. 2.2.1 исправляет вылет хоста в бою между двумя
разными ПК (игра падала при движении техники другого игрока, например при конце расстановки): обновиться должны оба.
2.2.2: в бою операции окопы, которые игра ставит сама при постройке боя, больше не вдавливаются второй раз по
списку другой игры (у хоста они уходили всё глубже: ямы с отвесными стенками). Обновиться должны оба.

## Install

1. Download `MiusPlayer-Port-2.2.2.zip` from Releases and unpack it. Copy the `mpmod1` folder into the game folder
   (the one with `starter_x64.exe`; Steam: right-click the game, Manage, Browse local files).
2. Close the game and run `mpmod1\Enable_Multiplayer.bat`. It checks the game files against
   `mpmod1\game_build_3598.sha256` (in this port: the hashes of Steam buildid 15814271) and copies five files into the
   game. No game file is changed. `mpmod1\Disable_Multiplayer.bat` removes them again.
3. Both players use the same version. Everything else (hosting, joining, Steam friends, UPnP) is as described in
   `mpmod1\README.txt` from the original author.

## What changed against release 2

1. **30 address fixes** (`port/spec_public_15814271.json`). The author's exact game build was recovered from the
   Ghidra project in the original repo (`port/ghidra_filebytes.py`; the 7 files match the author's published SHA-256).
   Old and new code were then matched function by function (`port/portmap.py`). adv_game, base_main, base_shell and
   basic_steam are code-identical. Only adv_interf (33 functions), adv_opgame (112) and adv_physic (19) changed.
   Fixes: 27 game addresses, 2 hook signatures (input action, next turn: their prologues were recompiled), and the
   next-turn hook length (16 → 17 bytes).
2. **Static emplacements on the host** (`port/mpfix/nest_fix.asm`, new section `.mpfix`, one redirected
   instruction at rva 0x1d182). The joining player's game moves its own units into its deployment area at the start.
   The host follows them by writing position and rotation. A moving vehicle's render model follows by itself, a
   static one (seen: the `mg_pznest` MG nest) does not. So on the host the nest's model and its 2 crewmen stayed at
   the old place, 845 m away, and were pulled back on every update. Now, when a followed vehicle's model is more
   than 5 m from its position, the mod calls the engine's own render-model setter (adv_physic+0xd930) with the
   vehicle's transform.
3. **Ping** (2.2.0, `port/mpfix/ping.asm`, same section). Right of the top status banner ("MULTIPLAYER · … ·
   connected") a box shows `ping N ms`: the round trip to the other player's game, smoothed, refreshed every second,
   hidden when no answer came for 5 s. Two new 12-byte packets (types 0x20 PING / 0x21 PONG, the sender's
   GetTickCount echoed back). It is measured inside the network pump, so it includes up to one frame on each side:
   two games on one PC show about 30 ms.
4. **Vehicles keep their own render handles** (2.2.1, `port/mpfix/keep_handles.asm`, same section, the mod's call
   of its state loader at rva 0x2f092 redirected). Each game loads the other player's unit states into its copies of
   his units. The author already keeps the process-local parts of a unit around that load (model part handles, a
   soldier's animation handles, a vehicle's node points). A vehicle also carries its model node handles and instance
   number at `+0x11a8..+0x11b7`, and those were taken over from the other game. Two games on one PC build their
   scene the same way and hand out the same numbers, so the tests above never showed it. A host on another PC did
   (crash report from a real two-PC game, Steam join, skirmish on Mius_a): its copy of the joiner's MG42 got the
   joiner's handle `0x52800`, which named an empty node group in the host's renderer, and the host crashed at
   `basic_render+0x12983` (called from `adv_physic+0xd930`, the vehicle model setter) when the game placed the
   squads at the end of deployment. Now those 16 bytes are saved before the load and put back after it, for
   vehicles only.
5. **Trenches are not stamped a second time** (2.2.2, one jump in the mod's own code at rva 0x37be0). When a game
   builds a battle it stamps some trenches into the ground by itself, outside any squad's dig (seen in an
   operation battle: the operation's field works). Release 2 records those, sends the list to the other game and
   that game stamps every entry it has not stamped from such a list before. But it has stamped the same trenches
   itself, from the same battle description, and its own stamps are not in that check (the entries also carry
   a variant number, so a list sent again counts as new). In a real two-PC operation battle (Stepanovka 1941,
   2.2.1) the host stamped the joiner's 19 such trenches on top of its own twice, once when the joiner
   reconnected and again at the end of deployment; the host's player saw deep pits and trenches with straight
   walls. The original source says the same about digs made while the battle is built: "sent again it would be
   dug twice there". Now the received list is dropped without stamping; each game keeps the trenches it stamped
   itself. Digs of squads (the owner's dig carried out in the other game) are unchanged.

`port/verify_sites.py` checks every signature compare and hook of the mod against a game folder:

| | sites | bad |
|---|---|---|
| release 2 on the author's build | 42 | 0 |
| release 2 on Steam 15814271 | 42 | 19 |
| this port on Steam 15814271 | 42 | 0 |

## Tests

`qa/run_versus.ps1 -Game <test copy of the game> -Tag <name>`: host plus joiner on one PC, no mouse or keyboard,
saved test battle from the original repo (`_mp_research` must be in the game copy). Result on the Steam `public`
build (2026-11-05):

```
25 passed, 0 failed     RESULT: PASS
  hosting, joining (mp_join), sides Soviets/Germans, AI commander off in both
  shared Start button: deployment -> initial orders -> battle, each step only after both players pressed Start
  145/145 units agree; no unit more than 5 m apart in any of 6 samples
  position corrections: host mean 0.02 m (largest 0.44 m, 0 jumps); joiner mean 0.02 m
  fog of war: host shows 80/80 own and 0/65 of the joiner's units; joiner 65/65 own, 0/80 of the host's
  no crash dump, both games still running after ~6 min
```

Before the port: 17 passed, 7 failed (battle never left deployment; joiner's units 12.7 km off on the host).
Mutation check: the same test with the port but without the emplacement fix fails "no unit more than 5 m apart"
(2 units, every sample).

Fog check: `qa/fog_check.py` replaces the original `view_check.py`, which read unit `+0x6f0` as an "own unit" flag.
That field is the unit's place in its force and is 0 for every unit in a skirmish battle.

All test scripts need `_mp_research` from the original repo in the game copy (its `tools` folder) and Python 3
(`MP_PYTHON` to pick one). Results with 2.2.0 unless noted, Steam `public` 15814271, two games on one PC:

| Script | What it does | Result |
|---|---|---|
| `qa/run_versus.ps1` | saved test battle, host + mp_join | 25 passed, 0 failed; ping shown in both games (30 / 34 ms). With 2.2.1: 25/0; also with `-Image` = the battle of the two-PC crash and `-HostProfile` = the crashed host's options: 25/0 |
| `qa/run_versus.ps1 -Chaos <profile> -ChaosDir <coop-anything>\tools\chaos` | the same, the joiner's traffic through the coop-anything playbook's chaos box (`tools/chaos`) (delay, jitter, loss, bandwidth) | `transatlantic` (90 ms each way, 0.3 % loss): 26/0, ping shown 204 / 198 ms. With 2.1.0: `bad_wifi` 26/0 (twice), `mobile_tether` 26/0, `transatlantic` 26/0 |
| `qa/run_operation.ps1 -Trenches -Extra @{ MP_LOG_TRENCH = "1" }` | the same with every dig and stamp logged and the trenches of both games counted (`qa/trench_dups.py`) | 2.2.2: 40 passed, 0 failed. This battle (first turn) has no trenches stamped outside a dig, so it shows that 2.2.2 breaks nothing, not that the pits are gone |
| `qa/run_operation.ps1` | a NEW operation through the menus (Stepanovka 1941): host and join menus, map shared, the joiner on the German side with fog of war, one order, next turn by both, merge, turn carried out, battle started from the map, both in the battle, units compared, back to the map, turn 2 shared | 40 passed, 0 failed, also with 2.2.1 (battle: 426 units, 0 disagreeing, 0 more than 5 m apart, corrections ≤ 0.10 m); with 2.1.0 also 4 turns in a row |
| `qa/run_steam_join.ps1` | joining as Steam's "Join Game" does (`+gtmf_join=steam:<id>`), lobby, battle download and battle over the Steam path, using the mod's own Steam stand-in (`MP_STEAM_FAKE`: Steam datagrams over UDP on this PC) | 19 passed, 1 failed: one sample had 13 units whose status (not position) differed. The stand-in's socket keeps Windows' default buffer (the real UDP socket asks for 2 MB) and lost about 30 % of the ~750 KB/s burst traffic on this PC; positions stayed within 5 m |
| `qa/status_probe.py` | samples unit status in both games N times: stuck (every sample) or lag (now and then) | used on the `bad_wifi` run: the differences were lag, none stuck |

The `hell` chaos profile (512 kbit/s, 5 % loss) kept units in agreement but the battle ran at ×0.55–0.72 speed:
the mod sends 100–400 KB/s during a battle (skirmish ~105 KB/s, the operation battle ~400 KB/s), more than such a
link carries.

## Not tested

2.2.2 (trench fix): run_versus 25/0 and run_operation 40/0 on one PC. The pits themselves were not reproduced
on one PC: the bots fire no artillery and the test battles stamp no trenches outside a dig. The fix comes from the
logs of the real two-PC game and has to be checked there (both players on 2.2.2, an operation battle).

Real Steam play between two PCs was tried once with 2.2.0 (joining a friend through Steam's "Join Game", skirmish):
lobby, battle download and deployment worked, then the host crashed as described in change 4 above. 2.2.1 has not
yet been played between two PCs. Also not tested: a 2.1.0 or 2.2.0 game against a 2.2.1 game (use the same version),
the `public_beta` branch. The lobby may show a VPN adapter's address
(e.g. Cloudflare WARP 198.18.0.1) instead of the LAN address.

## Rebuilding the patched module yourself

```
python -I port/build_spec.py <release 2 basic_network.codelib> <game dir>   # writes port/spec_public_15814271.json
python -I port/apply_patch.py port/spec_public_15814271.json <release 2 basic_network.codelib> out/ported.codelib
python -I port/mpfix/build_mpfix.py --blob port/mpfix/mpfix.bin out/ported.codelib out/basic_network.codelib
python -I port/verify_sites.py out/basic_network.codelib <game dir>/bin/rel/x64
```

`apply_patch.py` accepts only release 2's exact `basic_network.codelib` (SHA-256 8108bd1e…5723 from `GTMPRelease1.zip`
in the original repo), checks every byte it overwrites and never writes its input. `build_mpfix.py` accepts only
the ported file (6218ff0b…a90b). The output must have the SHA-256 in the table above.

## Credits

All multiplayer code is by VampyrCat ([MiusPlayer](https://github.com/VampyrCat/MiusPlayer), CC0). This repository
only ports it. Made following the coop-anything playbook.
