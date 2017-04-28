import os, sys
from yaplctargets.toolchain_yaplc2 import toolchain_yaplc2

target_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.join(os.path.join(os.path.join(target_dir, ".."), ".."), "..")
plc_rt_dir = os.path.join(os.path.join(base_dir, "RTE"), "src")

class yaplc_target(toolchain_yaplc2):
    def __init__(self, CTRInstance):
        
        toolchain_yaplc2.__init__(self, CTRInstance)
        
        self.dev_family       = "STM32F4"
        self.load_addr        = "0x08008000"
        self.runtime_addr     = "0x080001ac"
        self.base_flags       = ["-mthumb", "-mcpu=cortex-m4", "-mfpu=fpv4-sp-d16", "-mfloat-abi=hard", 
                                 "-O0", "-g3", "-DARM_MATH_CM4", "-D__FPU_USED"]
        self.toolchain_prefix = "arm-none-eabi-"
        self.linker_script    = os.path.join(os.path.join(os.path.join(plc_rt_dir, "bsp"), "nuc-227-dev"), "stm32f4disco-app.ld")
               
    def GetBinaryCode(self):
        if os.path.exists(self.exe_path):
            yaplc_boot_loader = os.path.join(os.path.join(base_dir, "stm32flash"), "stm32flash")
            command = [yaplc_boot_loader, "-w", self.exe_path + ".hex", "-v", "-g", "0x0", "-S", self.load_addr, "%(serial_port)s"]
            return command
        else:
	    return None
