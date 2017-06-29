import os, sys
from yaplctargets.toolchain_yaplc_stm32 import toolchain_yaplc_stm32
from yaplctargets.toolchain_yaplc_stm32 import plc_rt_dir as plc_rt_dir

class nuc247_target(toolchain_yaplc_stm32):
    def __init__(self, CTRInstance):
        
        toolchain_yaplc_stm32.__init__(self, CTRInstance)
        
        self.dev_family       = "STM32F2"
        self.load_addr        = "0x08008000"
        self.runtime_addr     = "0x08000184"
        self.linker_script    = os.path.join(os.path.join(os.path.join(plc_rt_dir, "bsp"), "nuc-247-0"), "stm32f205xC-app.ld")
