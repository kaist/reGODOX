/* CamLCD is global metadata, separate from the four bank payloads. */
extern void camlcd_stock_touch(void*,u8*);
extern void camlcd_stock_encoder(void*,u8*);
u32 camlcd_get(void) {State *s=bank_find_state();return s?(s->reserved_meta>>8)&1:0;}
void camlcd_set(u32 value) {
    State *s=bank_find_state();if(!s || value>1 || value==camlcd_get())return;
    s->reserved_meta=(s->reserved_meta&~256u)|(value<<8);bank_flush(s);
}
void *camlcd_tile_ref(void *tile) {
    Drawer *d=drawer_context(bank_find_state(),0);if(!d)return 0;
    if(tile)d->camlcd_tile=tile;return d->camlcd_tile;
}
static u32 camlcd_active(Drawer *d) {return d && (d->camlcd_auto || d->camlcd_pending);}
static void camlcd_dismiss(Drawer *d) {
    d->camlcd_pending=d->camlcd_dismiss_pending=d->camlcd_auto=0;
    if(d->root) {
        camera_consume_touch();
        FN(0x08026820,u32,(void*,void*))(d->root,0);
        FN(0x0802e310,void,(void*))(d->root);
    }
    d->camlcd_dim_seen=1;d->camera_restore=1;
    /* Same inactivity reset as native touch wake. No persistent setting is
     * changed, and the next auto-show needs a fresh bright->dim transition. */
    WORD(0x20000044u)=WORD(0x20000050u);
    WORD(0x20000048u)=WORD(0x20000050u);
    WORD(0x2000004cu)=*(volatile unsigned short*)0x200000fcu;
    FN(0x08013bcc,void,(void))();camera_request_ui();
}
void camlcd_dim_service(void) {
    FN(0x08013bcc,void,(void))();
    Drawer *d=drawer_context(bank_find_state(),0);if(!d)return;
    u32 dim=WORD(0x20000048u)==0;
    if(!dim) {d->camlcd_dim_seen=0;return;}
    if(d->camlcd_dim_seen)return;
    d->camlcd_dim_seen=1;
    if(camlcd_get() && !d->root && !BYTE(0x200003eau) && !BYTE(0x200004c9u)) {
        d->camlcd_pending=1;camera_request_ui();
    }
}
static void camlcd_poll(Drawer *d) {
    if(d->camlcd_dismiss_pending) {camlcd_dismiss(d);return;}
    if(d->camlcd_pending) {
        d->camlcd_pending=0;
        if(!camlcd_get() || d->root || BYTE(0x200003eau) || BYTE(0x200004c9u))return;
        camera_open();if(!d->root)return;
        d->camlcd_auto=1;
        FN(0x08026820,u32,(void*,void*))(d->root,0);POS(d->root,0,0);
        FN(0x08017650,void,(void*))(0);camera_request_ui();
    }
}
static u32 camlcd_gpio(u32 port,u32 mask,u32 raw) {
    u32 key=port==0x40020000u?(mask==0x200?1:mask==0x100?2:0):
        port==0x40020400u && mask==0x8000?4:0;
    if(!key)return raw;
    Drawer *d=drawer_context(bank_find_state(),0);if(!d)return raw;
    if(!raw && camlcd_active(d)) {
        /* GPIO can be scanned in an interrupt. Request GUI dismissal, while
         * preserving the native press so TEST/power/knob act normally. */
        d->camlcd_dismiss_pending=1;camera_request_ui();
    }
    return raw;
}
void camlcd_touch(void *driver,u8 *data) {
    camlcd_stock_touch(driver,data);
    Drawer *d=drawer_context(bank_find_state(),0);
    if(data[18] && camlcd_active(d)) {
        camlcd_dismiss(d);
        /* The read callback precedes copying data.state into indev.proc.
         * Consume the new press even if the old proc.state is RELEASED. */
        u8 *indev=FN(0x0802c4e4,u8*,(void))();if(indev)indev[5]|=8;
    }
}
void camlcd_encoder(void *driver,u8 *data) {
    Drawer *d=drawer_context(bank_find_state(),0);
    /* Restore the native encoder group before dispatching the same step or
     * click. The delta is latched by the physical encoder ISR at byte3B. */
    if(camlcd_active(d) && (BYTE(0x2000003bu) || !(WORD(0x40020410u)&0x8000u)))
        camlcd_dismiss(d);
    camlcd_stock_encoder(driver,data);
    if((*(short*)(data+16) || data[18]) && camlcd_active(d))camlcd_dismiss(d);
}
