; mpfix 3: a vehicle keeps its own render handles when the other game's state is loaded into it (MiusPlayer
; release 2 port, Steam public 15814271). Assembled into the .mpfix section at 63780h.
;
; The mod loads the other player's unit states into this game's copies of his units (state_load_keep_motion:
; "inc g_remote_load; call state_load 2eca4h; dec g_remote_load", the call at mod rva 2f092h). The author already
; keeps the process-local parts of a unit around that load (model part handles, a soldier's animation handles,
; a vehicle's node points). One block was missing: a vehicle (i_techn) saves and loads its two model node handles
; and two more renderer values at +11a8h..+11b7h (seen: +11a8h node handle, +11ach -1, +11b0h instance number,
; +11b4h -1). A handle is a place in the renderer's node tables (group << 10 | node). Two games that built their
; scene the same way hand out the same numbers, so two games on one PC never show it. A friend's game on another
; PC did not: the host's copy of the joiner's MG42 got the joiner's handle 52800h, which named a node group that
; was empty in the host's renderer, and the host crashed in basic_render+12983h the next time the game moved that
; vehicle (placing the squads at the end of deployment: adv_game b7540h -> techn vtable 88h -> adv_physic d930h).
;
; Called instead of "call 2eca4h" at 2f092h: rcx = object, rdx = data, r8 = size; returns state_load's eax.
; Position independent, no relocations (build_mpfix.py checks the call/pop bytes).

STATE_LOAD      equ 2ECA4h
TECHN_NAME      equ 3A6E686365745F69h   ; "i_techn:" - the object's name starts at +8

.code
ORG 780h
keep_handles PROC
    push rbx
    call kh_pc
kh_pc:
    pop rbx                         ; rbx = image base + 63786h
    push rsi
    push rdi                        ; 3 pushes: entry rsp 16k+8 -> 16k
    sub rsp, 30h
    sub rbx, 63786h
    mov rdi, rcx
    xor esi, esi
    mov rax, TECHN_NAME
    cmp qword ptr [rdi+8], rax
    jne load
    mov esi, 1
    movups xmm0, xmmword ptr [rdi+11A8h]
    movups xmmword ptr [rsp+20h], xmm0
load:
    lea rax, [rbx+STATE_LOAD]
    call rax                        ; rcx, rdx, r8 as they came
    test esi, esi
    jz done
    movups xmm0, xmmword ptr [rsp+20h]
    movups xmmword ptr [rdi+11A8h], xmm0
done:
    add rsp, 30h
    pop rdi
    pop rsi
    pop rbx
    ret
keep_handles ENDP
END
