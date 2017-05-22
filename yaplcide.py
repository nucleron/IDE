#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = "$Revision$"

import __builtin__
import gettext
import os
import sys

gettext.install('yaplcide')  # this is a dummy to prevent gettext falling down

_dist_folder = os.path.split(sys.path[0])[0]
_beremiz_folder = os.path.join(_dist_folder, "beremiz")
#Ensure that Beremiz things are imported before builtins and libs.
sys.path.insert(1,_beremiz_folder)

from Beremiz import *

class YAPLCIdeLauncher(BeremizIDELauncher):
    """
    YAPLC IDE Launcher class
    """
    def __init__(self):
        BeremizIDELauncher.__init__(self)
        self.yaplc_dir = os.path.dirname(os.path.realpath(__file__))
        self.splashPath = self.YApath("images", "splash.png")
        self.extensions.append(self.YApath("yaplcext.py"))

        import features
        # Let's import nucleron yaplcconnectors
        import yaplcconnectors
        import connectors

        connectors.connectors.update(yaplcconnectors.connectors)

        # Import Nucleron yaplctargets
        import yaplctargets
        import targets

        targets.toolchains.update(yaplctargets.toolchains)
        targets.targets.update(yaplctargets.yaplctargets)

        features.libraries = [
	    ('Native', 'NativeLib.NativeLibrary')]
        
        features.catalog.append(('yaplcconfig',
                                 _('YAPLC Configuration Node'),
                                 _('Adds template located variables'),
                                 'yaplcconfig.yaplcconfig.YAPLCNodeConfig'))

    def YApath(self, *args):
        return os.path.join(self.yaplc_dir, *args)


# This is where we start our application
if __name__ == '__main__':
    beremiz = YAPLCIdeLauncher()
    beremiz.Start()
