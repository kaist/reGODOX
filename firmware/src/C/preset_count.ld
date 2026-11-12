SECTIONS { . = 0x080f0800;
 .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) *(.comment*) } }
count_stock_focus = 0x080f0601;
drawer_stock_main_event = 0x080f06c1;
camlcd_stock_touch = 0x080f06d1;
camlcd_stock_encoder = 0x080f06e1;
ASSERT(SIZEOF(.data)==0,"data unsupported")
ASSERT(SIZEOF(.bss)==0,"bss unsupported")
