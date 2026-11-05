; mpfix 2: ping to the other player, shown right of the top status banner (MiusPlayer release 2 port, Steam
; public 15814271). Assembled together with nest_fix.asm into the .mpfix section (rva 63000h):
;
;   63000h  nest_fix   (nest_fix.asm, unchanged)
;   63200h  ping_rx    called from on_packet (mod rva 169e1h, 11 bytes -> call + 6 nop)
;   63400h  ping_draw  called from ui_render (mod rva 2ce0dh, "call 24820h" -> "call ping_draw"), ends with jmp 24820h
;   63700h  data       (the section is read/write/execute)
;
; Protocol: two new packet types after the mod's 1..11 (protocol.h Head: u32 magic 'GTMP', u8 type, u8 flags,
; u16 count), 12 bytes each: PING = Head{type 20h} + u32 sender's GetTickCount; PONG = Head{type 21h} + the same
; u32 echoed. In release 2's code the switch sends unknown types (above 15) to its return, so 2.1.0 should ignore
; both (read from the code, not tested; both players should use the same version anyway).
;
; On every packet from the peer (on_packet, after the peer check): at most once per second send a PING; answer a
; PING with a PONG; on a PONG: rtt = now - echoed tick, smoothed (3*old + new)/4. "now" is the network pump's
; GetTickCount, so the value includes up to one frame on each side.
;
; Registers at 169e1h: rsi = packet, ebx = size, r13d = now (GetTickCount). The stub redoes the replaced
; "movzx ecx, byte [rsi+4]" and "mov [g_last_rx 5b908h], r13d" and returns with ecx = type.
;
; Position independent, no relocations: each stub finds the image base with call/pop (build_mpfix.py checks the
; bytes at the offsets used below).

DATA_LASTPING   equ 63700h      ; u32 tick of the last PING sent
DATA_RTT        equ 63704h      ; u32 smoothed round trip, ms
DATA_LASTPONG   equ 63708h      ; u32 tick of the last PONG received
DATA_HAVE       equ 6370Ch      ; u8  1 once a PONG came

G_LAST_RX       equ 5B908h
SEND_PEER       equ 19A98h      ; send_peer(rcx = data, edx = size)
TEXT_TEX        equ 2B2B8h      ; text_tex(rcx = device, rdx = string, r8d = px, r9d = 0) -> [rax+8] = width
QUAD            equ 290D8h      ; quad(xmm0 x, xmm1 y, xmm2 w, xmm3 h, [rsp+20h] color)
TEXT            equ 2B048h      ; text(rcx str, xmm1 x, xmm2 y, xmm3 size, [rsp+20h] color, [rsp+28h] align, [rsp+30h] bold)
NEXT_UI         equ 24820h      ; what the call site called before
G_SCALE         equ 5CBD8h      ; float UI scale
G_WIDTH         equ 5CAA8h      ; float screen width
IAT_TICK        equ 44240h      ; GetTickCount

.code
ORG 200h
ping_rx PROC
    push r11
    call rx_pc
rx_pc:
    pop r11                         ; r11 = image base + 63207h
    push rax
    push rdx
    push r8
    push r9
    push r10
    push rcx
    push rdi                        ; 8 pushes + 0A8h: entry rsp 16k+8 -> 16k
    sub rsp, 0A8h
    movdqu [rsp+40h], xmm0
    movdqu [rsp+50h], xmm1
    movdqu [rsp+60h], xmm2
    movdqu [rsp+70h], xmm3
    movdqu [rsp+80h], xmm4
    movdqu [rsp+90h], xmm5
    sub r11, 63207h                 ; image base

    mov dword ptr [r11+G_LAST_RX], r13d
    movzx ecx, byte ptr [rsi+4]
    cmp ecx, 21h
    je got_pong
    cmp ecx, 20h
    jne maybe_ping
    cmp ebx, 12
    jl rx_done
    mov dword ptr [rsp+20h], 504D5447h      ; 'GTMP'
    mov dword ptr [rsp+24h], 21h            ; PONG, flags 0, count 0
    mov eax, dword ptr [rsi+8]
    mov dword ptr [rsp+28h], eax
    jmp send

got_pong:
    cmp ebx, 12
    jl rx_done
    mov eax, r13d
    sub eax, dword ptr [rsi+8]
    cmp eax, 60000
    ja rx_done                      ; not ours / garbage
    cmp byte ptr [r11+DATA_HAVE], 0
    je first
    mov edx, dword ptr [r11+DATA_RTT]
    lea edx, [rdx+rdx*2+2]
    add eax, edx
    shr eax, 2
first:
    mov dword ptr [r11+DATA_RTT], eax
    mov dword ptr [r11+DATA_LASTPONG], r13d
    mov byte ptr [r11+DATA_HAVE], 1
    jmp rx_done

maybe_ping:
    mov eax, r13d
    sub eax, dword ptr [r11+DATA_LASTPING]
    cmp eax, 1000
    jb rx_done
    mov dword ptr [r11+DATA_LASTPING], r13d
    mov dword ptr [rsp+20h], 504D5447h
    mov dword ptr [rsp+24h], 20h            ; PING
    mov dword ptr [rsp+28h], r13d
send:
    lea rcx, [rsp+20h]
    mov edx, 12
    lea rax, [r11+SEND_PEER]
    call rax

rx_done:
    movdqu xmm0, [rsp+40h]
    movdqu xmm1, [rsp+50h]
    movdqu xmm2, [rsp+60h]
    movdqu xmm3, [rsp+70h]
    movdqu xmm4, [rsp+80h]
    movdqu xmm5, [rsp+90h]
    add rsp, 0A8h
    pop rdi
    pop rcx
    pop r10
    pop r9
    pop r8
    pop rdx
    pop rax
    pop r11
    movzx ecx, byte ptr [rsi+4]     ; the replaced instructions' result: ecx = type
    ret
ping_rx ENDP

ORG 400h
; Called instead of "call 24820h" right after the banner (rbx = D3D device, rdi = status string, maybe empty).
; Draws "ping N ms" in a box right of the banner box, then jumps to 24820h with rcx, rdx, r8, r9, xmm0-3 as they
; came in.
ping_draw PROC
    push rbp
    call dr_pc
dr_pc:
    pop rbp                         ; rbp = image base + 63406h
    push rsi
    push r12
    push r13
    push r14                        ; 5 pushes: entry 16k+8 -> 16k+8+40 = 16k
    sub rsp, 0E0h
    mov [rsp+60h], rcx
    mov [rsp+68h], rdx
    mov [rsp+70h], r8
    mov [rsp+78h], r9
    movdqu [rsp+80h], xmm0
    movdqu [rsp+90h], xmm1
    movdqu [rsp+0A0h], xmm2
    movdqu [rsp+0B0h], xmm3
    movdqu [rsp+0C0h], xmm6
    movdqu [rsp+0D0h], xmm7
    sub rbp, 63406h                 ; image base

    cmp byte ptr [rdi], 0
    je dr_done
    cmp byte ptr [rbp+DATA_HAVE], 0
    je dr_done
    call qword ptr [rbp+IAT_TICK]
    sub eax, dword ptr [rbp+DATA_LASTPONG]
    cmp eax, 5000
    jae dr_done

    ; "ping N ms" into [rsp+40h]
    mov dword ptr [rsp+40h], 676E6970h      ; "ping"
    mov byte ptr [rsp+44h], 20h
    mov eax, dword ptr [rbp+DATA_RTT]
    cmp eax, 9999
    jbe small
    mov eax, 9999
small:
    lea rsi, [rsp+58h]              ; digits backwards from here
    mov r12d, 10
digit:
    xor edx, edx
    div r12d
    add dl, 30h
    dec rsi
    mov byte ptr [rsi], dl
    test eax, eax
    jnz digit
    lea r13, [rsp+45h]
copy:
    mov al, byte ptr [rsi]
    mov byte ptr [r13], al
    inc rsi
    inc r13
    lea rax, [rsp+58h]
    cmp rsi, rax
    jb copy
    mov dword ptr [r13], 00736D20h          ; " ms\0"

    ; font size in px as the banner computes it: (int)(scale * 17 + 0.5)
    movss xmm0, dword ptr [rbp+G_SCALE]
    mov eax, 41880000h              ; 17.0
    movd xmm1, eax
    mulss xmm0, xmm1
    mov eax, 3F000000h              ; 0.5
    movd xmm1, eax
    addss xmm0, xmm1
    cvttss2si r14d, xmm0

    ; banner box width = text width + 36 * scale, right edge = width * 0.5 + box * 0.5
    mov rcx, rbx
    mov rdx, rdi
    mov r8d, r14d
    xor r9d, r9d
    lea rax, [rbp+TEXT_TEX]
    call rax
    xor ecx, ecx
    test rax, rax
    jz no_tex1
    mov ecx, dword ptr [rax+8]
no_tex1:
    cvtsi2ss xmm6, ecx
    movss xmm0, dword ptr [rbp+G_SCALE]
    mov eax, 42100000h              ; 36.0
    movd xmm1, eax
    mulss xmm0, xmm1
    addss xmm6, xmm0                ; banner box width
    mov eax, 3F000000h
    movd xmm1, eax
    mulss xmm6, xmm1
    movss xmm0, dword ptr [rbp+G_WIDTH]
    mulss xmm0, xmm1
    addss xmm6, xmm0                ; banner box right edge
    movss xmm0, dword ptr [rbp+G_SCALE]
    mov eax, 41000000h              ; 8.0 gap
    movd xmm1, eax
    mulss xmm0, xmm1
    addss xmm6, xmm0                ; our box x

    ; our text width
    mov rcx, rbx
    lea rdx, [rsp+40h]
    mov r8d, r14d
    xor r9d, r9d
    lea rax, [rbp+TEXT_TEX]
    call rax
    xor ecx, ecx
    test rax, rax
    jz no_tex2
    mov ecx, dword ptr [rax+8]
no_tex2:
    cvtsi2ss xmm7, ecx
    movss xmm0, dword ptr [rbp+G_SCALE]
    mov eax, 41C00000h              ; 24.0 = 12 padding each side
    movd xmm1, eax
    mulss xmm0, xmm1
    addss xmm7, xmm0                ; our box width

    ; quad(x, 46 s, w, 34 s, 0xc0181410)
    mov dword ptr [rsp+20h], 0C0181410h
    movss xmm4, dword ptr [rbp+G_SCALE]
    mov eax, 42080000h              ; 34.0
    movd xmm3, eax
    mulss xmm3, xmm4
    mov eax, 42380000h              ; 46.0
    movd xmm1, eax
    mulss xmm1, xmm4
    movaps xmm2, xmm7
    movaps xmm0, xmm6
    lea rax, [rbp+QUAD]
    call rax

    ; text(str, x + 12 s, 49 s, 17.0, 0xffa8f0a0, left, not bold)
    movss xmm4, dword ptr [rbp+G_SCALE]
    mov eax, 41400000h              ; 12.0
    movd xmm1, eax
    mulss xmm1, xmm4
    addss xmm1, xmm6
    mov eax, 42440000h              ; 49.0
    movd xmm2, eax
    mulss xmm2, xmm4
    mov eax, 41880000h              ; 17.0
    movd xmm3, eax
    mov dword ptr [rsp+20h], 0FFA8F0A0h
    mov dword ptr [rsp+28h], 0
    mov byte ptr [rsp+30h], 0
    lea rcx, [rsp+40h]
    lea rax, [rbp+TEXT]
    call rax

dr_done:
    lea rax, [rbp+NEXT_UI]
    mov rcx, [rsp+60h]
    mov rdx, [rsp+68h]
    mov r8, [rsp+70h]
    mov r9, [rsp+78h]
    movdqu xmm0, [rsp+80h]
    movdqu xmm1, [rsp+90h]
    movdqu xmm2, [rsp+0A0h]
    movdqu xmm3, [rsp+0B0h]
    movdqu xmm6, [rsp+0C0h]
    movdqu xmm7, [rsp+0D0h]
    add rsp, 0E0h
    pop r14
    pop r13
    pop r12
    pop rsi
    pop rbp
    jmp rax
ping_draw ENDP

ORG 700h
    dd 0, 0, 0, 0
END
