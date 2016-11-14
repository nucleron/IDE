from ConfigTreeNode import ConfigTreeNode
from YAPLCConfigFile import YAPLConfigFile
import os, sys, shutil


base_folder = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


class YAPLCNodeConfig(YAPLConfigFile):

    def GetIconName(self):
        return "YAPLCConfig"
