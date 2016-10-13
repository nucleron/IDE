#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = "$Revision$"

import __builtin__
import getopt
import gettext
import os
import sys

import wx

gettext.install('nucleron')  # this is a dummy to prevent gettext falling down

_dist_folder = os.path.split(sys.path[0])[0]
_beremiz_folder = os.path.join(_dist_folder, "beremiz")
sys.path.append(_beremiz_folder)


def Bpath(*args):
    return os.path.join(CWD, *args)


if __name__ == '__main__':

    def usage():
        print "\nUsage of Beremiz.py :"
        print "\n   %s [Projectpath] [Buildpath]\n"%sys.argv[0]

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hu:e:", ["help", "updatecheck=", "extend="])
    except getopt.GetoptError:
        # print help information and exit:
        usage()
        sys.exit(2)

    extensions=[]

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        if o in ("-u", "--updatecheck"):
            updateinfo_url = a
        if o in ("-e", "--extend"):
            extensions.append(a)

    if len(args) > 2:
        usage()
        sys.exit()
    elif len(args) == 1:
        projectOpen = args[0]
        buildpath = None
    elif len(args) == 2:
        projectOpen = args[0]
        buildpath = args[1]
    else:
        projectOpen = None
        buildpath = None

    if os.path.exists("BEREMIZ_DEBUG"):
        __builtin__.__dict__["BMZ_DBG"] = True
    else:
        __builtin__.__dict__["BMZ_DBG"] = False

    if wx.VERSION >= (3, 0, 0):
        app = wx.App(redirect=BMZ_DBG)
    else:
        app = wx.PySimpleApp(redirect=BMZ_DBG)

    # this would run a new application with window (Beremiz)
    app.SetAppName('beremiz')
    if wx.VERSION < (3, 0, 0):
        wx.InitAllImageHandlers()

    from util.misc import InstallLocalRessources

    InstallLocalRessources(_beremiz_folder)


# This part implements some methods and functions to Beremiz
_nucmanager_path = os.path.split(__file__)[0]
import features


features.libraries = [
    ('Native', 'NativeLib.NativeLibrary')]


# Let's import nucleron yaplcconnectors
import yaplcconnectors
import connectors

connectors.connectors.update(yaplcconnectors.connectors)

# from yaplcconnectors.YAPLCConnector import YAPLC_connector_factory
#
# yaplcconnectors.yaplcconnectors["YAPLC"] = lambda: YAPLC_connector_factory

# Import Nucleron yaplctargets
import yaplctargets
import targets

targets.toolchains.update(yaplctargets.toolchains)
targets.targets.update(yaplctargets.yaplctargets)

# from yaplctargets.YAPLCtarget import YAPLC_target
#
# yaplctargets.yaplctargets["YAPLC"] = {"xsd": os.path.join(_nucmanager_path, "YAPLCtarget", "XSD"),
#                             "class": lambda: YAPLC_target,
#                             "code": os.path.join(_nucmanager_path, "YAPLCtarget", "plc_yaplc_main.c")}
# yaplctargets.toolchains["yaplc"] = os.path.join(_nucmanager_path, "YAPLCtarget", "XSD_toolchain_makefile")

from Beremiz import *

# Ready to show default splash screen
splash = ShowSplashScreen()

havecanfestival = False
try:
    from canfestival import RootClass as CanOpenRootClass
    from canfestival.canfestival import _SlaveCTN, _NodeListCTN, NodeManager
    from canfestival.NetworkEditor import NetworkEditor
    from canfestival.SlaveEditor import SlaveEditor

    havecanfestival = True
except:
    havecanfestival = False


# -------------------------------------------------------------------------------
#                              YAPLCProjectController Class
# -------------------------------------------------------------------------------

def mycopytree(src, dst):
    """
    Copy content of a directory to an other, omit hidden files
    @param src: source directory
    @param dst: destination directory
    """
    for i in os.listdir(src):
        if not i.startswith('.'):
            srcpath = os.path.join(src, i)
            dstpath = os.path.join(dst, i)
            if os.path.isdir(srcpath):
                if os.path.exists(dstpath):
                    shutil.rmtree(dstpath)
                os.makedirs(dstpath)
                mycopytree(srcpath, dstpath)
            elif os.path.isfile(srcpath):
                shutil.copy2(srcpath, dstpath)


[SIMULATION_MODE, TRANSFER_MODE] = range(2)


# This is where we start our application
if __name__ == '__main__':

    from threading import Thread, Timer, Semaphore

    wx_eval_lock = Semaphore(0)
    eval_res = None


    def wx_evaluator(callable, *args, **kwargs):
        global eval_res
        eval_res = None
        try:
            eval_res = callable(*args, **kwargs)
        finally:
            wx_eval_lock.release()


    def evaluator(callable, *args, **kwargs):
        global eval_res
        wx.CallAfter(wx_evaluator, callable, *args, **kwargs)
        wx_eval_lock.acquire()
        return eval_res


    # Command log for debug, for viewing from wxInspector
    if BMZ_DBG:
        __builtins__.cmdlog = []

    if projectOpen is not None:
        projectOpen = DecodeFileSystemPath(projectOpen, False)


    # Install a exception handle for bug reports
    AddExceptHook(os.getcwd(), __version__)

    frame = Beremiz(None, projectOpen, buildpath)
    if splash:
        splash.Close()

    frame.Show()
    app.MainLoop()
