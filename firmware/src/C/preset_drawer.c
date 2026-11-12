/* Native LVGL overlay; the stock upper shade and its gesture handler remain. */
typedef struct {
    State *state;
    void *root,*group,*previous_group,*buttons[4];
    u32 closing;
#ifdef CAMERA_SHEET
    u32 kind,seen,revision,painted_revision,shown_seen;
    u8 camera_values[4];
    char shown[4][24];
    void *camera_labels[4],*camera_status;
    void *camera_edge,*camera_edge_parent;
    u32 camera_edge_visible,camera_restore;
    u8 *camera_font_bitmap;
    void *camera_pager;u32 camera_pager_scrollable;
    void *camera_link_slash,*camera_shutter_prefix;
    u32 camera_value_fonts[3],camera_swipe_armed;
    void *camlcd_tile;
    u32 camlcd_auto,camlcd_pending,camlcd_dim_seen,camlcd_wake_keys,camlcd_dismiss_pending;
#endif
} Drawer;
#ifdef CAMERA_SHEET
static void camera_open(void);
static void camera_update(Drawer *d);
static void camera_edge_update(Drawer *d);
static u32 camera_link_state(void);
static void camlcd_poll(Drawer *d);
static u32 camlcd_gpio(u32 port,u32 mask,u32 raw);
#endif
extern void drawer_stock_main_event(u8 *);
static Drawer *drawer_context(State *s,u32 create) {
    if(!s)return 0;
    Drawer *d=(Drawer*)HEAD(s,15);
    if(!d && create) {
        d=FN(0x0802d5c4,Drawer*,(u32))(sizeof(Drawer));
        if(!d)return 0;
        for(u32 i=0;i<sizeof(Drawer)/4;i++)((u32*)d)[i]=0;
        d->state=s;d->group=FN(0x0802b608,void*,(void))();
        HEAD(s,15)=(u32)d;
    }
    return d;
}
u32 drawer_is_open(State *s) {
    Drawer *d=drawer_context(s,0);return d && d->root;
}
static u32 drawer_direction(void) {
    void *indev=FN(0x0802c5fc,void*,(void))();
    return indev?FN(0x0802c608,u32,(void*))(indev):0;
}
#ifdef CAMERA_SHEET
static void camera_consume_touch(void) {
    u8 *indev=FN(0x0802c5fc,u8*,(void))();
    /* Native LVGL wait_until_release bit, verified in its pointer reader.
     * Otherwise the sliding/deleted overlay exposes a button to the SAME
     * still-held finger, producing a phantom press on the main screen. */
    if(indev && BYTE(*(u32*)indev)==1 && indev[4])indev[5]|=8;
}
#endif
static void drawer_animate(void *root,i32 from,i32 to,void (*ready)(u32*)) {
    u32 anim[24];FN(0x080269c8,void,(u32*))(anim);
    anim[0]=(u32)root;anim[1]=0x08019135u;anim[3]=(u32)ready;
#ifdef CAMERA_SHEET
    Drawer *d=drawer_context(bank_find_state(),0);
    if(d && d->kind)anim[1]=0x0803172bu;
#endif
    anim[7]=0x08026a6bu;anim[8]=from;anim[9]=from;anim[10]=to;anim[11]=220;
    FN(0x08026aac,void*,(u32*))(anim);
}
static void drawer_close_ready(u32 *animation) {
    void *root=(void*)animation[0];
    if(root && VALID(root))FN(0x0802e428,void,(void*))(root);
}
static void drawer_close(Drawer *d) {
    if(!d || !d->root || d->closing)return;
#ifdef CAMERA_SHEET
    camera_consume_touch();
#endif
    d->closing=1;
#ifdef CAMERA_SHEET
    if(d->kind)d->camera_restore=6;
#endif
    i32 end=448;
#ifdef CAMERA_SHEET
    if(d->kind)end=-368;
#endif
    drawer_animate(d->root,0,end,drawer_close_ready);
}
void drawer_poll(State *s) {
    Drawer *d=drawer_context(s,0);
    if(!d)return;
#ifdef CAMERA_SHEET
    if(d->camera_restore && !d->root) {
        d->camera_restore=0;
        if(d->camera_pager && VALID(d->camera_pager) && d->camera_pager_scrollable)
            FN(0x0802da22,void,(void*,u32))(d->camera_pager,0x10);
        d->camera_pager=0;
    }
    camlcd_poll(d);
    camera_edge_update(d);
#endif
    u32 pressed=!(WORD(0x40020010u)&0x100u);
    if(d->root && pressed && !d->closing)drawer_close(d);
#ifdef CAMERA_SHEET
    if(d->root && d->kind && !d->closing && (d->painted_revision!=d->revision || d->shown_seen!=camera_link_state()))camera_update(d);
#endif
}
u32 drawer_gpio_read(u32 port,u32 mask) {
    /* Consume the short modal dismiss press before native handlers can open
     * the upper shade. Raw PA8 remains available to drawer_poll. After the
     * close animation a held key resumes the original shutdown behavior. */
    u32 raw=(WORD(port+0x10)&mask)==mask;
#ifdef CAMERA_SHEET
    raw=camlcd_gpio(port,mask,raw);
#endif
    if(port==0x40020000u && mask==0x100u && drawer_is_open(bank_find_state())) {
#ifdef CAMERA_SHEET
        Drawer *d=drawer_context(bank_find_state(),0);
        if(d && (d->camlcd_auto || d->camlcd_pending))return raw;
#endif
        return 1;
    }
    return raw;
}
static void drawer_event(u8 *e) {
    Drawer *d=(Drawer*)*(u32*)(e+12);if(!d)return;
    if(e[8]==33) {
        if(*(void**)(e+4)!=d->root)return;
        d->root=0;d->closing=0;
        FN(0x0802c912,void,(void*,void*))((void*)WORD(0x200003d0u),d->previous_group);
        FN(0x0802b798,void,(void*))(d->group);
        return;
    }
    u32 direction=8;
#ifdef CAMERA_SHEET
    if(d->kind)direction=1;
#endif
    if(e[8]==12 && drawer_direction()==direction)drawer_close(d);
}
static void drawer_mark(Drawer *d) {
    for(u32 i=0;i<count_value(d->state);i++) {
        void *button=d->buttons[i];u32 chosen=i==d->state->active;
        FN(0x080315c0,void,(void*,u32,u32))(button,chosen?4:0,0);
        FN(0x0803159e,void,(void*,u32,u32))(button,0xffe0,0);
        void *text=FN(0x0802ebc8,void*,(void*,i32))(button,0);
        COLOR(text,chosen?0xffe0:0xffff,0);
    }
}
static void drawer_button(u8 *e) {
    if(e[8]!=7)return;
    Drawer *d=(Drawer*)*(u32*)(e+12);if(!d || d->closing)return;
    u32 index=FN(0x0802ed92,u32,(void*))(*(void**)(e+4));
    State *s=d->state;
    if(index>=count_value(s))return;
    if(index!=s->active) {
        CAPTURE(s,s->active);s->active=index;APPLY(s,index);
        bank_flush(s);FN(ASM_REFRESH,void,(void))();
    }
    drawer_mark(d);
    drawer_close(d);
}
static void *drawer_box(void *parent,i32 x,i32 y,i32 w,i32 h,u32 color,u32 radius,u32 clickable) {
    void *obj=OBJ_CREATE(parent);if(!obj)return 0;
    FN(0x08030e2a,void,(void*,void*,u32))(obj,0,0xfffff);
    FN(0x0802e2d2,void,(void*,u32))(obj,0x316);
    if(clickable)FN(0x0802da22,void,(void*,u32))(obj,2);
    POS(obj,x,y);SIZE(obj,w,h);
    FN(0x0803157c,void,(void*,u32,u32))(obj,color,0);
    FN(0x08031594,void,(void*,u32,u32))(obj,255,0);
    FN(0x08031696,void,(void*,u32,u32))(obj,radius,0);
    return obj;
}
void drawer_open(void) {
    State *s=bank_find_state();
    if(!s || BYTE(0x200003e7u) || BYTE(0x200003e4u))return;
    Drawer *d=drawer_context(s,1);if(!d || d->root)return;
#ifdef CAMERA_SHEET
    d->kind=0;
#endif
    if(s->panel && VALID((void*)s->panel))FN(0x0802e428,void,(void*))((void*)s->panel);
    s->panel=0;HEAD(s,9)=HEAD(s,10)=HEAD(s,11)=HEAD(s,12)=0;
    void *screen=FN(0x0803205a,void*,(void))();
    d->root=drawer_box(screen,0,448,368,448,0x39c7,0,1);
    if(!d->root)return;
    d->closing=0;
    FN(0x0802e2d2,void,(void*,u32))(d->root,0x8000);
    EVENT(d->root,drawer_event,12,d);EVENT(d->root,drawer_event,33,d);
    drawer_box(d->root,138,8,92,6,0xffff,0,0);
    void *title_box=drawer_box(d->root,12,22,344,84,0x1082,42,0);
    void *title=LABEL(title_box);FONT(title,0x0804ed50,0);COLOR(title,0xffff,0);
    TEXT(title,"PRESETS");ALIGN(title,9,0,0);
    void *panel=drawer_box(d->root,12,116,344,320,0x1082,50,0);
    u32 count=count_value(s);
    static const char *const names[]={"P1","P2","P3","P4"};
    FN(0x0802b798,void,(void*))(d->group);
    for(u32 i=0;i<count;i++) {
        i32 x=40+(i%2)*156,y=40+(i/2)*132;
        if(count==2)y=106;
        if(count==3 && i==2)x=118;
        void *button=drawer_box(panel,x,y,108,108,0x2124,54,1);
        d->buttons[i]=button;
        void *text=LABEL(button);FONT(text,0x0805c9f4,0);COLOR(text,0xffff,0);
        TEXT(text,names[i]);ALIGN(text,9,0,0);
        EVENT(button,drawer_button,7,d);
        /* remove_style_all also removes theme outline opacity. Set the full
         * focus style explicitly, for FOCUSED and keyboard FOCUS_KEY. */
        for(u32 focus=2;focus<=4;focus+=2) {
            FN(0x08031604,void,(void*,u32,u32))(button,0xffff,focus);
            FN(0x08031630,void,(void*,u32,u32))(button,4,focus);
            FN(0x08031626,void,(void*,u32,u32))(button,5,focus);
            FN(0x0803161c,void,(void*,u32,u32))(button,255,focus);
        }
        GROUP_ADD(d->group,button);
    }
    drawer_mark(d);
    d->previous_group=(void*)WORD(0x20000470u);
    FN(0x0802c912,void,(void*,void*))((void*)WORD(0x200003d0u),d->group);
    FOCUS(d->buttons[s->active]);
    drawer_animate(d->root,448,0,0);
}
void drawer_main_event(u8 *e) {
    if(e[8]==12 && !BYTE(0x200003e7u) && !BYTE(0x200003e4u) && drawer_direction()==4) {
        drawer_open();return;
    }
    drawer_stock_main_event(e);
}
#ifdef CAMERA_SHEET
#include "camera_sheet.c"
#include "camlcd.c"
#endif
