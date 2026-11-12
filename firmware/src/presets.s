.syntax unified
.thumb

.word init+1, callback+1, capture+1, apply_bank+1, refresh_ui+1, update_indicator+1, stock_save+1, code_end
init:
    push {r4, lr}
    bl 0x08035944
    movw r0, #996
    bl 0x0802d5c4
    cmp r0, #0
    beq init_done
    mov r4, r0
    movs r1, #0
    str r1, [r4]
    str r1, [r4, #4]
    str r1, [r4, #8]
    str r1, [r4, #12]
    str r1, [r4, #16]
    str r1, [r4, #20]
    str r1, [r4, #24]
    str r1, [r4, #28]
    str r1, [r4, #32]
    mov r0, r4
    bl 0x080ee000
    bl refresh_ui
    adr r0, callback
    adds r0, #1
    movs r1, #20
    mov r2, r4
    bl 0x08033500
init_done:
    pop {r4, pc}

    nop
callback:
    push {r4, r5, r6, r7, lr}
    sub sp, #4
    ldr r4, [r0, #12]
    cmp r4, #0
    beq done
    bl 0x080334d8
    mov r5, r0
    mov r0, r4
    bl update_indicator
    ldr r0, [r4, #8]
    cmp r0, #0
    beq check_button
    ldr r1, [r4, #12]
    subs r1, r5, r1
    cmp.w r1, #1000
    blo check_button
    bl 0x080303b8
    cmp r0, #0
    beq panel_already_deleted
    ldr r0, [r4, #8]
    bl 0x0802e428
panel_already_deleted:
    movs r0, #0
    str r0, [r4, #8]
check_button:
    movw r0, #0x003c
    movt r0, #0x2000
    ldrb r0, [r0]
    tst r0, #1
    bne held
    movs r0, #0
    str r0, [r4]
    b done
held:
    ldr r0, [r4]
    cmp r0, #0
    bne check_time
    movs r0, #1
    str r0, [r4]
    str r5, [r4, #4]
    b done
check_time:
    cmp r0, #1
    bne done
    ldr r0, [r4, #4]
    subs r0, r5, r0
    cmp.w r0, #500
    blo done
    movs r0, #2
    str r0, [r4]
    ldr r0, [r4, #20]
    cmp r0, #0
    bne banks_ready
    mov r0, r4
    movs r1, #0
    bl capture
    mov r0, r4
    movs r1, #1
    bl capture
    mov r0, r4
    movs r1, #2
    bl capture
    mov r0, r4
    movs r1, #3
    bl capture
    movs r0, #1
    str r0, [r4, #20]
banks_ready:
    mov r0, r4
    ldr r1, [r4, #16]
    bl capture
    ldr r1, [r4, #16]
    adds r1, #1
    cmp r1, #4
    blo bank_selected
    movs r1, #0
bank_selected:
    str r1, [r4, #16]
    mov r0, r4
    bl apply_bank
    mov r0, r4
    bl 0x080ee004
    bl refresh_ui
    mov r0, r4
    mov r1, r5
    bl 0x080ee008
done:
    add sp, #4
    pop {r4, r5, r6, r7, pc}
    nop
capture:
    push {r4, r5, r6, r7, r8, lr}
    .byte 0xef,0xf3,0x10,0x88
    cpsid i
    movs r2, #100
    mul r1, r1, r2
    add r5, r0, #64
    add r5, r1
    movw r4, #0x0b68
    movt r4, #0x2000
    movs r6, #0
capture_groups:
    ldrb r0, [r4, r6]
    strb r0, [r5, r6]
    adds r6, #1
    cmp r6, #96
    blo capture_groups
    movs r6, #5
capture_mask:
    ldrb r0, [r5, r6]
    and r0, r0, #1
    strb r0, [r5, r6]
    adds r6, #6
    cmp r6, #96
    blo capture_mask
    adr r7, fields
    movs r6, #0
capture_fields:
    ldr r4, [r7, r6, lsl #2]
    ldrb r0, [r4]
    add r1, r5, #96
    strb r0, [r1, r6]
    adds r6, #1
    cmp r6, #4
    blo capture_fields
    .byte 0x88,0xf3,0x10,0x88
    pop {r4, r5, r6, r7, r8, pc}

apply_bank:
    push {r4, r5, r6, r7, r8, lr}
    .byte 0xef,0xf3,0x10,0x88
    cpsid i
    movs r2, #100
    mul r1, r1, r2
    add r5, r0, #64
    add r5, r1
    movw r4, #0x0b68
    movt r4, #0x2000
    movs r6, #0
    movs r7, #5
apply_groups:
    ldrb r0, [r5, r6]
    cmp r6, r7
    bne apply_group_store
    ldrb r1, [r4, r6]
    bic r1, r1, #1
    orrs r0, r1
    adds r7, #6
apply_group_store:
    strb r0, [r4, r6]
    adds r6, #1
    cmp r6, #96
    blo apply_groups
    adr r7, fields
    movs r6, #0
apply_fields:
    ldr r4, [r7, r6, lsl #2]
    add r1, r5, #96
    ldrb r0, [r1, r6]
    strb r0, [r4]
    adds r6, #1
    cmp r6, #4
    blo apply_fields
    .byte 0x88,0xf3,0x10,0x88
    pop {r4, r5, r6, r7, r8, pc}
refresh_ui:
    push {r4, r5, r6, lr}
    movw r4, #0x03e5
    movt r4, #0x2000
    movs r0, #1
    strb r0, [r4]
    movw r4, #0x22fc
    movt r4, #0x2004
    ldr r0, [r4, #4]
    cmp r0, #0
    beq refresh_done
    bl 0x080303b8
    cmp r0, #0
    beq refresh_done
    ldr r0, [r4, #4]
    bl 0x0802ee16
    mov r5, r0
    bl 0x0803205a
    cmp r0, r5
    bne refresh_done
    bl 0x0803840c
refresh_done:
    pop {r4, r5, r6, pc}
update_indicator:
    push {r4, r5, r6, r7, lr}
    sub sp, #4
    mov r4, r0
    movw r0, #0x22fc
    movt r0, #0x2004
    ldr r7, [r0]
    cmp r7, #0
    beq indicator_done
    mov r0, r7
    bl 0x080303b8
    cmp r0, #0
    beq indicator_done
    mov r0, r7
    bl 0x0802ee0a
    mov r7, r0
    cmp r7, #0
    beq indicator_done
    ldr r6, [r4, #24]
    cmp r6, #0
    beq indicator_create
    mov r0, r6
    bl 0x080303b8
    cmp r0, #0
    beq indicator_create
    mov r0, r6
    bl 0x0802ee0a
    cmp r0, r7
    beq indicator_existing
    mov r0, r6
    bl 0x0802e428
    movs r0, #0
    str r0, [r4, #24]
indicator_create:
    mov r0, r7
    bl 0x0802c9fc
    cmp r0, #0
    beq indicator_done
    mov r6, r0
    str r6, [r4, #24]
    str r7, [r4, #28]
    movw r1, #0xbbe0
    movt r1, #0x0804
    movs r2, #0
    bl 0x080316cc
    mov r0, r6
    movw r1, #0xffe0
    movs r2, #0
    bl 0x080316b4
    mov r0, r6
    movs r1, #107
    movs r2, #8
    bl 0x08031318
    movs r0, #255
    str r0, [r4, #32]
indicator_existing:
    ldr r5, [r4, #16]
    ldr r0, [r4, #32]
    cmp r0, r5
    beq indicator_done
    adr r1, bank_names
    add r1, r1, r5, lsl #2
    mov r0, r6
    bl 0x0802d33c
    str r5, [r4, #32]
indicator_done:
    add sp, #4
    pop {r4, r5, r6, r7, pc}
stock_save:
    push {r4, r5, r6, lr}
    bl 0x08006c90
    b.w 0x08013b86
code_end:
.balign 4
fields:
.word 0x20000054, 0x20000055, 0x200003df, 0x20000484
message:
.asciz "BANK 1"
.space 9
.asciz "BANK 2"
.space 9
.asciz "BANK 3"
.space 9

.balign 4
bank_names:
.asciz "P1"
.byte 0
.asciz "P2"
.byte 0
.asciz "P3"
.byte 0

.asciz "P4"
.byte 0
