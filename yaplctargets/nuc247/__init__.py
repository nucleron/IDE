import os, sys
from yaplctargets.toolchain_yaplc_stm32 import toolchain_yaplc_stm32

target_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.join(os.path.join(os.path.join(target_dir, ".."), ".."), "..")
plc_rt_dir = os.path.join(os.path.join(base_dir, "RTE"), "src")

class nuc247_target(toolchain_yaplc_stm32):
    def __init__(self, CTRInstance):
        
        toolchain_yaplc_stm32.__init__(self, CTRInstance)
        
        self.dev_family       = "STM32F2"
        self.load_addr        = "0x08008000"
        self.runtime_addr     = "0x08000184"
        self.base_flags       = ["-mthumb", "-mcpu=cortex-m3", "-O0", "-g3"]
        self.toolchain_prefix = "arm-none-eabi-"
        self.linker_script    = os.path.join(os.path.join(os.path.join(plc_rt_dir, "bsp"), "nuc-247-0"), "stm32f205xC-app.ld")