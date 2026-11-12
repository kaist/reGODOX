/* Native LVGL objects/fonts. State offsets 36..48 were reserved in the
 * existing 996-byte context; persistent payload and flash format unchanged. */
typedef unsigned int u32;
#define FN(a,r,args) ((r (*)args)((a)|1u))
#define VALID FN(0x080302a0,u32,(u32))
#define SCREEN FN(0x0802ecfe,u32,(u32))
#define PARENT FN(0x0802ecf2,u32,(u32))
#define ACTIVE FN(0x08031f42,u32,(void))
#define CREATE FN(0x0802e2f4,u32,(u32))
#define LABEL FN(0x0802c8e4,u32,(u32))
#define DELETE FN(0x0802e310,void,(u32))
#define SIZE FN(0x0803129a,void,(u32,u32,u32))
#define CENTER FN(0x0802e010,void,(u32))
#define ALIGN FN(0x0802da2c,void,(u32,u32,int,int))
#define TEXT FN(0x0802d224,void,(u32,const char*))
#define REMOVE_STYLE FN(0x08030d12,void,(u32,u32,u32))
#define CLEAR_FLAGS FN(0x0802e1ba,void,(u32,u32))
#define STYLE(a,o,v) FN(a,void,(u32,u32,u32))(o,v,0)

static u32 label(u32 parent,const char *text,u32 font,u32 color,u32 y) {
    u32 obj=LABEL(parent);
    if(!obj)return 0;
    STYLE(0x080315b4,obj,font);
    STYLE(0x0803159c,obj,color);
    TEXT(obj,text);
    ALIGN(obj,2,0,y); /* LV_ALIGN_TOP_MID */
    return obj;
}
static void popup_deleted(u32 *event) {
    u32 *state=(u32*)event[3];
    if(state && state[2]==event[1])
        state[2]=state[9]=state[10]=state[11]=state[12]=0;
}
__attribute__((used,noinline)) void preset_popup(u32 *state,u32 tick) {
    static const char *const digits[4]={"1","2","3","4"};
    if(state[4]>3)return;
    u32 screen=ACTIVE();
    if(!screen)return;
    u32 panel=state[2];
    if(panel && VALID(panel)) {
        u32 number=state[10];
        if(SCREEN(panel)==screen && number && VALID(number) && PARENT(number)==panel) {
            TEXT(number,digits[state[4]]);
            ALIGN(number,2,0,102);
            state[3]=tick;
            return;
        }
        DELETE(panel);
    }
    state[2]=state[9]=state[10]=state[11]=state[12]=0;
    panel=CREATE(screen);
    if(!panel)return;
    FN(0x0802d862,void,(u32,void (*)(u32*),u32,u32))(panel,popup_deleted,33,(u32)state);
    /* Native factory: remove all styles with NULL style + ANY selector.
     * This is a THREE-argument API, distinct from the flag clear below. */
    REMOVE_STYLE(panel,0,0x000fffff);
    CLEAR_FLAGS(panel,0x16); /* CLICKABLE | CLICK_FOCUSABLE | SCROLLABLE */
    SIZE(panel,256,200);
    STYLE(0x08031522,panel,0); /* native set_pad_all */
    STYLE(0x08031464,panel,0x2124); /* native dark grey, RGB(39,39,39) */
    STYLE(0x0803147c,panel,255);
    STYLE(0x0803157e,panel,15); /* rounded corners */
    STYLE(0x080314a8,panel,1);  /* border width */
    STYLE(0x0803149e,panel,255);
    STYLE(0x08031486,panel,0x52aa);
    /* Main group rows occupy y=40..344; their center is y=192. */
    ALIGN(panel,9,0,-32);
    u32 title=label(panel,"PRESET",0x0804ec30,0xffff,44);
    u32 number=label(panel,digits[state[4]],0x080dfc50,0xffe0,102);
    if(!title || !number) {DELETE(panel);return;}
    state[2]=panel;state[3]=tick;
    state[9]=title;state[10]=number;state[11]=0;state[12]=screen;
}
