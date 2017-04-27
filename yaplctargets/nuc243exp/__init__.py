import os, sys, shutil
from util.ProcessLogger import ProcessLogger
from yaplctargets.toolchain_gcc import toolchain_gcc_base

target_load_addr    = "0x08008000"
target_runtime_addr = "0x08000184"        
toolchain_prefix = "arm-none-eabi-"

target_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.join(os.path.join(os.path.join(target_dir, ".."), ".."), "..")
plc_rt_dir = os.path.join(os.path.join(base_dir, "RTE"), "src")

class nuc243exp_target(toolchain_gcc_base):
    def __init__(self, CTRInstance):
        self.extension = ".elf"
        toolchain_gcc_base.__init__(self, CTRInstance)

    def getBuilderCFLAGS(self):
        """
        Returns list of builder specific CFLAGS
        """
        flags = ["-mthumb", "-mcpu=cortex-m3", "-O0", "-g3", "-std=gnu90", "-Wall", 
                 "-fdata-sections", "-ffunction-sections", "-fno-strict-aliasing",
                 "-DSTM32F2"] 
        flags += ["-I\"" + plc_rt_dir + "\""]
        flags += ["-DPLC_RTE_ADDR=" + target_runtime_addr]
        flags += self.cflags
        return flags

    def getBuilderLDFLAGS(self):
        """
        Returns list of builder specific LDFLAGS
        """
        plc_linker_script = os.path.join(plc_rt_dir, "bsp/nuc-243/stm32f205xC-app.ld")
        
        flags = ["-mthumb", "-mcpu=cortex-m3", "-O0", "-g3", "-Xlinker"] 
        flags += ["-T \"" + plc_linker_script + "\""]
        flags += ["-Wl,--gc-sections", "-nostartfiles"]
        flags += ["-Wl,-Map=" + self.exe_path + ".map"]
        return flags

    def getCompiler(self):
        """
        Returns compiler
        """
        return toolchain_prefix + "gcc"
      
    def getLinker(self):
        """
        Returns linker
        """
        return toolchain_prefix + "g++"
               
    def GetBinaryCode(self):
        yaplc_boot_loader = os.path.join(os.path.join(base_dir, "stm32flash"), "stm32flash")

        command = [yaplc_boot_loader, "-w", self.exe_path + ".hex", "-v", "-g", "0x0", "-S", target_load_addr, "%(serial_port)s"]

        return command

    def build(self):
      
        #Build project
        self.cflags = ["-DPLC_MD5=" + toolchain_gcc_base.calc_md5(self)]
        
        if toolchain_gcc_base.build(self):
	    #Run objcopy on success
	    self.CTRInstance.logger.write("   [OBJCOPY]  " + self.exe +" -> " + self.exe + ".hex\n")
	    
	    objcpy = [toolchain_prefix + "objcopy", "--change-address", target_load_addr,  "-O", "ihex", self.exe_path, self.exe_path + ".hex"]
	    ProcessLogger( self.CTRInstance.logger, objcpy).spin()
            
            return True
        
        return False
