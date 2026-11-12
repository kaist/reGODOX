/* Freestanding Cortex-M4 code. Every mutable object lives in the allocated
 * timer context; there are no new fixed RAM globals or startup sections. */
#include "popup_v5_addresses.h"
typedef unsigned char u8;
typedef unsigned int u32;
typedef int i32;
typedef struct {
    u32 phase, start, panel, panel_tick, active, initialized;
    u32 indicator, parent, indicator_bank;
    u8 reserved[28];
    u8 banks[4][100];
    u32 latest, sequence, busy, status, reserved_meta;
    u8 buffer[512];
} State;
_Static_assert(sizeof(State)==996,"state size");
_Static_assert(__builtin_offsetof(State,banks)==64,"bank offset");
_Static_assert(__builtin_offsetof(State,buffer)==484,"buffer offset");

#define PAGE_A 0x080f4000u
#define PAGE_B 0x080f5000u
#define MAGIC 0x34424b58u
#define COMMIT 0x5aa5c33cu
#define FN(addr,ret,args) ((ret (*)args)((addr)|1u))
#define CAPTURE FN(ASM_CAPTURE,void,(State*,u32))
#define APPLY FN(ASM_APPLY,void,(State*,u32))
#define WATCHDOG FN(0x0803ba4c,void,(void))
#define UNLOCK FN(0x080218e8,void,(void))
#define LOCK FN(0x080217b0,void,(void))
#define ERASE FN(0x0802182c,u32,(u32))
#define WRITE FN(0x08021a30,u32,(u32,const u8*,u32))
#define STOCK_SAVE FN(ASM_STOCK_SAVE,void,(void))
#define DEFAULTS FN(0x080073f0,void,(void))

static u32 irq_get(void) {u32 x;__asm__ volatile("mrs %0, primask":"=r"(x));return x;}
static void irq_disable(void) {__asm__ volatile("cpsid i":::"memory");}
static void irq_restore(u32 x) {__asm__ volatile("msr primask, %0"::"r"(x):"memory");}
static void copy(u8 *to,const u8 *from,u32 n) {for(u32 i=0;i<n;i++)to[i]=from[i];}
static u32 equal(const u8 *a,const u8 *b,u32 n) {for(u32 i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;}
static u32 word(const u8 *p,u32 at) {return *(const u32 *)(p+at);}
static void put(u8 *p,u32 at,u32 value) {*(u32 *)(p+at)=value;}

__attribute__((used,noinline)) u32 bank_crc(const u8 *p,u32 n) {
    u32 c=~0u;
    for(u32 i=0;i<n;i++) {
        c^=p[i];
        for(u32 j=0;j<8;j++)c=(c>>1)^((0u-(c&1u))&0xedb88320u);
    }
    return ~c;
}
static u32 slot_address(u32 a) {
    return a>=PAGE_A && a<PAGE_B+4096 && (a&511u)==0;
}
__attribute__((used,noinline)) u32 bank_valid(u32 a) {
    if(!slot_address(a))return 0;
    const u8 *p=(const u8*)a;
    if(word(p,0)!=MAGIC || word(p,4)!=2 || word(p,12)!=400 ||
       word(p,16)>3 || (word(p,20)!=~0u && (word(p,20)<2 || word(p,20)>4)) || (word(p,24)!=~0u && word(p,24)>1) || word(p,468)!=COMMIT)return 0;
    if(bank_crc(p,464)!=word(p,464))return 0;
    for(u32 i=0;i<4;i++) {
        const u8 *b=p+64+i*100;
        if(b[96]<1 || b[96]>32 || b[97]>99 || b[98]>1 || b[99]>1)return 0;
        for(u32 j=5;j<96;j+=6)if(b[j]>1)return 0;
    }
    return 1;
}
__attribute__((used,noinline)) u32 bank_latest(void) {
    u32 best=0,sequence=0;
    for(u32 a=PAGE_A;a<PAGE_B+4096;a+=512)if(bank_valid(a)) {
        u32 next=word((const u8*)a,8);
        if(!best || (i32)(next-sequence)>0) {best=a;sequence=next;}
    }
    return best;
}
void camera_context_init(State *s);
static void seed(State *s) {
    s->active=0;s->reserved_meta=260;
    for(u32 i=0;i<4;i++)CAPTURE(s,i);
    s->initialized=1;
}
__attribute__((used,noinline)) void bank_init(State *s) {
    s->busy=0;s->status=0;s->reserved_meta=260;
    ((u32*)s)[13]=0;((u32*)s)[14]=0;((u32*)s)[15]=0;
    s->latest=bank_latest();s->sequence=0;
    if(s->latest) {
        const u8 *p=(const u8*)s->latest;
        s->sequence=word(p,8);s->active=word(p,16);
        u32 count=word(p,20);s->reserved_meta=count>=2 && count<=4?count:4;
        if(s->active>=count)s->active=0; if(word(p,24)==1 || word(p,24)==~0u)s->reserved_meta|=256;
        copy(&s->banks[0][0],p+64,400);
        s->initialized=1;
        APPLY(s,s->active);
    } else seed(s);
    camera_context_init(s);
}
static u32 erased(u32 a) {
    const volatile u32 *p=(const volatile u32*)a;
    for(u32 i=0;i<128;i++)if(p[i]!=~0u)return 0;
    return 1;
}
static u32 program(u32 a,const u8 *b,u32 n) {
    for(u32 i=0;i<n;i+=32) {
        u32 count=n-i;if(count>32)count=32;
        WATCHDOG();
        if(WRITE(a+i,b+i,count)!=1)return 0;
    }
    return equal((const u8*)a,b,n);
}
__attribute__((used,noinline)) u32 bank_flush(State *s) {
    if(!s || !s->initialized || s->active>3 || s->busy)return 0;
    s->busy=1;
    CAPTURE(s,s->active);
    u32 latest=s->latest;
    if(!bank_valid(latest))latest=bank_latest();
    if(latest && word((const u8*)latest,16)==s->active &&
       word((const u8*)latest,20)==(s->reserved_meta&255) && word((const u8*)latest,24)==((s->reserved_meta>>8)&1) &&
       equal((const u8*)latest+64,&s->banks[0][0],400)) {
        s->latest=latest;s->sequence=word((const u8*)latest,8);
        s->busy=0;s->status=1;return 1;
    }
    u32 sequence=latest?word((const u8*)latest,8)+1:1;
    u32 page=latest?(latest&~4095u):PAGE_A;
    u32 target=latest?latest+512:page;
    while(target<page+4096 && !erased(target))target+=512;
    u32 erase_page=0;
    if(target>=page+4096) {
        /* Keep the latest valid record in the other page until commit. */
        page=latest?(page==PAGE_A?PAGE_B:PAGE_A):PAGE_A;
        target=page;erase_page=1;
    }
    if(!slot_address(target) || (erase_page && latest && (latest&~4095u)==page)) {
        s->busy=0;s->status=2;return 0;
    }
    u8 *b=s->buffer;
    for(u32 i=0;i<512;i++)b[i]=255;
    put(b,0,MAGIC);put(b,4,2);put(b,8,sequence);put(b,12,400);put(b,16,s->active);put(b,20,s->reserved_meta&255);put(b,24,(s->reserved_meta>>8)&1);
    copy(b+64,&s->banks[0][0],400);
    put(b,464,bank_crc(b,464));put(b,468,COMMIT);
    WATCHDOG();
    u32 irq=irq_get();irq_disable();UNLOCK();
    u32 ok=1;
    if(erase_page) {
        /* Native driver handles 2 KiB sectors. Reserving 4 KiB and erasing
         * both halves before programming also keeps 4 KiB geometry isolated. */
        ok=ERASE(page)==3;WATCHDOG();
        if(ok)ok=ERASE(page+2048)==3;
        WATCHDOG();
        if(ok)for(u32 a=page;a<page+4096;a+=512)if(!erased(a))ok=0;
    }
    if(ok)ok=program(target,b,468);   /* payload + CRC, without commit */
    if(ok)ok=program(target+468,b+468,4); /* commit written last */
    if(ok)ok=bank_valid(target);
    LOCK();irq_restore(irq);WATCHDOG();
    if(ok) {s->latest=target;s->sequence=sequence;}
    s->busy=0;s->status=ok?1:2;
    return ok;
}
__attribute__((used,noinline)) State *bank_find_state(void) {
    u32 *list=(u32*)0x200011a8;
    u32 *node=(u32*)list[1];
    for(u32 count=0;node && count<256;count++) {
        if(node[2]==(ASM_CALLBACK|1u))return (State*)node[3];
        /* LVGL linked list: data size, then next pointer after data+4. */
        node=*(u32**)((u8*)node+list[0]+4);
    }
    return (State*)0;
}
__attribute__((used,noinline)) void bank_save_hook(void) {
    u32 irq=irq_get();
    State *s=bank_find_state();if(s)bank_flush(s);
    STOCK_SAVE();
    irq_restore(irq);
}
__attribute__((used,noinline)) void bank_reset_hook(void) {
    DEFAULTS();
    State *s=bank_find_state();
    if(s) {seed(s);bank_flush(s);}
}

#define ASM_REFRESH 0x080ed9deu

#define ASM_INDICATOR 0x080eda18u

#define CAMERA_SHEET 1

#define PRESET_DRAWER 1

#include "preset_count_ui.c"

#include "preset_drawer.c"
