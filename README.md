# MiusPlayer-Port 2.1.0

Two-player multiplayer (versus) for **Graviteam Tactics: Mius-Front**, ported to the current Steam build.

This is [VampyrCat/MiusPlayer](https://github.com/VampyrCat/MiusPlayer) "release 2" (mpmod1, network version 20,
CC0). The original targets a different compile of build 3598 than the one Steam ships now, so on the current game
many of its hooks were switched off: the shared Start button, hit sync, the crash guard. Battles never left
deployment. This port fixes that and one sync bug.

| | |
|---|---|
| Version | **2.1.0** (= MiusPlayer release 2 + port to Steam `public` + static-emplacement fix) |
| Game | Graviteam Tactics: Mius-Front, Steam app 312980, branch `public`, buildid 15814271 (GRAVITECH3 6.00, assembly 3598, compiled 2024-09-24) |
| Not for | the Steam `public_beta` branch (untested), other stores (untested) |
| `basic_network.codelib` SHA-256 | `cd9ae1b8ab09bee363fb3ba26af25373b0ce2c53009f2620824e23b42c493b7c` |
| License | CC0 1.0, like the original |

**Русский:** порт мультиплеер-мода MiusPlayer (релиз 2) на текущую Steam-версию игры (ветка `public`, buildid
15814271). Установка как у оригинала: папку `mpmod1` положить в папку игры и запустить
`mpmod1\Enable_Multiplayer.bat`. У обоих игроков должен быть один и тот же файл (SHA-256 выше).

## Install

1. Download `MiusPlayer-Port-2.1.0.zip` from Releases and unpack it. Copy the `mpmod1` folder into the game folder
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

## Not tested

Operations (operation map, turns), the host/join menus, joining through Steam friends, real play over the internet,
the `public_beta` branch. The lobby may show a VPN adapter's address (e.g. Cloudflare WARP 198.18.0.1) instead of
the LAN address.

## Rebuilding the patched module yourself

```
python -I port/build_spec.py                    # needs a game copy in ./game_test (see the script header)
python -I port/apply_patch.py port/spec_public_15814271.json <release 2 basic_network.codelib> out/ported.codelib
python -I port/mpfix/build_mpfix.py --blob port/mpfix/nest_fix.bin out/ported.codelib out/basic_network.codelib
python -I port/verify_sites.py out/basic_network.codelib <game dir>/bin/rel/x64
```

`apply_patch.py` accepts only release 2's exact `basic_network.codelib` (SHA-256 8108bd1e…5723 from `GTMPRelease1.zip`
in the original repo), checks every byte it overwrites and never writes its input. `build_mpfix.py` accepts only
the ported file (6218ff0b…a90b). The output must have the SHA-256 in the table above.

## Credits

All multiplayer code is by VampyrCat ([MiusPlayer](https://github.com/VampyrCat/MiusPlayer), CC0). This repository
only ports it. Made following the coop-anything playbook.
