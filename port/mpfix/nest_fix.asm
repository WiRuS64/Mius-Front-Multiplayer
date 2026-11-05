; mpfix: keep a followed vehicle's render model on its position (MiusPlayer release 2, Steam public 15814271).
;
; Bug: the joiner's game moves its own static emplacements (seen: mg_pznest) at the start of deployment. The host
; follows them by writing the unit's position (+0x1b0) and rotation (+0xf0) only. A moving vehicle's render model
; is refreshed from those by the engine every step; a static one's is not, so on the host the model, its node
; matrices (+0x1640, translation at +0x1670) and the crew seated in it stayed at the old place (845 m away).
;
; Fix: called from the mod's transform-apply loop (mod rva 0x1d182, r15 = unit, its new transform written). For an
; i_techn whose first node is more than 5 m (horizontal) from its position, call adv_physic+0xd930(unit, matrix),
; the engine's own "set render model transform" (the per-step update builds the same matrix from +0xf0 and +0x1b0),
; then do the instruction this call replaced: lea rcx, [r15+1d0h].
;
; Position independent, no relocations: the image base comes from the call/pop below; the mod's import of
; GetModuleHandleA (IAT rva 0x441b0) and its string "adv_physic.codelib" (rva 0x45e20) are reached through it.
; The section is placed at rva 63000h (see build_mpfix.py, which checks the offsets of the call/pop).

.code
nest_fix PROC
    push rbx
    call getpc
getpc:
    pop rbx                         ; rbx = image base + 63006h
    push rax
    push rcx
    push rdx
    push r8
    push r9
    push r10
    push r11
    sub rsp, 0C8h                   ; 16-byte aligned here (entry rsp = 16k+8, 8 pushes, 0C8h)
    movdqu [rsp+60h], xmm0
    movdqu [rsp+70h], xmm1
    movdqu [rsp+80h], xmm2
    movdqu [rsp+90h], xmm3
    movdqu [rsp+0A0h], xmm4
    movdqu [rsp+0B0h], xmm5
    sub rbx, 63006h                 ; image base

    mov rax, 3A6E686365745F69h      ; "i_techn:" at +8 (the object's name)
    cmp [r15+8], rax
    jne done
    cmp byte ptr [r15+0E0Ch], 0     ; node count
    je done
    movss xmm0, dword ptr [r15+1670h]
    subss xmm0, dword ptr [r15+1B0h]
    mulss xmm0, xmm0
    movss xmm1, dword ptr [r15+1678h]
    subss xmm1, dword ptr [r15+1B8h]
    mulss xmm1, xmm1
    addss xmm0, xmm1
    mov eax, 41C80000h              ; 25.0 = (5 m)^2
    movd xmm1, eax
    comiss xmm0, xmm1
    jbe done

    lea rcx, [rbx+45E20h]           ; "adv_physic.codelib"
    call qword ptr [rbx+441B0h]     ; GetModuleHandleA
    test rax, rax
    jz done
    mov rcx, 8B4820EC83485740h      ; 40 57 48 83 EC 20 48 8B: push rdi; sub rsp,20h; mov rdi,...
    cmp [rax+0D930h], rcx
    jne done
    lea rbx, [rax+0D930h]

    movups xmm0, [r15+0F0h]         ; rotation rows -> matrix rows 0..2 (w = 0)
    movups [rsp+20h], xmm0
    movups xmm0, [r15+100h]
    movups [rsp+30h], xmm0
    movups xmm0, [r15+110h]
    movups [rsp+40h], xmm0
    xor eax, eax
    mov [rsp+2Ch], eax
    mov [rsp+3Ch], eax
    mov [rsp+4Ch], eax
    mov rax, [r15+1B0h]             ; position -> row 3 (w = 1)
    mov [rsp+50h], rax
    mov eax, [r15+1B8h]
    mov [rsp+58h], eax
    mov dword ptr [rsp+5Ch], 3F800000h
    mov rcx, r15
    lea rdx, [rsp+20h]
    call rbx

done:
    movdqu xmm0, [rsp+60h]
    movdqu xmm1, [rsp+70h]
    movdqu xmm2, [rsp+80h]
    movdqu xmm3, [rsp+90h]
    movdqu xmm4, [rsp+0A0h]
    movdqu xmm5, [rsp+0B0h]
    add rsp, 0C8h
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdx
    pop rcx
    pop rax
    pop rbx
    lea rcx, [r15+1D0h]             ; the instruction the call replaced
    ret
nest_fix ENDP
END
