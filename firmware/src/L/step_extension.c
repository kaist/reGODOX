/* STEP is a stock global setting, journal byte 0x7b, runtime 0x200003e1.
 * All power/protocol values remain tenths. Only user input uses step indices.
 * No RAM globals, allocation, interrupts, or changes to preset storage. */
typedef unsigned char u8;
typedef unsigned int u32;
#define BYTE(a) (*(volatile u8 *)(a))
#define MODE BYTE(0x200003e1u)
#define MAX BYTE(0x200003e0u)
#define CALL(a,t) ((t)((a)|1u))
extern int step_stock_m(int,int);
extern int step_stock_ttl(int,int);
static int unit(void) { return MODE==2?5:MODE==3?10:1; }
static int clip(int x,int max) { return x<0?0:x>max?max:x; }
static int thirds(int x) { return x/10*3+(x%10>=7?2:x%10>=3?1:0); }
static int from_thirds(int x) { return x/3*10+(x%3==2?7:x%3==1?3:0); }
int step_m(int x,int delta) {
    if(MODE<2) return step_stock_m(x,delta);
    return clip(x-delta*unit(),MAX);
}
int step_ttl(int x,int delta) {
    if(MODE==1) return step_stock_ttl(x,delta);
    return clip(x+delta*unit(),60);
}
void step_ttl_encoder(volatile u8 *group,int delta) {
    group[2]=step_ttl(group[2],delta);
}
int step_max(void) { return MODE==1?MAX/10*3:MAX/unit(); }
int step_from_index(int x) {
    return clip(MAX-(MODE==1?from_thirds(x):x*unit()),MAX);
}
int step_to_index(int x) {
    x=clip(MAX-x,MAX);
    return MODE==1?thirds(x):x/unit();
}
int step_ttl_to_index(int x) { return MODE==1?thirds(x):x/unit(); }
int step_ttl_from_index(int x) { return clip(MODE==1?from_thirds(x):x*unit(),60); }
void step_ttl_range(void *obj,int min,int max) {
    (void)min;(void)max;
    CALL(0x080329a8,void (*)(void *,int,int))(obj,0,MODE==1?18:60/unit());
}
int step_ttl_ratio(int pixels_times_index) {
    return pixels_times_index/(MODE==1?18:60/unit());
}
void step_negative_label(char *buf,int x) {
    x=30-x;
    CALL(0x08004c48,int (*)(char *,int,const char *,...))(buf,10,"-%d.%d",x/10,x%10);
}
void step_options(void *obj,const char *old,int mode) {
    (void)old;
    CALL(0x08031dc8,void (*)(void *,const char *,int))(obj,"0.1\n0.3\n0.5\n1.0",mode);
}
void step_event(u8 *event) {
    if(event[8]!=28 || BYTE(0x200004cfu)) return;
    void *obj=*(void **)(event+4);
    u32 selected=CALL(0x08031d30,u32 (*)(void *))(obj);
    if(selected>3)return;
    MODE=selected;
    /* Match the stock downward quantization when changing the step. */
    volatile u8 *g=(volatile u8 *)0x20000b68u;
    for(int i=0;i<16;i++,g+=6) {
        g[1]=selected==1?from_thirds(thirds(g[1])):g[1]/unit()*unit();
        g[2]=selected==1?from_thirds(thirds(g[2])):g[2]/unit()*unit();
    }
}
void step_margins(short *up,short *down) {
    volatile u8 *g=(volatile u8 *)0x20000b68u;
    int first=1,a=0,b=0;
    for(int i=0;i<16;i++,g+=6) {
        if((g[3]>>6)!=3 || g[0]>1)continue;
        int x=g[g[0]==0?1:2];
        int hi=g[0]==0?MAX-x:x;
        int lo=g[0]==0?x:60-x;
        int h=MODE==1?thirds(hi):hi/unit();
        int l=MODE==1?thirds(lo):lo/unit();
        if(first||h<a)a=h;
        if(first||l<b)b=l;
        first=0;
    }
    *up=a;*down=b;
}
int step_is_thirds(void) { return MODE==1; }
int step_overlay_value(int x) { return x*unit(); }
