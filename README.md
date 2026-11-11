# Mius-Front Multiplayer 2.6.2

Two-player multiplayer (versus) for **Graviteam Tactics: Mius-Front** on the current Steam build, in Russian or
English as the game is, drawn with the game's own fonts.

Mius-Front Multiplayer is [VampyrCat/MiusPlayer](https://github.com/VampyrCat/MiusPlayer) "release 2" (mpmod1,
network version 20, CC0) ported to the game Steam ships now, with fixes. Release 2 targets another compile of
build 3598, so on the current game many of its hooks were off and battles never left deployment.

| | |
|---|---|
| Version | **2.6.2** (operations: beta) |
| Game | Graviteam Tactics: Mius-Front, Steam app 312980, branch `public`, buildid 15814271 (GRAVITECH3 6.00, assembly 3598, compiled 2024-09-24) |
| Not for | the Steam `public_beta` branch (untested), other stores (untested) |
| `basic_network.codelib` SHA-256 | `7ca758550f5bccf53009d68364398e6dcaa12079044821feb4077eb4a9d286fe` |
| License | CC0 1.0, like the original |

**Русский:** Mius-Front Multiplayer — сетевая игра вдвоём для Graviteam Tactics: Mius-Front (Steam, ветка
`public`, buildid 15814271). Основа — мод MiusPlayer (релиз 2), перенесённый на текущую версию игры. Установка:
папку `mpmod1` положить в папку игры и запустить `mpmod1\Enable_Multiplayer.bat`. У обоих игроков должен быть один и
тот же файл (SHA-256 выше). С 2.3.0 мод говорит на языке игры: в русской игре все его надписи по-русски, в английской
по-английски, и рисуются они шрифтами самой игры. С 2.4.0 логи мода лежат в папке `mp_logs` в папке игры: её
можно запаковать и отправить, если что-то пошло не так. С 2.6.2 юниты в бою синхронизируются полностью, даже если
у двух игроков модели загрузились в разном порядке. **Операции пока в бета-версии** (в меню: «СОЗДАТЬ ОПЕРАЦИЮ (БЕТА)»):
они могут работать нестабильно.

## Install

1. Download `Mius-Front-Multiplayer-2.6.2.zip` from Releases and unpack it. Copy the `mpmod1` folder into the game
   folder (the one with `starter_x64.exe`; Steam: right-click the game, Manage, Browse local files).
2. Close the game and run `mpmod1\Enable_Multiplayer.bat`. It checks the game files against
   `mpmod1\game_build_3598.sha256` (the hashes of Steam buildid 15814271) and copies five files into the game. No
   game file is changed. `mpmod1\Disable_Multiplayer.bat` removes them again.
3. Both players use the same version. Hosting, joining, Steam friends and UPnP are described in `mpmod1\README.txt`
   from the original author.

## What changed against release 2

| | Change | Where |
|---|---|---|
| 1 | Ported to Steam 15814271: 27 game addresses, 2 hook signatures, 1 hook length | `port/spec_public_15814271.json` |
| 2 | Static emplacements (MG nests) on the host follow the joiner's moves | `port/mpfix/nest_fix.asm` |
| 3 | Ping to the other player, right of the top line (2.2.0) | `port/mpfix/ping.asm` |
| 4 | No crash between two PCs: vehicles keep their own render handles, the model (2.2.1) and the turrets and guns (2.4.0) | `port/mpfix/fixes.c` |
| 5 | Operation battles: the other game's trenches are not stamped a second time (no more pits, 2.2.2) | one jump at rva 0x37be0 |
| 6 | Russian or English as the game is, in the game's own fonts (2.3.0) | `port/mpfix/text.c`, `lang_ru.txt` |
| 7 | The logs in a folder of their own, `mp_logs` in the game folder; older than 14 days deleted (2.4.0) | `port/mpfix/fixes.c` |
| 8 | After leaving an operation the main menu has MULTIPLAYER again; a joining player who leaves the map goes back to the host's lobby (2.5.0) | `port/mpfix/menu_fix.asm` |
| 9 | The operation map no longer hangs at next turn: when the other player's moves do not arrive the host gives up after 45 s (up to 180 s while they are being received), says so and next turn can be pressed again; the joining player is told to go back to the map (2.6.0) | `port/mpfix/fixes.c`, `qa/run_turnhang.ps1` |
| 10 | The lobby and UPnP use the PC's network address when the default route goes through a tunnel such as Cloudflare WARP; the host is told why the map is not handed over while battles of the turn are pending (2.6.0) | `port/mpfix/fixes.c` |
| 11 | Hits reach the other game: a game that has not received the other game's table of numbers 6 s after connecting asks for it again, every 6 s. In the owners' first battle between two PCs the joiner never got the host's table, so none of the host's 44434 hits on its own units was carried out on the joiner's side (2.6.2) | `port/mpfix/fixes.c` |
| 12 | Full unit state sync between two PCs: when the two games number the renderer's model groups differently (models loaded in another order), the other game's unit states were all refused (about 5400 every 5 s in that battle) and units were only moved by position. They are now loaded, with the other game's group numbers changed to this game's (2.6.2) | `port/mpfix/fixes.c`, `qa/handle_scan.py`, `qa/state_dump_scan.py` |
| 13 | Operations are marked as beta in the multiplayer menu: HOST AN OPERATION (BETA) / СОЗДАТЬ ОПЕРАЦИЮ (БЕТА) (2.6.2) | `port/mpfix/text.c`, `lang_ru.txt` |

Details of each are in the commit history and the release notes.

Change 4, turrets (2.4.0): a vehicle's weapon mounts hold two renderer node handles each, and they travel in
the unit state like the model handle of 2.2.1. `qa/turret_probe.py` shows it: a handle changed in the host's copy
of a joiner vehicle is back at the joiner's value 2 s later (with 2.4.0 it stays). A friend's host crashed in
`basic_render` on such a handle (the renderer numbers its node groups differently on another PC).

Change 12 (2.6.2): a renderer handle is `group << 10 | node`; every model has a group, and the group numbers depend
on the order the game loaded its models. The mod's guard (mod rva 0x2e7e0) loads a state only if every part handle is
the same. `mp_handles_ok` replaces that call. If the counts and node numbers are the same and the groups match one to one (8 at most), every value
in the state that names one of the other game's groups gets this game's group, and the state is loaded. Anything else is
refused as before. Where the handles are was found in live memory (`qa/handle_scan.py`) and in 600 dumped states
(`MP_TEST_DUMP_STATES`, `qa/state_dump_scan.py`): soldiers have them in the part list and at 13 fixed places, and no
chance match of other data was found. Test switches: `MP_TEST_SHIFT_GROUPS=<n>` moves this game's groups in every state
received, as another PC would number them; `MP_TEST_NO_GROUP_MAP=1` and `MP_TEST_GROUPS_UNTRANSLATED=1` are the
mutations.

Change 6:

- **Language.** The mod's texts are English in its code. `text.c` looks each one up in `port/mpfix/lang_ru.txt`
  (about 190 entries: menus, lobby, the top line in battle and on the map, the ceasefire menu, the ping) when the
  game runs in Russian. The game writes its language (`loc_rus` / `loc_eng`) to `root\engine.txt` at every start;
  `MP_LANG=ru` or `en` overrides it. Names in the texts use the game's own words (СХВАТКА, ОПЕРАЦИИ, «Следующий
  ход», «Начать бой!», СССР, Германия).
- **Font.** The game draws its menus with its own bitmap fonts. `text.c` reads them from the player's game
  (`data\common\loc_*\packed_data\data_loc.flatdata`: DXT5 / 32-bit textures and 256-character font maps), nothing
  of the game is shipped. Titles, buttons and the main menu entry use the handwriting of the main menu, the rest the
  game's standard font. If the fonts cannot be read the text falls back to a Windows font.
- **How.** The mod draws every text through one function; its three Windows calls there (CreateFontA,
  GetTextExtentPoint32A, TextOutA) now go to `text.c`, compiled with MSVC and laid into the mod's `.mpfix` section by
  `port/mpfix/link_coff.py`. A translation much longer than the English text is drawn a little smaller so it
  stays in its box.

`port/verify_sites.py` checks every signature compare and hook of the mod against a game folder: release 2 on
the author's build 42/0 bad, release 2 on Steam 15814271 42/19, this port 42/0.

## Tests

All on Steam `public` 15814271, two games on one PC, no mouse or keyboard except where noted. The scripts need
`_mp_research` from the original repo in the game copy (its `tools` folder) and Python 3 (`MP_PYTHON`).

| Script | What it does | Result with 2.6.2 |
|---|---|---|
| `qa/run_text.ps1 [-Lang ru\|en]` | starts one game; frames of the main menu, the multiplayer panel (clicked), the join screen, the lobby; checks the language and that the game's fonts were read | 2.4.0: Russian game 6/0 (2.3.0: also `-Lang en` 6/0) |
| `qa/run_versus.ps1` | saved test battle, host + joiner: shared Start button, unit agreement, fog of war, crashes | 25/0 (2.6.2) |
| `qa/run_fight.ps1 -ShiftGroups 8192` | a real fight where each game's states name the other's model groups moved by 8192, as on two PCs; states loaded and refused, the other numbering left in units (`qa/handle_scan.py`), hits carried out in each direction | 2.6.2: 19/0, 91620 states loaded, 0 refused, 0 values of the other numbering left, 0 disagreeing units, hits 108/108. Mutations: without the group matching 0 loaded, 90804 refused, 12 units disagreeing; loaded without renumbering: crash in `basic_render` |
| `qa/run_suite.ps1 [-Only shift,fight,versus]` | the scripts above in a row, one pair of games at a time | |
| `qa/run_operation.ps1` | a new operation through the menus (Stepanovka 1941): map shared, next turn by both, battle from the map, units compared, turn 2 | 40/0 |
| `qa/run_turnhang.ps1` | the joining player leaves the map, then both press next turn | 2.5.0: the host still waiting after 70 s (fail); 2.6.0: 5/0, gives up after 45 s |
| `qa/run_othermap.ps1` | next turn by both players on another operation (Stepanovka-Marinovka, July 1943), no orders, no battle | 8/0 |
| `qa/run_fight.ps1 -Fight 360` | the joining force is brought to 200 m in deployment; a real fight with hits, units compared; hits carried out by the other game (each direction with 10 or more) and both games have the other's table | 2.6.2: 16/0, 0 units disagreeing, hits 38/38. 2.6.1 without the ask-again (table records dropped for 8 s): 81 hits sent, 0 carried out |
| `qa/turret_probe.py <tools> <host pid> <joiner pid>` | while a versus battle runs: turret handles in both games; one is changed in the host's copy of a joiner vehicle | 2.3.0: put back by the next state load; 2.4.0: kept |
| `qa/drive.ps1` + `qa/ctrl_dump.py` | keys, clicks and frames in one running game; the menu controller's fields | leaving an operation (Esc, Esc): 2.4.0 no MULTIPLAYER entry; 2.5.0 the host has it, the joining player is back in the lobby in about 1 s |
| `qa/run_operation.ps1 -Trenches` | the same, trenches of both games counted (`qa/trench_dups.py`) | 2.2.2: 40/0 |
| `qa/run_versus.ps1 -Chaos <profile>` | the joiner through the coop-anything chaos box (delay, loss) | 2.2.0, `transatlantic`: 26/0, ping 204 / 198 ms |
| `qa/run_steam_join.ps1` | joining as Steam's "Join Game" does, through the mod's Steam stand-in | 2.2.0: 19/1 (the stand-in loses packets) |

Before the port: 17 passed, 7 failed (battle never left deployment). Mutation check: without the emplacement fix
the 5 m check fails (2 units, every sample).

## Not tested

- Real Steam play between two PCs: 2.2.0 (host crash, fixed in 2.2.1) and 2.3.0 (an operation battle played to
  the end; a host crash in an earlier battle, fixed in 2.4.0). Known from that game and not fixed yet: low frame rate at x6 speed, vehicles firing at soldiers already dead, the host's squad names and battle timer
  missing, the host's losses shown as 0 at the end (not reproduced in three automated fights with 2.6.0).
- While the host's briefing panel is open on the operational map the map is not handed to the joining player (the
  mod reads the menu controller's +0x1260 == 2 as "battles pending"; the briefing sets it too). Close it with F2.
- Russian texts that only appear in rare situations (a force rejected on the Skirmish screen, UPnP failures,
  withdrawal countdowns) are in the table but were not seen on screen.
- The `public_beta` branch; different mod versions against each other (use the same version).
- 2.6.2 between two real PCs: the renumbering was tested on one PC by moving the groups (`-ShiftGroups`), not yet
  with two games that loaded their models in another order. The operation scripts were not rerun for 2.6.2:
  operations are beta.

## Rebuilding the patched module yourself

```
python -I port/build_spec.py <release 2 basic_network.codelib> <game dir>   # writes port/spec_public_15814271.json
python -I port/apply_patch.py port/spec_public_15814271.json <release 2 basic_network.codelib> out/ported.codelib
python -I port/mpfix/build_mpfix.py --blob port/mpfix/mpfix.bin out/ported.codelib out/basic_network.codelib
python -I port/verify_sites.py out/basic_network.codelib <game dir>/bin/rel/x64
```

`apply_patch.py` accepts only release 2's exact `basic_network.codelib` (SHA-256 8108bd1e…5723 from
`GTMPRelease1.zip` in the original repo) and never writes its input; `build_mpfix.py` accepts only the ported file
(6218ff0b…a90b). Without `--blob` it assembles the `.asm` files with ml64 and compiles `text.c` with cl
(`MSVC_SETUP` = a script that sets up the x64 compiler, such as `vcvars64.bat`); after editing `lang_ru.txt` that is
the way to rebuild. The output must have the SHA-256 in the table above.

## Credits

All multiplayer code is by VampyrCat ([MiusPlayer](https://github.com/VampyrCat/MiusPlayer), CC0). This repository
ports it, fixes it and translates it. Made following the coop-anything playbook.
