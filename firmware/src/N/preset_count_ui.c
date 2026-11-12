/* Included after preset_count_banks.c: share its allocated timer State. */
#define BYTE(a) (*(volatile u8 *)(a))
#define WORD(a) (*(volatile u32 *)(a))
#define OBJ_CREATE FN(0x0802e2f4,void*,(void*))
#define LABEL FN(0x0802c8e4,void*,(void*))
#define TEXT FN(0x0802d224,void,(void*,const char*))
#define VALID FN(0x080302a0,u32,(void*))
#define FONT FN(0x080315b4,void,(void*,u32,u32))
#define COLOR FN(0x0803159c,void,(void*,u32,u32))
#define SIZE FN(0x0803129a,void,(void*,i32,i32))
#define POS FN(0x08031200,void,(void*,i32,i32))
#define ALIGN FN(0x0802da2c,void,(void*,u32,i32,i32))
#define EVENT FN(0x0802d862,void,(void*,void (*)(u8*),u32,void*))
#define SELECT FN(0x08031ea2,void,(void*,u32,u32))
#define SELECTED FN(0x08031d30,u32,(void*))
#define GROUP_ADD FN(0x0802b46c,void,(void*,void*))
#define FOCUS FN(0x0802b558,void,(void*))
#define HEAD(s,n) (((u32*)(s))[n])
extern void count_stock_focus(u32);
#ifdef CAMERA_SHEET
u32 camlcd_get(void);void camlcd_set(u32 value);void *camlcd_tile_ref(void *tile);
#endif
#ifdef PRESET_DRAWER
u32 drawer_is_open(State *s);
void drawer_poll(State *s);
#endif
void count_indicator(State *s) {
    if(BYTE(0x200003e7u)!=0) {
        /* Native settings replace the complete main screen. Discard cached
         * child pointers before that heap memory can hold new menu objects. */
        s->indicator=0;s->parent=0;s->indicator_bank=255;
        return;
    }
#ifdef CAMERA_SHEET
    if(drawer_is_open(s) || BYTE(0x200003e4u)!=0)return;
#endif
    if(BYTE(0x200003e4u)>=0x80)return;
    FN(ASM_INDICATOR,void,(State*))(s);
}
u32 count_button_gate(State *s) {
    u32 allowed=BYTE(0x200003e7u)==0 && BYTE(0x200003e4u)==0;
#ifdef PRESET_DRAWER
    drawer_poll(s);
    if(drawer_is_open(s))allowed=0;
#endif
    void *header=(void*)WORD(0x200422f8u);
    if(allowed && (!header || !VALID(header)))allowed=0;
    if(allowed && FN(0x0802ecfe,u32,(void*))(header)!=FN(0x08031f42,u32,(void))())allowed=0;
    if(allowed) {
        void *p=header;
        for(u32 i=0;p && i<16;i++) {
            if(FN(0x0802fb86,u32,(void*,u32))(p,1)) {allowed=0;break;}
            p=FN(0x0802ecf2,void*,(void*))(p);
        }
    }
    if(!allowed) {
        /* Close the toast before the native screen transition frees its
         * parent. Otherwise its saved pointer can be reused by a menu widget
         * before the delayed timeout tries to delete it. */
        void *panel=(void*)s->panel;
        if(panel && VALID(panel) && FN(0x0802ecfe,u32,(void*))(panel)==HEAD(s,12))
            FN(0x0802e310,void,(void*))(panel);
        s->panel=0;HEAD(s,9)=HEAD(s,10)=HEAD(s,11)=HEAD(s,12)=0;
        s->phase=(BYTE(0x2000003cu)&1)?2:0;
    }
    return 0x2000003cu;
}
static u32 count_value(State *s) {
    return s && (s->reserved_meta&255)>=2 && (s->reserved_meta&255)<=4?(s->reserved_meta&255):4;
}
u32 count_get(void) { return count_value(bank_find_state()); }
void count_set(u32 n) {
    State *s=bank_find_state();
    if(!s || n<2 || n>4 || n==count_value(s))return;
    CAPTURE(s,s->active);
    s->reserved_meta=(s->reserved_meta&~255u)|n;
    if(s->active>=n) {
        s->active=0;APPLY(s,0);
        FN(ASM_REFRESH,void,(void))();
    }
    bank_flush(s);
}
void count_event(u8 *e) {
    if(e[8]!=28 || BYTE(0x200004cfu))return;
    u32 selected=SELECTED(*(void**)(e+4));
#ifdef CAMERA_SHEET
    if(BYTE(0x200004c4u)==15) {if(selected<2)camlcd_set(selected);return;}
#endif
    if(selected<3)count_set(selected+2);
}
void count_tile_event(u8 *e) {
    if(e[8]!=4 || BYTE(0x200004c9u))return;
    BYTE(0x200004cbu)=10;
    u32 page=(u32)*(void**)(e+12);
    BYTE(0x200004c4u)=page;
    BYTE(0x2000065cu)=1;
    BYTE(0x200004c8u)=page;
}
static void count_icon(void *tile,u32 camera) {
    /* Match the native menu's white outline symbols with code-native shapes.
     * Opaque card faces hide the rear outlines where the cards overlap. */
    for(u32 i=0;i<(camera?1:3);i++) {
        void *card=OBJ_CREATE(tile);if(!card)return;
        FN(0x08030d12,void,(void*,void*,u32))(card,0,0xfffff);
        FN(0x0802e1ba,void,(void*,u32))(card,0x16);
        SIZE(card,66,56);POS(card,40+i*9,24+i*8);
        FN(0x08031464,void,(void*,u32,u32))(card,0x2124,0);
        FN(0x0803147c,void,(void*,u32,u32))(card,255,0);
        FN(0x0803157e,void,(void*,u32,u32))(card,8,0);
        FN(0x080314a8,void,(void*,u32,u32))(card,4,0);
        FN(0x08031486,void,(void*,u32,u32))(card,0xffff,0);
        FN(0x0803149e,void,(void*,u32,u32))(card,255,0);
        if(camera) {
            void *lens=OBJ_CREATE(card);
            FN(0x08030d12,void,(void*,void*,u32))(lens,0,0xfffff);
            FN(0x0802e1ba,void,(void*,u32))(lens,0x16);
            SIZE(lens,28,28);ALIGN(lens,9,0,0);
            FN(0x0803157e,void,(void*,u32,u32))(lens,14,0);
            FN(0x080314a8,void,(void*,u32,u32))(lens,4,0);
            FN(0x08031486,void,(void*,u32,u32))(lens,0xffff,0);
        }
    }
}
void count_append(void *parent) {
    State *s=bank_find_state();if(!s)return;
    for(u32 page=14;page<=
#ifdef CAMERA_SHEET
    15
#else
    14
#endif
    ;page++) {
    void *tile=FN(0x08006224,void*,(void*,u32,i32,i32,i32,i32))(parent,1,page==14?191:10,page==14?1080:1260,166,168);
    if(!tile)return;
    if(page==14)HEAD(s,13)=(u32)tile;
#ifdef CAMERA_SHEET
    else camlcd_tile_ref(tile);
#endif
    FN(0x0803157e,void,(void*,u32,u32))(tile,25,0);
    FN(0x08031464,void,(void*,u32,u32))(tile,0x2124,0);
    FN(0x0803147c,void,(void*,u32,u32))(tile,255,0);
    count_icon(tile,page==15);
    void *name=LABEL(tile);FONT(name,0x0804ec30,0);COLOR(name,0xffff,0);
    TEXT(name,page==14?"Presets":"CamLCD");ALIGN(name,2,0,115);
    EVENT(tile,count_tile_event,0,(void*)page);
    }
}
void count_page(void *parent,u32 index) {
    if(index!=14
#ifdef CAMERA_SHEET
       && index!=15
#endif
    ) {FN(0x08006f10,void,(void*,u32))(parent,index);return;}
    State *s=bank_find_state();if(!s)return;
    void *title=LABEL(parent);FONT(title,0x0804ec30,0);COLOR(title,0xffff,0);
    TEXT(title,index==14?"Presets":"CamLCD");ALIGN(title,2,0,80);
    void *roller=FN(0x08031b68,void*,(void*))(parent);
    if(!roller)return;
    HEAD(s,14)=(u32)roller;
    FN(0x0802e1ba,void,(void*,u32))(roller,0x300);
    u32 font=index==15?0x0805c8d4:0x080dfc50;
    FONT(roller,font,0);FONT(roller,font,0x40000);COLOR(roller,0xffff,0);
    COLOR(roller,0xffff,0x40000);
    FN(0x08031464,void,(void*,u32,u32))(roller,0,0);
    FN(0x08031464,void,(void*,u32,u32))(roller,0,0x40000);
    FN(0x0803147c,void,(void*,u32,u32))(roller,255,0);
    FN(0x0803157e,void,(void*,u32,u32))(roller,15,0);
    FN(0x080314a8,void,(void*,u32,u32))(roller,0,0);
    FN(0x080315be,void,(void*,u32,u32))(roller,15,0);
    FN(0x080314ec,void,(void*,u32,u32))(roller,0xffff,4);
    FN(0x080314ec,void,(void*,u32,u32))(roller,0xfce1,8);
    FN(0x0803150e,void,(void*,u32,u32))(roller,6,4);
    FN(0x0803150e,void,(void*,u32,u32))(roller,6,8);
    FN(0x08031dc8,void,(void*,const char*,u32))(roller,index==14?"2\n3\n4":"Off\nOn",0);
    FN(0x08031efc,void,(void*,u32))(roller,3);
    SIZE(roller,180,164);POS(roller,94,130);
        u32 selected=count_value(s)-2;
#ifdef CAMERA_SHEET
    if(index==15)selected=camlcd_get();
#endif
    SELECT(roller,selected,0);
    EVENT(roller,(void (*)(u8*))0x08034f39u,18,0);
    EVENT(roller,(void (*)(u8*))0x08034f39u,20,0);
    EVENT(roller,(void (*)(u8*))0x08034f39u,25,0);
    EVENT(roller,count_event,28,0);
}
void count_focus(u32 index) {
    State *s=bank_find_state();
    void *group=(void*)WORD(0x20000470u);
    if(index==14
#ifdef CAMERA_SHEET
       || index==15
#endif
    ) {
        FN(0x0802b680,void,(void*))(group);
        FN(0x0802b79a,void,(void*,u32))(group,0);
        void *roller=s?(void*)HEAD(s,14):0;
        if(roller && VALID(roller)) {
            GROUP_ADD(group,roller);
            /* This page has one control: turning the wheel edits it directly. */
            FN(0x0802b79a,void,(void*,u32))(group,1);
        }
        return;
    }
    u32 remembered=BYTE(0x200004c8u);
    if(index==0 && remembered>=14)BYTE(0x200004c8u)=1;
    count_stock_focus(index);
    if(index==0) {
        BYTE(0x200004c8u)=remembered;
        void *tile=s?(void*)HEAD(s,13):0;
        if(BYTE(0x200003ddu) && tile && VALID(tile)) {
            GROUP_ADD(group,tile);
            if(remembered==14)FOCUS(tile);
        }
#ifdef CAMERA_SHEET
        tile=camlcd_tile_ref(0);
        if(BYTE(0x200003ddu) && tile && VALID(tile)) {
            GROUP_ADD(group,tile);if(remembered==15)FOCUS(tile);
        }
#endif
    }
}
