import os, sys, shutil
from ..toolchain_yaplc import toolchain_yaplc

target_load_addr    = "0x08010000"
target_runtime_addr = "0x08000184"

target_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.join(os.path.join(os.path.join(target_dir, ".."), ".."), "..")


class yaplcF2k64_target(toolchain_yaplc):
    def __init__(self, CTRInstance):
        toolchain_yaplc.__init__(self, CTRInstance)

        #Needed for plc_main.c
        plc_rt_dir = os.path.join(os.path.join(base_dir, "RTE"), "src")
        
        self.cflags.append("-I\"" + plc_rt_dir + "\"")
        self.cflags.append("-DPLC_RTE_ADDR=" + target_runtime_addr)
        
        #Add linker script to ldflags
        plc_linker_script = os.path.join(plc_rt_dir, "bsp/nuc-243/stm32f205xC-app.ld")
        
        #Target specific build options
        self.target_options.append("LDFLAGS=-Wl,-script=\""+plc_linker_script+"\" ")
        self.target_options.append("OUTPUT="+self.exe)
        self.target_options.append("LOADADDR="+target_load_addr)
        
    def build(self):
        #Copy make file
        shutil.copy(os.path.join(target_dir, "Makefile"), os.path.join(self.buildpath, "Makefile"))
        #Build project
        return toolchain_yaplc.build(self)

    def GetBinaryCode(self):
        yaplc_boot_loader = os.path.join(os.path.join(base_dir, "stm32flash"), "stm32flash")
        
        command = [yaplc_boot_loader, "-w", toolchain_yaplc.GetBinaryCode(self) + ".hex", "-v", "-g", "0x0", "-S",
                   target_load_addr, "%(serial_port)s"]
        #
        return command
