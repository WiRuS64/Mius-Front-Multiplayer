; mpfix 4: the main menu is recognised again after an operation (Mius-Front Multiplayer 2.5.0). Assembled into the
; .mpfix section at 63780h (where keep_handles.asm of 2.2.1 was; that is in fixes.c now).
;
; The mod's UI decides "this is the main menu" (and only then draws its MULTIPLAYER entry) from the menu controller
; (i_opgame:opgame +100h): screen +1258h == 0 and +1200h != 0 ("4 in the menus, 0 on the map"). Measured on Steam
; 15814271: once an operation has been opened, +1200h stays 0 for good, also back in the main menu and also without
; the mod's multiplayer - only the operation pointer +1d8h tells them apart (set on the map, 0 in the menus). So a
; player who left an operation (Esc, Esc) had no MULTIPLAYER entry and no way back.
;
; Called instead of "cmp dword ptr [rax+1200h], r15d" (7 bytes, r15d = 0) at mod rva 2bcb6h, rax = controller, the
; screen already checked to be 0. Returns ZF = 0 for "main menu" (the caller's jne then takes it), ZF = 1 otherwise:
;   +1200h != 0                    -> main menu (as before)
;   +1200h == 0, operation present -> not the menu (the map); remembers that the map was seen
;   +1200h == 0, no operation      -> main menu; but in the joining player's map program (g_map_mode, mod data
;                                     5b72ah) that has been on the map: after 60 such frames joiner_back_to_lobby
;                                     (mod rva 127dch: back into the host's lobby, ready; it ends this program)
; Only rbx is used (saved); flags are the result.

MAP_MODE        equ 5B72Ah
BACK_TO_LOBBY   equ 127DCh
SEEN_MAP        equ 637F0h          ; byte: this program has shown an operation's map
MENU_FRAMES     equ 637F4h          ; dword: frames on the menu since

.code
ORG 780h
menu_check PROC
    push rbx
    call mc_pc
mc_pc:
    pop rbx                         ; rbx = image base + 63786h
    sub rbx, 63786h
    cmp dword ptr [rax+1200h], 0
    jne is_menu
    cmp qword ptr [rax+1D8h], 0
    jne on_map
    cmp byte ptr [rbx+MAP_MODE], 0
    je is_menu
    cmp byte ptr [rbx+SEEN_MAP], 0
    je is_menu
    inc dword ptr [rbx+MENU_FRAMES]
    cmp dword ptr [rbx+MENU_FRAMES], 60
    jb not_menu
    lea rax, [rbx+BACK_TO_LOBBY]
    pop rbx
    jmp rax                         ; rsp as at a call's entry; does not come back
on_map:
    mov byte ptr [rbx+SEEN_MAP], 1
    mov dword ptr [rbx+MENU_FRAMES], 0
not_menu:
    pop rbx
    cmp eax, eax                    ; ZF = 1
    ret
is_menu:
    pop rbx
    test rsp, rsp                   ; ZF = 0
    ret
menu_check ENDP
END
