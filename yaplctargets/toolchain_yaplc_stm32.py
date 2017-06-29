import os, sys
from toolchain_yaplc import toolchain_yaplc
from toolchain_yaplc import plc_rt_dir as plc_rt_dir

toolchain_dir  = os.path.dirname(os.path.realpath(__file__))
base_dir       = os.path.join(os.path.join(toolchain_dir, ".."), "..")

class toolchain_yaplc_stm32(toolchain_yaplc):
    
    def GetBinaryCode(self):
        if os.path.exists(self.exe_path):
            yaplc_boot_loader = os.path.join(os.path.join(base_dir, "stm32flash"), "stm32flash")
            if (os.name == 'posix' and not os.path.isfile(yaplc_boot_loader)):
                yaplc_boot_loader = "stm32flash"
            command = [yaplc_boot_loader, "-w", self.exe_path + ".hex", "-v", "-g", "0x0", "-S", self.load_addr, "%(serial_port)s"]
            return command
        else:
	    return None
