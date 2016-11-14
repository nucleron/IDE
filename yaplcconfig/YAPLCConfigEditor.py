import wx
from editors.ConfTreeNodeEditor import ConfTreeNodeEditor
from editors.CodeFileEditor import VariablesEditor
from controls.VariablePanel import VariablePanel
from PLCControler import LOCATION_CONFNODE, LOCATION_MODULE, LOCATION_GROUP, LOCATION_VAR_INPUT, LOCATION_VAR_OUTPUT, \
    LOCATION_VAR_MEMORY

[ID_YAPLCCONFIGEDITOR,
 ] = [wx.NewId() for _init_ctrls in range(1)]


class YAPLCConfigEditor(ConfTreeNodeEditor):
    ID = ID_YAPLCCONFIGEDITOR

    CODE_EDITOR = None

    CONFNODEEDITOR_TABS = [
        (_("YAPLC Config"), "_create_YAPLCConfigEditor")]

    def _create_YAPLCConfigEditor(self, prnt):
        self.ConfigEditor = wx.SplitterWindow(prnt)
        self.ConfigEditor.SetMinimumPaneSize(1)

        self.VariablesPanel = VariablesEditor(self.ConfigEditor,
                                              self.ParentWindow, self.Controler)

        if self.CODE_EDITOR is not None:
            self.CodeEditor = self.CODE_EDITOR(self.ConfigEditor,
                                               self.ParentWindow, self.Controler)

            self.ConfigEditor.SplitHorizontally(self.VariablesPanel,
                                                self.CodeEditor, 150)
        else:
            self.ConfigEditor.Initialize(self.VariablesPanel)

        return self.ConfigEditor

    def __init__(self, parent, controler, window):
        ConfTreeNodeEditor.__init__(self, parent, controler, window)

        wx.CallAfter(self.ConfigEditor.SetSashPosition, 150)

    def GetBufferState(self):
        return self.Controler.GetBufferState()

    def Undo(self):
        self.Controler.LoadPrevious()
        self.RefreshView()

    def Redo(self):
        self.Controler.LoadNext()
        self.RefreshView()

    def RefreshView(self):
        ConfTreeNodeEditor.RefreshView(self)

        self.VariablesPanel.RefreshView()

    def Find(self, direction, search_params):
        pass
