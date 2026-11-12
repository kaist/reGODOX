/* Scale the original numeric glyphs to 2x / 1.5x without storing a second
 * bitmap font in flash. LVGL consumes this scratch bitmap synchronously. */
static u32 camera_large_dsc(const void *font,u8 *out,u32 ch,u32 next) {
    u32 num=*(const i32*)((const u8*)font+8)==68?3:2,den=num==3?2:1;
    u32 ok=FN(0x0802af18,u32,(u32,u8*,u32,u32))(0x0805c9f4,out,ch,next);
    if(ok) {
        for(u32 i=4;i<10;i+=2) {
            unsigned short *v=(unsigned short*)(out+i);*v=(*v*num+den-1)/den;
        }
        for(u32 i=10;i<14;i+=2) {
            short *v=(short*)(out+i);*v=(*v*(i32)num)/(i32)den;
        }
    }
    return ok;
}
static const u8 *camera_large_bitmap(const void *font,u32 ch) {
    u32 num=*(const i32*)((const u8*)font+8)==68?3:2,den=num==3?2:1;
    Drawer *d=drawer_context(bank_find_state(),0);
    if(!d || !d->camera_font_bitmap)return 0;
    u8 desc[20];
    if(!FN(0x0802af18,u32,(u32,u8*,u32,u32))(0x0805c9f4,desc,ch,0))return 0;
    const u8 *src=FN(0x0802ae30,const u8*,(u32,u32))(0x0805c9f4,ch);
    u32 w=*(unsigned short*)(desc+6),h=*(unsigned short*)(desc+8),bpp=desc[14]&15;
    u32 outw=(w*num+den-1)/den,outh=(h*num+den-1)/den;
    if(!src || !bpp || (outw*outh*bpp+7)/8>2560)return 0;
    u32 mask=(1u<<bpp)-1;
    u8 *dst=d->camera_font_bitmap;
    for(u32 i=0;i<(outw*outh*bpp+7)/8;i++)dst[i]=0;
    for(u32 y=0;y<outh;y++)for(u32 x=0;x<outw;x++) {
        u32 bit=((y*den/num)*w+x*den/num)*bpp;
        u32 pixel=(src[bit/8]>>(8-bpp-bit%8))&mask;
        bit=(y*outw+x)*bpp;
        dst[bit/8]|=pixel<<(8-bpp-bit%8);
    }
    return dst;
}
typedef struct {
    void *dsc,*bitmap;i32 height,baseline;u32 style;void *data,*fallback,*user;
} CameraFont;
static const CameraFont camera_large_font={(void*)camera_large_dsc,(void*)camera_large_bitmap,90,20,0,0,0,0};
static const CameraFont camera_medium_font={(void*)camera_large_dsc,(void*)camera_large_bitmap,68,15,0,0,0,0};
static u32 camera_value_font(u32 field,const char *text) {
    u32 width=0;
    for(u32 i=0;text[i];i++) {
        u8 desc[20];
        if(FN(0x0802af18,u32,(u32,u8*,u32,u32))(0x0805c9f4,desc,text[i],text[i+1]))
            width+=*(unsigned short*)(desc+4);
    }
    u32 available=240;
    if(width*2<=available)return (u32)&camera_large_font;
    /* Long ISO values keep a large 1.5x face instead of dropping to 45px. */
    if((width*3+1)/2+8<=available)return (u32)&camera_medium_font;
    return 0x0805c9f4;
}
static void camera_request_ui(void) {
    /* Native main loop skips lv_timer_handler when 6A!=0, B4==0, 25==0.
     * Its own camera-active change (0800C294) and control-change path
     * (0800694A) set B4=10. Reuse that bounded
     * wake budget, without fabricating touch events or resetting sleep time. */
    u32 irq=irq_get();irq_disable();
    if(BYTE(0x200000b4u)<10)BYTE(0x200000b4u)=10;
    irq_restore(irq);
}
/* Receive-side observer never allocates or calls LVGL. The existing 20ms UI
 * timer paints only changed strings, with an atomic four-byte snapshot. */
void camera_context_init(State *s) { drawer_context(s,1); }
u32 camera_status_received(void) {
    u32 result=FN(0x0800c1e8,u32,(void))();
    Drawer *d=drawer_context(bank_find_state(),0);
    if(d) {
        /* Use the validated packet copy: native working zoom may be kept or
         * overridden by local settings when the camera is not active. */
        u32 zoom=BYTE(0x20000ca9u)&0x7fu;
        u8 next[4]={BYTE(0x20000ca8u),BYTE(0x20000ca7u),BYTE(0x20000caau),
            zoom>=1 && zoom<=9?BYTE(0x0803c690u+zoom):0};
        u32 changed=!d->seen;
        for(u32 i=0;i<3;i++)if(next[i]!=d->camera_values[i])changed=1;
        if(changed) {
            for(u32 i=0;i<4;i++)d->camera_values[i]=next[i];
            d->seen=1;d->revision++;
            if(d->root && d->kind && !d->closing)camera_request_ui();
        }
    }
    return result;
}
static void camera_text(char *to,const char *from) {do {*to++=*from;}while(*from++);}
static void camera_number(char *to,u32 value) {
    char reverse[10];u32 n=0;
    do {reverse[n++]='0'+value%10;value/=10;}while(value);
    while(n)*to++=reverse[--n];*to=0;
}
static void camera_format(u32 field,u32 raw,u32 seen,char *buf) {
    if(!seen || raw==255) {camera_text(buf,"--");return;}
    if(field==3) {
        if(raw) {
            camera_number(buf,raw);
        }else camera_text(buf,"--");return;
    }
    int index=-1;
    u32 fraction=raw&7;
    if(fraction==0 || fraction==3 || fraction==5)index=(raw/8)*3+(fraction==3?1:fraction==5?2:0);
    if(field==0) {
        static const u32 iso[]={25,32,40,50,64,80,100,125,160,200,250,320,400,500,640,800,1000,1250,1600,2000,2500,3200,4000,5000,6400,8000,10000,12800,16000,20000,25600,32000,40000,51200,64000,80000,102400};
        index-=21;
        if(index>=0 && index<(int)(sizeof(iso)/sizeof(iso[0]))) {camera_number(buf,iso[index]);return;}
    }
    if(field==1) {
        static const char *const f[]={"1.0","1.1","1.2","1.4","1.6","1.8","2.0","2.2","2.5","2.8","3.2","3.5","4.0","4.5","5.0","5.6","6.3","7.1","8.0","9.0","10","11","13","14","16","18","20","22","25","29","32"};
        index-=3;
        if(index>=0 && index<(int)(sizeof(f)/sizeof(f[0]))) {camera_text(buf,f[index]);return;}
    }
    if(field==2) {
        /* Canon Tv codes: full-stop, third-stop and half-stop aliases.
         * Canon Tv baseline; hot-shoe 0x74=1/200 calibrated by device owner.
         * Unknown stays hex; do not shift neighboring codes. */
        static const u8 codes[]={0x00,0x04,0x0c,0x10,0x13,0x14,0x15,0x18,0x1b,0x1c,0x1d,0x20,0x23,0x24,0x25,0x28,0x2b,0x2c,0x2d,0x30,0x33,0x34,0x35,0x38,0x3b,0x3c,0x3d,0x40,0x43,0x44,0x45,0x48,0x4b,0x4c,0x4d,0x50,0x53,0x54,0x55,0x58,0x5b,0x5c,0x5d,0x60,0x63,0x64,0x65,0x68,0x6b,0x6c,0x6d,0x70,0x73,0x74,0x75,0x77,0x78,0x7b,0x7c,0x7d,0x80,0x83,0x84,0x85,0x88,0x8b,0x8c,0x8d,0x90,0x93,0x94,0x95,0x98,0x9b,0x9c,0x9d,0xa0,0xa8};
        static const char *const times[]={"AUTO","BULB","BULB","30s","25s","20s","20s","15s","13s","10s","10s","8s","6s","6s","5s","4s","3.2s","3s","2.5s","2s","1.6s","1.5s","1.3s","1s","0.8s","0.7s","0.6s","0.5s","0.4s","0.3s","0.3s","1/4","1/5","1/6","1/6","1/8","1/10","1/10","1/13","1/15","1/20","1/20","1/25","1/30","1/40","1/45","1/50","1/60","1/80","1/90","1/100","1/125","1/160","1/200","1/200","1/250","1/250","1/320","1/350","1/400","1/500","1/640","1/750","1/800","1/1000","1/1250","1/1500","1/1600","1/2000","1/2500","1/3000","1/3200","1/4000","1/5000","1/6000","1/6400","1/8000","1/16000"};
        for(u32 i=0;i<sizeof(codes);i++)if(raw==codes[i]) {camera_text(buf,times[i]);return;}
    }
    static const char hex[]="0123456789ABCDEF";
    buf[0]='0';buf[1]='x';buf[2]=hex[(raw>>4)&15];buf[3]=hex[raw&15];buf[4]=0;
}
static u32 camera_link_state(void) {
    /* Same predicate as the stock camera glyph, 08038448..080384DA.
     * 64 alone is readiness, not a complete connection indication. */
    return !BYTE(0x2000005au) && BYTE(0x20000064u) && !BYTE(0x20000027u);
}
static void camera_update(Drawer *d) {
    u8 values[4];u32 seen,revision,irq=irq_get();irq_disable();
    for(u32 i=0;i<4;i++)values[i]=d->camera_values[i];
    seen=d->seen;revision=d->revision;irq_restore(irq);
    u32 repainted=0,connected=camera_link_state();
    if(d->shown_seen!=connected) {
        COLOR(d->camera_status,connected?0x07e0:0x7bef,0);
        if(connected)FN(0x0802da22,void,(void*,u32))(d->camera_link_slash,1);
        else FN(0x0802e2d2,void,(void*,u32))(d->camera_link_slash,1);
        d->shown_seen=connected;repainted=1;
    }
    for(u32 i=0;i<3;i++) {
        char text[24];camera_format(i,values[i],seen,text);
        u32 same=1,j=0;
        do {if(text[j]!=d->shown[i][j]) {same=0;break;}}while(text[j++]);
        if(!same) {
            repainted=1;
            const char *value=text;
            if(i==2) {
                u32 fraction=text[0]=='1' && text[1]=='/';
                if(!d->shown[2][0] || fraction!=(d->shown[2][0]=='1' && d->shown[2][1]=='/'))
                    TEXT(d->camera_shutter_prefix,fraction?"1/":"");
                if(fraction)value+=2;
            }
            u32 font=camera_value_font(i,value);
            if(font!=d->camera_value_fonts[i]) {
                FONT(d->camera_labels[i],font,0);d->camera_value_fonts[i]=font;
            }
            TEXT(d->camera_labels[i],value);
            u32 j=0;do {d->shown[i][j]=text[j];}while(text[j++]);
        }
    }
    if(repainted) {
        /* Rendering may run before this timer in the current LVGL pass.
         * Keep the native loop awake for the following refresh as well. */
        camera_request_ui();
        /* Commit the complete text/font snapshot once in this UI callback;
         * no receive-path rendering and no refresh for unchanged packets. */
        FN(0x08017768,void,(void*))(0);
    }
    d->painted_revision=revision;
}
static void camera_open(void) {
    State *s=bank_find_state();
    Drawer *d=drawer_context(s,1);if(!d || d->root)return;
    if(s->panel && VALID((void*)s->panel))FN(0x0802e428,void,(void*))((void*)s->panel);
    s->panel=0;HEAD(s,9)=HEAD(s,10)=HEAD(s,11)=HEAD(s,12)=0;
    if(!d->camera_font_bitmap)d->camera_font_bitmap=FN(0x0802d5c4,u8*,(u32))(2560);
    if(!d->camera_font_bitmap)return;
    camera_consume_touch();
    d->kind=1;d->closing=0;d->shown_seen=~0u;d->camlcd_auto=0;
    d->root=drawer_box(FN(0x0803205a,void*,(void))(),-368,0,368,448,0,0,1);
    if(!d->root)return;
    FN(0x0802da22,void,(void*,u32))(d->root,0x60000);
    FN(0x0802e2d2,void,(void*,u32))(d->root,0x8000);
    EVENT(d->root,drawer_event,12,d);EVENT(d->root,drawer_event,33,d);
    d->camera_status=LABEL(d->root);
    FONT(d->camera_status,0x0806e3a0,0);TEXT(d->camera_status,"\xee\xa4\x80");
    POS(d->camera_status,323,9);
    d->camera_link_slash=LABEL(d->root);
    FONT(d->camera_link_slash,0x0804bbe0,0);COLOR(d->camera_link_slash,0xf800,0);
    TEXT(d->camera_link_slash,"/");POS(d->camera_link_slash,331,7);
    /* One value per row: aperture, shutter, then ISO. */
    static const i32 y[]={280,88,184};
    for(u32 i=0;i<3;i++) {
        void *row=drawer_box(d->root,16,y[i],336,92,0,0,0);
        void *name=LABEL(row);FONT(name,0x0805c9f4,0);COLOR(name,0xffff,0);
        TEXT(name,i==0?"ISO":i==1?"F/":"1/");ALIGN(name,3,-248,3);
        if(i==2)d->camera_shutter_prefix=name;
        void *value=LABEL(row);d->camera_labels[i]=value;
        FONT(value,0x0805c9f4,0);COLOR(value,0xffff,0);
        POS(value,96,0);
        d->shown[i][0]=0;d->camera_value_fonts[i]=0;
    }
    d->previous_group=(void*)WORD(WORD(0x200003d0u)+0x80);
    FN(0x0802b798,void,(void*))(d->group);
    FN(0x0802c912,void,(void*,void*))((void*)WORD(0x200003d0u),d->group);
    camera_update(d);drawer_animate(d->root,-368,0,0);
}
static void camera_edge_event(u8 *e) {
    Drawer *d=(Drawer*)*(u32*)(e+12);if(!d)return;
    if(e[8]==33) {d->camera_edge=0;d->camera_edge_parent=0;return;}
    if(e[8]==1) {
        i32 point[2];
        void *indev=FN(0x0802c5fc,void*,(void))();
        FN(0x0802c634,void,(void*,i32*))(indev,point);
        d->camera_swipe_armed=point[0]>=0 && point[0]<16 && point[1]>=40;
        if(!d->camera_swipe_armed)return;
        void *overview=(void*)WORD(0x20000430u);
        if(overview && VALID(overview)) {
            d->camera_pager=FN(0x0802ee0a,void*,(void*))(overview);
            if(d->camera_pager) {
                d->camera_pager_scrollable=FN(0x0802fc9e,u32,(void*,u32))(d->camera_pager,0x10);
                FN(0x0802e2d2,void,(void*,u32))(d->camera_pager,0x10);
            }
        }
    }
    if((e[8]==8 || e[8]==3) && !d->root && d->camera_pager) {
        if(d->camera_pager_scrollable)FN(0x0802da22,void,(void*,u32))(d->camera_pager,0x10);
        d->camera_pager=0;
    }
    if(e[8]==12 && d->camera_swipe_armed && drawer_direction()==2 && !d->root)camera_open();
}
static void camera_edge_update(Drawer *d) {
    void *screen=FN(0x0803205a,void*,(void))();
    u32 main=!BYTE(0x200003e7u) && !BYTE(0x200003e4u);
    if(d->camera_edge && d->camera_edge_parent!=screen) {
        if(VALID(d->camera_edge))FN(0x0802e428,void,(void*))(d->camera_edge);
        d->camera_edge=0;d->camera_edge_parent=0;
    }
    if(!d->camera_edge && main && screen) {
        d->camera_edge=drawer_box(screen,0,40,16,408,0,0,1);
        d->camera_edge_parent=screen;
        d->camera_edge_visible=1;
        FN(0x08031594,void,(void*,u32,u32))(d->camera_edge,0,0);
        FN(0x0802da22,void,(void*,u32))(d->camera_edge,0x60000);
        FN(0x0802e2d2,void,(void*,u32))(d->camera_edge,0x8000);
        EVENT(d->camera_edge,camera_edge_event,1,d);
        EVENT(d->camera_edge,camera_edge_event,3,d);
        EVENT(d->camera_edge,camera_edge_event,8,d);
        EVENT(d->camera_edge,camera_edge_event,12,d);
        EVENT(d->camera_edge,camera_edge_event,33,d);
    }
    if(d->camera_edge) {
        u32 visible=main && !d->root;
        if(d->camera_edge_visible!=visible) {
            if(visible)FN(0x0802e2d2,void,(void*,u32))(d->camera_edge,1);
            else FN(0x0802da22,void,(void*,u32))(d->camera_edge,1);
            d->camera_edge_visible=visible;
        }
    }
}
