GRAVITEAM TACTICS: MIUS-FRONT - MULTIPLAYER  (mpmod1, test version)
For game version 6.00, build 3598 (the final Steam version). Two players: one hosts, one joins.
Mius-Front Multiplayer 2.6.2: this copy is ported to the current Steam "public" branch (buildid 15814271,
build 3598 compiled 2024-09-24). game_build_3598.sha256 lists THAT build. basic_network.codelib is
release 2 ported, with fixes (MG nests, ping, host crashes, trench pits) and Russian/English texts in the
game's own fonts (Russian when the game runs in Russian; set MP_LANG=en or ru to override).
The module's logs are in the game folder's mp_logs (logs older than 14 days are deleted): when something
goes wrong, zip that folder and send it along.
Operation, host: while your briefing panel is open on the map, the map is not handed to the other player -
close it (F2). Leaving an operation (Esc, Esc) brings the MULTIPLAYER entry back; the other player then goes
back to your lobby by himself.
Operations are BETA (HOST AN OPERATION (BETA) in the menu): they may be unstable. Battles: units are now
fully synchronised between two PCs even when the two games loaded their models in another order (2.6.2).
Both players need this same file: SHA-256 7ca758550f5bccf53009d68364398e6dcaa12079044821feb4077eb4a9d286fe
Both players need the same mpmod1: network version 20, module built 2026-11-06.

QUICK START
  1. Put the whole "mpmod1" folder into the game folder - the one that contains starter_x64.exe.
     (Steam: right-click the game in your library, Manage, Browse local files.)
  2. Close the game and double-click   mpmod1\Enable_Multiplayer.bat
  3. Start the game as usual (through Steam). The main menu has a new entry at the top: MULTIPLAYER.
  4. One player hosts:   MULTIPLAYER -> HOST A SKIRMISH (or A CUSTOM MISSION, or AN OPERATION).
     The other joins:    MULTIPLAYER -> JOIN A GAME, type the host's address, CONNECT, then READY.
     Which address to type, and the port the host needs open: see NETWORK below.
  Back to the original game at any time:   mpmod1\Disable_Multiplayer.bat

WHAT ENABLE AND DISABLE DO
  Enable_Multiplayer.bat copies five new files from mpmod1\files into the game. No file of the game is
  changed or replaced:

      bin\rel\x64\basic_network.codelib   the multiplayer module
      root\programs\opgame.progpack       menu / operational map program, with the multiplayer module added
      root\programs\tacgame.progpack      battle program, with the multiplayer module added
      steam_appid.txt                     lets the game start a second copy of itself (joining a battle)
      mp_join.exe                         optional: join from a command prompt

  Before it copies anything it checks that the game is version 6.00, build 3598, and says so if it is
  not. If the game already has a steam_appid.txt it is left as it is. An earlier version of this
  multiplayer in the game is replaced.
  Until you choose MULTIPLAYER in the main menu the game is the normal single-player game; nothing is
  sent or received.

  Disable_Multiplayer.bat deletes those files again. The game is then exactly the original. Your
  multiplayer operation saves in users\mp_saves stay.

  While multiplayer is enabled, mpmod1 keeps a few notes in mpmod1\state. So: to move to a newer mpmod1,
  run Disable_Multiplayer.bat, replace the folder, run Enable_Multiplayer.bat - and do not delete the
  folder while multiplayer is enabled (if you did: put an mpmod1 folder back and run
  Disable_Multiplayer.bat).

PLAY
  Start the game as usual (Steam has to be running, as for the normal game). The main menu has one more
  entry at the top, MULTIPLAYER. Until you use it the game is the normal single-player game.

      MULTIPLAYER -> HOST A SKIRMISH        opens the lobby as host of a skirmish
                  -> HOST A CUSTOM MISSION  opens the lobby as host of a mission: a prepared one or one
                                            made in the battle editor
                  -> HOST AN OPERATION      opens the lobby as host of an operation
                  -> JOIN A GAME            type the host's address (Ctrl+V pastes) and, if he hosts on
                                            another port than 1943, the port; CONNECT: the host's lobby.
                                            Or pick a Steam friend who is hosting from the list below
                                            the buttons: JOIN - no address and no port needed.

  At the bottom of the MULTIPLAYER panel, for hosting:
      Host port (UDP)      the port your hosted game listens on. Empty means 1943, which the field shows in
                           grey; type another number (1 to 65535) to host on that one. Digits typed on this
                           panel go into the field.
      Open it by UPnP      tick it to have the game ask your router to pass that port on to this PC (off
                           unless you tick it). The host's lobby says whether the router did, and shows your
                           public address when the router gives it. Un-ticking it takes the forward away
                           again if this game made it.
  Both are remembered for the next time, like the address and port you last joined.
  In JOIN A GAME the port field next to the address works the same way (empty = 1943, shown in grey). Tab
  or a click moves between the two fields; typing a colon in the address field moves on to the port; a
  pasted "address:port" fills both.

  The lobby shows both players by their profile names, which force each commands, and whether the joined
  player is ready.
      Host:    SET UP THE BATTLE / CHOOSE THE MISSION / CHOOSE THE OPERATION opens the game's own
               Skirmish, Missions or Operations screen; set everything up and start the battle there as
               usual. A line at the top of the screen keeps showing who has joined. F9 brings the lobby
               back. LEAVE THE LOBBY stops hosting.
      Mission: the Missions screen lists the prepared missions and the ones made in the battle editor.
               The host normally commands the mission's player force and the joined player its enemy
               force; SWAP SIDES turns that round. The mission itself (units, objectives, triggers)
               travels to the joined player with the battle, so only the host needs to have it. A mission
               that uses a map the other player does not have cannot work.
      Joined:  READY. When the host starts the battle, a ready player's game downloads it and enters it.
      Skirmish, either player:  SWAP SIDES. The host sets up the battle on the Skirmish screen; normally
               the host commands its own force and the joined player the enemy force, SWAP SIDES turns that
               round.
      Skirmish, joined player:  CHOOSE MY FORCE - pick your own units instead of the enemy force the
               host's setup makes. It opens the Skirmish screen in your game: set your own side to the side
               you command (the lobby names it), choose your units, press that screen's start button. No
               battle starts: your game comes back into the host's lobby by itself and sends your force,
               and the lobby says when the host has it. When the host starts the battle, your force takes
               the place of the one the setup made for your side, on the same spots of the map.
               Your supports (the screen's SUPPORT rows: a battery or aircraft and the observer squad
               that calls it) come along into the host's battle, even when the host's setup has none.
               Cost limit: your force may cost as much as the host's own force costs on his Skirmish screen
               (the COST row of that screen, added up; the lobby shows the figure, and so does a line at
               the top of your Skirmish screen while you pick). A force that costs more, or is of the wrong
               side, is refused when you press start - you stay on the screen and can change it. The host
               has to have opened his Skirmish screen once, so that his force has a cost. Your picks are
               kept (users\mp_my_force.cfgpack) for the next battles with the same host until you leave
               the lobby.
               Year and season: the battle is fought in the host's year and season, so your Skirmish
               screen opens set to them (and to the two sides); your own Skirmish setup is put back
               afterwards. A force picked for another year or season is refused like one that costs too
               much - set YEAR AND SEASON back to what the screen opened with.
               After the host has started: while the host's battle is still in deployment you can still
               choose your force (the lobby says so). His battle then starts again with your force in it -
               his deployment begins anew - and your game enters it when you are ready. Once his battle is
               past deployment your own force can only go into the next battle; press READY to join this
               one with the force his setup made.
      Operation: the host plays the side of the operation he opens (to play the other side, open the
               operation from that side's entry); modifiers are set on the Operations screen as usual.
               Every time an operation battle starts, the operation's save - written by the game after the
               move and before the battle - is copied to users\mp_saves\<host>_vs_<player>. The operation
               lobby lists these and RESTORE puts one back, so the host can go on from it whatever happened
               to either game. (What RESTORE replaces is kept in users\mp_saves\_replaced.)

  On the operational map (operations). Both players have the map at the same time and each moves his own
  side; nothing has to be handed back and forth.
      - When the host is on the map and the other player is ready in the lobby, the other player's game
        opens the same operation from his side by itself: his own territory and battle groups, fog of war
        over the host's forces. He selects and orders his groups as in a single-player operation.
      - What each player knows of the other's groups works as in the single-player game, for both: the
        groups his own groups' scouting reaches are seen (the game works this out for his side - for the
        other player, his game does it when his map comes up), and a group that has fought his, or that
        his side's intelligence has found out, stays identified for the rest of the operation - shown as
        what it is, not as an unknown contact, whenever it is seen again. The host's game keeps this for
        the host as it always does; what the other player has identified is kept by the host's game in
        users\mp_saves\_known_<operation>.txt and goes into every copy of the map he gets. (The turn is
        carried out by the host's game, the other player's intelligence with it: what it finds out of
        the host's groups is noted there and handed on.)
      - The turn ends when BOTH players have pressed the map's "next turn" control. There is no time
        limit: a player who has pressed waits for the other, and pressing again takes it back. The line at
        the top of the screen says who is waiting for whom.
      - Then the other player's orders are fetched and put into the host's operation, the host's map
        reloads twice (about 20 seconds in all) and the turn is carried out: both players' ordered groups
        move, and the computer plans nothing for the other player's side (it still moves computer-led
        allies of the host). Nothing is drawn over the map meanwhile, so the moves can be watched; the
        host's map takes no clicks until the turn has been carried out.
      - After the battles of a turn the host presses next turn once more (as in the single-player game)
        to move on; the next turn's map then goes to the other player.
      - The other player stays on the operational map throughout. When the turn has been carried out his
        map reloads with the result (one loading screen) and he gives the next turn's orders. If the turn
        leads to a battle, his game goes from the map straight into the battle as soon as the host starts
        it; after the battle it returns to the host by itself and gets the map of what follows.
      - If the other player's game goes away (closed, connection lost), the host is not kept waiting: his
        next-turn control ends the turn the usual way, without the other player.
  The other player's game keeps the host's operation in its own profile as that operation's save (for
  the other side's version of the operation); a save of his own with that name is kept in
  users\mp_saves\_replaced.
  A battle has to be fought to its end for the operation to move on to the next turn.

  In the battle. Each player commands one force; the computer commander only leads the computer-led
  formations an operation gives the host's side. The line at the top of the screen always has the same
  shape:
      MULTIPLAYER  -  <you> (<your side>)  vs  <other player> (<their side>)  -  <what is going on>
  Deployment ends when BOTH players have pressed the game's Start button (the arrow in the top toolbar,
  or Enter), and the battle starts when both have pressed it again after the initial orders.
  Pause and speed belong to both players. The pause and speed keys (and the buttons of the top toolbar)
  are each player's WORD, not a switch:
      - the battle pauses when BOTH players have paused, and goes on as soon as either un-pauses;
      - it runs faster than normal only as fast as BOTH have asked for (one wants x4, the other x2: it runs
        at x2), and slower than normal only as far as both have asked for. One player's wish alone changes
        nothing.
    The top line says what is asked and by whom ("... asks for a pause - pause as well to agree"), and the
    game's own time display shows your wish next to the speed the battle really runs at.
  The ESC menu does not pause the battle any more, for either player: the battle goes on behind it, and
  it is not left paused when the menu closes.
  Nothing else changes the speed either. The game's automatic speed control (which holds the speed back
  at low frame rates and lets it creep up slowly) is switched off while another player is in the battle:
  the battle runs at exactly the speed the two players have agreed on, from its first second and at once
  after a pause. A PC that cannot keep up is waited for - see below - not slowed down for.
  (In the single-player game all of this is as it always was.)
  Both games simulate at the same fixed rate (50 steps per second), so a faster PC gives no advantage.
  The two battle clocks are kept together by catching up, never by dropping or redoing anything: a game
  that has fallen behind simulates faster (up to four times) until it is level, and the host slows down
  and, if need be, stops for a joined game that cannot keep up ("waiting for ...'s game to catch up" in
  the top line). Both games then run at the pace of the slower PC and neither misses anything.
  Fog of war is each game's own: a player sees the other player's units only while his own units have
  them spotted.
  You can select only your own units. In a battle against the other player a click or a selection box
  takes in none of his units, so their panels (state, orders, ammunition) stay hidden from you. Allied
  units in a battle on the same side are not affected.
  Ending the battle. A battle ends for both players in the same moment, and both get the game's end
  screen with the same table of results - each from his own side (one player's TOTAL VICTORY is the
  other's TOTAL DEFEAT).
      - Withdraw (the running man in the ESC menu's column of buttons, then Yes): your force leaves the
        battle. The other player is told at once ("... is withdrawing - the battle ends in 0:30" in the
        top line, with the game's own countdown clock); when the countdown is over the battle ends for
        both, and the ground goes to the player who stayed.
      - CEASEFIRE (a button under the ESC menu's column of buttons, only in a battle with another
        player): proposes to end the battle now. The other player sees the proposal in the top line and
        the button reads ACCEPT CEASEFIRE for him. Once both have chosen it the battle ends five seconds
        later. Until then a second press takes your word back.
      - The battle's own end (time up, a force broken, a mission's trigger) comes from the host's game.
    The end screen stays as long as you want to read it, also when the other player has already left. In
    an operation the host then goes back to the operational map; the other player's game goes back to
    the host's lobby by itself and follows him onto the map.
  If the host closes its game or the connection is lost during a battle, the joined game closes the
  battle after a few seconds and returns to the menu.

NETWORK
  There are two ways for the joining player to reach the host.

  By address. The host needs his hosting port (UDP 1943 unless he chose another on the MULTIPLAYER panel)
  reachable from the other player: forward that UDP port to the host PC on the router by hand, or tick
  "Open it by UPnP" on the MULTIPLAYER panel and the game asks the router to do it (the lobby shows the
  outcome). If Windows Firewall asks whether starter_x64.exe may communicate on the network when you
  host for the first time, allow it. Only the host needs the port; the joining player needs nothing set
  up, he types the host's address and port.
      Over the internet:    the host's public address
      On the same network:  the address shown in the host's lobby
      On the same PC:       127.0.0.1
  From a command prompt:    mp_join.exe <host address>[:port] [germans | soviets]
                            (a game hosted from a command line: MP_PORT=<port>, MP_UPNP=1)

  Through Steam. A game that hosts is shown to its player's Steam friends: their JOIN A GAME screen lists
  him under STEAM FRIENDS HOSTING A GAME, and JOIN connects - through Steam's own peer-to-peer network,
  by way of Steam's relays if the two PCs cannot reach each other directly. No address, no port, no
  router setting. Both players need Steam running (as the game does anyway), have to be Steam friends,
  and need the same version of these files; the host needs nothing switched on for it.
  State of this: the whole path - list, lobby, battle download, the battle and the change from the menu
  into the battle - passes its test with a stand-in for Steam on one PC, and against the real Steam the
  game's Steam library answers, Steam's callbacks arrive and the note for friends is taken. Two players
  actually connected through Steam have NOT been tried: that needs two Steam accounts on two PCs.
  Steam's own "Join Game" works as well: right-click a friend who hosts in Steam's friends list and pick
  Join Game. If your game is running, it goes into his lobby from the main menu; if it is not, Steam starts
  it and it goes into his lobby by itself. (Steam starts the game with the host's text after its name -
  "root\programs\opgame.progpack, +gtmf_join=steam:<id>" - which the game's menu program takes as usual.)
  MP_STEAM=0 switches Steam joining off.
  Expect roughly 300-400 KB/s in each direction during a battle of about 150 units. The state stream is
  limited to 600 KB/s per game (MP_STATE_KBPS changes that).

HOW IT WORKS, AND ITS LIMITS
  Each PC simulates the whole battle, and for everything that matters exactly one of the two games
  decides and the other takes over the result:

      a unit (place, damage, crew, ammunition, where its gun points)   the game of the player who
                                                                       commands it; the host's game for
                                                                       the computer-led formations an
                                                                       operation has on the host's side
      a shot (when, from where, in which direction)                    the game that owns the firing unit
      off-map artillery and flares                                     the game of the player whose side
                                                                       fires them (the host's for every
                                                                       other side)
      a crew blowing up its own vehicle                                the game that owns the vehicle
      a trench                                                         the game that owns the squad
      a hit on a unit                                                  the game that owns the unit struck
      a soldier's animation and the way he is turned                   the game that owns the soldier
      a crater, and the ground in general                              the host's game
      a side leaving the battle (Withdraw)                             the game of the player who commands it
      the moment the battle ends, and its result                       the host's game
      the battle time                                                  the host's game
      pause and speed                                                  both players together

  Units. The owner's game sends a unit's position 15 times a second and its complete saved state whenever
  it changes; the other game loads them. So what a hit did to a unit is what its owner's game worked out:
  a vehicle is destroyed, damaged or untouched in both games alike, in skirmishes, missions and operation
  battles.
  Hits. Whatever strikes a unit is worked out once, by the game that owns the unit, and sent; the other
  game carries out the same hit with the same numbers and drops what its own flying shell would have
  done to that unit. MP_SYNC_HITS=0 switches this off.
  Soldiers. What a soldier's animation is asked to do, and the way he is turned, are his owner's game's
  and are sent whenever they change. MP_SYNC_ANIM=0 / MP_SYNC_FACING=0 switch this off.
  The other player's units are shown by interpolation: about an eighth of a second in the past, moving
  smoothly from one received position to the next. Each position carries the battle time at which its
  owner's game took it, and the receiving game follows that clock, so the movement is even whatever
  either PC's frame rate (placing positions by the moment they happened to arrive made units move in
  fits and starts, the more so the fewer frames the other game drew). A unit whose owner has stopped
  sending (it stands still there) stays where the owner last had it. Nothing is predicted: every unit is
  simulated without delay by its owner's game.
  Vehicles. The other player's vehicles are not driven in your game, only placed, so their running gear is
  turned from their movement: tracks run and wheels roll at the speed the ground passes under them (they
  can run a little slower than in the owner's game). Front wheels steer as the owner's driver steers - his
  steering travels with the position.
  Shots. Every shell, bullet, smoke round and grenade the owner's game launches is sent to the other game,
  which launches it with exactly the same start, direction and speed; what the other game's own
  simulation would have fired for that unit is dropped. Launches are sent reliably and in order (repeated
  until acknowledged). MP_SYNC_SHOTS=0 switches this off, MP_LOG_SHOTS=1 writes every launch to
  out\mp_shots_<pid>.txt.
  Trenches. A trench is a ready-made piece of ground stamped onto one 32 m cell of the map. When a squad
  is dug in, the owner's game sends which cell, which way round, which kind - and whether it stamped
  anything at all - and the other game does exactly that; what it would have dug for that squad by itself
  is dropped. This covers the digging at the end of deployment and a squad its player puts somewhere else
  during deployment. MP_SYNC_TRENCH=0 switches this off, MP_LOG_TRENCH=1 logs every dig.
  Craters. Every crater the host's game makes is sent with all that shaped it (place, kind, size, the
  random numbers behind its form) and made the same in the other game, whose own craters are dropped.
  MP_SYNC_CRATERS=0 switches this off.
  Operations: what earlier battles left behind. A battle of an operation is built with the wrecks, ruins,
  craters and trenches of the operation's earlier battles on that ground, from files in the host's
  profile. The host's game hands those files (a few hundred KB) to a game that joins, together with the
  name of the operation and its turn; the joined game keeps them in a profile folder of their own
  (users\profiles\mp_guest, next to copies of the player's own settings - his own profile and saves are
  not touched) and builds its battle as a battle of that operation too. Both games then build the same
  scene. When such a battle is over, the joined game goes back to the menu and from there to the host's
  lobby instead of opening the host's operation. MP_JOIN_PLAIN=1 on the joining PC switches this off.
  The trenches of units that have held their ground since an earlier battle are put into the ground by
  each game itself (once when the battle is built and once more, with their places for soldiers, when
  deployment ends). Each game still tells the other of them, for a game that has not got them; a game
  that has made one on the other's word does not make it a second time.
  A saved state is only loaded into a unit whose internal render handles are the same in both games (they
  are when both games built the same scene). Where they differ, that unit is followed by position only;
  the game's log (out\basic_network_tacgame_*.log) counts these as "not loaded". Supply trucks are always
  followed by position only.
  The end of a battle. A side leaving the battle and a ceasefire proposed or taken back travel as events
  between the two games' own end-of-battle logic, so each game shows the engine's own warnings and
  countdown. The battle is over when the host's game says so; a joined game whose own countdown has run
  out waits for that word. What is left of a force is counted by the game of the player who commands it
  (each game sends its own count a few times a second), and the host's last word carries the numbers its
  result was made from - the joined game makes its end screen from exactly those. MP_SYNC_END=0 switches
  all of this off (each game ends its own battle, as before).

  Measured with both games on one PC (the test scripts are not part of this folder):
      - Saur-Mogila operation battle, 400 units, 4 minutes at three times real time: no unit differing
        between the games in any of 8 comparisons, none more than 5 m apart, about 1,200 launches passed
        to the other game, all 2,502 dug places (trenches and craters) identical;
      - the same battle with six squads dug in somewhere else during deployment (through the game's own
        dig call, by a test command - not by dragging them on the deployment screen): trenches identical;
      - a Peleshi operation battle with a history of earlier battles, 1,166 units: 2,357 of the host's
        2,358 dug places present in the joined game (it gets 2,367 craters and 18 trenches from the host);
      - skirmish, 150 s at three times real time: 1,517 launches all identical, no unit differing, trenches
        and craters identical; gun directions a median 0.0 degrees apart (a few degrees for a moment
        while a vehicle turns);
      - a Peleshi operation battle joined the new way (1,166 units): every one of about 17,000 unit states
        loaded in each game, none refused; no unit differing once the battle was under way; all 2,360
        dug places (the craters and trenches of earlier battles and of this one) and all 100,436 cover
        places identical, at the start of the battle and after fighting. (Until the last fix the host's
        game held 120 to 191 trench places twice: it had put the 18 old trenches into the ground a second
        time.) Saur-Mogila: identical in deployment, after squads were dug in elsewhere, and in the battle;
      - Withdraw by the host and by the joined player, and a ceasefire (proposed, taken back, proposed,
        accepted with a click on the button), in a skirmish: the other game heard of each within a
        moment; both battles ended 0.2 s apart; the two end screens showed the same table from the two
        sides (TOTAL DEFEAT / TOTAL VICTORY, and DRAW / DRAW after the ceasefire). The same for a ceasefire
        in a Peleshi operation battle, after which the joined game went back to the host's lobby and the
        host to its operational map;
      - pause and speed in a skirmish, by how fast battle time passed in both games: ESC menu of either
        player open - the battle went on; one player paused - went on; both - stood still; one let go -
        went on at once at x1.00; x4 asked by one - x1.00; x4 and x2 - x2.00; x4 and x4 - x4.00; half speed
        asked by both - x0.50; x1.00 from the first seconds of the battle. (Before the automatic speed
        control was switched off the same test gave x0.75 for the first half minute of a battle and after
        every pause, and x3.3 for x4.) A Peleshi operation battle of 1,166 units, two games on one PC at
        about 25 frames a second each: x1.00, and x1.98 with both players asking for x2;
      - the other player's units, skirmish: a soldier walking at a steady pace was drawn moving at 1.4 to
        4.4 m/s from one frame to the next (placed by arrival time, in the same run: 0 to 17 m/s); every
        simulation step exactly 20 ms in both games; the other player's tracks ran and his wheels rolled,
        and a halftrack's front wheels stayed within about 1 degree of the owner's steering (before: thrown
        to full lock by the receiving game and snapping back);
      - CHOOSE MY FORCE with an off-map battery in the joined player's force and none in the host's setup:
        the battery came into the host's battle and the joined player's observer called it - 4 of 4 rounds
        landed in both games.

  Not done yet, or not as good as it should be:
    - operational map: the other side's view needs the game to have that operation from the other side
      (e.g. ..._rus and ..._ger); for an operation without one the other player sees the host's version,
      with all of the host's groups visible. All sixteen operations of the game have their other-side
      version with the same formations. Identification after a battle was checked with the battle
      groups the game marks as having fought, not by playing a battle to its end and on into the next
      turn; identification by intelligence with a save that gives the other player's groups that
      ability, not with one a player earned in an operation;
      Played with both games on one PC: Odintsov (a turn and its battle) and Saur-Mogila (a turn, its
      battle to the end, the turn after it with both players' orders, into the next battle) - the battle's
      one-hour limit was shortened for that test; the other operations were checked from their files and
      saves, not played;
    - a battle with both players on the same side (the joined player asked for the host's side): the
      ceasefire and the shared pause are written for it but were only tried in versus battles;
    - skirmish, CHOOSE MY FORCE: a force for a mission or an operation cannot be chosen (their forces
      are the mission's and the operation's);
    - what a shot does when it lands, apart from its crater and the hit itself, is still worked out by
      each game: the smoke cloud of a smoke round and destroyed buildings can differ a little. The lower
      part of the end screen (who destroyed what) is each game's own count. Off-map artillery (also the
      joined player's), flares and a crew blowing up its vehicle are sent and happen once, in both games
      alike; an illumination mission was not tried at night (the game fires it only then). Mines were
      seen working in both games of a two-PC game, not measured by a test;
    - a few soldiers at a time are still shown in another animation or turned differently on the other PC
      (3 to 13 of 1,073 in a large battle), and the crew of a few vehicles can be drawn in a different
      place;
    - during deployment soldiers riding on a vehicle in one game can be shown walking beside it in the
      other; this sorts itself out within seconds of the battle's start;
    - the turret and gun are not sent as a stream of their own; they follow the unit's saved state;
    - the places the game marks for soldiers to take cover in (not the ground) are scattered at random by
      each game when it builds the battle; each game uses its own for its own player's soldiers;
    - joining through Steam (the list inside the game and Steam's own Join Game) has not been tried
      between two real Steam accounts (see NETWORK);
    - two players only. Two PCs over a real connection have been played (and work), but the
      measurements above are all from two games on one PC.

  Running two copies on one PC (for testing): they share the graphics card. The copy that is not the
  active window is held to 30 frames per second and the active one gives way until the other reaches
  that. Environment variables, set before starting the game: MP_BG_FPS (background limit, 0 = none),
  MP_FG_FPS (fixed limit for the active window), MP_SIM_HZ (simulation steps per second, 0 = stock).
