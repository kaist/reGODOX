SECTIONS { . = 0x080ef100; .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) *(.comment*) } }
step_stock_m = 0x080ef001;
step_stock_ttl = 0x080ef009;
ASSERT(SIZEOF(.data)==0,"data unsupported")
ASSERT(SIZEOF(.bss)==0,"bss unsupported")
