#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of Beremiz, a Integrated Development Environment for
# programming IEC 61131-3 automates supporting plcopen standard and CanFestival.
#
# Copyright (C) 2007: Edouard TISSERANT and Laurent BESSARD
#
# See COPYING file for copyrights details.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


import os
import re
import wx

from copy import deepcopy
from lxml import etree
from xmlclass import GenerateParserFromXSDstring
from PLCControler import UndoBuffer
from ConfigTreeNode import XSDSchemaErrorMessage
from CodeFileTreeNode import CodeFile
from YAPLCConfigEditor import YAPLCConfigEditor
from yaplcparser import YAPLCConfigParser
from PLCControler import LOCATION_CONFNODE, LOCATION_VAR_INPUT, LOCATION_VAR_OUTPUT, LOCATION_VAR_MEMORY, LOCATION_GROUP
from yaplcparser import ParseError
from editors.ConfTreeNodeEditor import ConfTreeNodeEditor
import shutil


def Warn(parent, message, caption = 'Warning!'):
    dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_WARNING)
    dlg.ShowModal()
    dlg.Destroy()


class YAPLCTLocation(object):
    """
    Represents a location with named parameters
    """
    XSD = ""

    EditorType = ConfTreeNodeEditor

    IconFileName = "YAPLCPlainLocation"

    def __init__(self):
        pass

    def GetVariableLocationTree(self):
        current_location = self.GetCurrentLocation()

        return {"name": self.BaseParams.getName(),
                "type": LOCATION_CONFNODE,
                "location": "",
                "children": []
                }

    def GetIconName(self):
        return self.IconFileName


"""
Represents locations group with named parameters specified by the user
"""
XSD_LOCATIONS_GROUP = """<?xml version="1.0" encoding="ISO-8859-1" ?>
    <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
      <xsd:element name="%(name)s">
        <xsd:complexType>
            %(attributes)s
        </xsd:complexType>
      </xsd:element>
    </xsd:schema>
    """

LOC_SECTION_TAG_ELEMENT = "<xsd:attribute name=\"%s\" type=\"%s\" %s/>"
LOC_SECTION_RESTRICTION_TAG_ELEMENT = """<xsd:attribute name="%(name)s" %(opt)s>
                <xsd:simpleType>
                    <xsd:restriction base="xsd:integer">
                        <xsd:minInclusive value="%(min)s"/>
                        <xsd:maxInclusive value="%(max)s"/>
                    </xsd:restriction>
                </xsd:simpleType>
            </xsd:attribute>\n"""


def CreateLocationClass(name, base, node):
    if node.parametrized():
        params = ''
        for p in node.parameters().values():
            if len(p['values']) > 1:
                params += LOC_SECTION_RESTRICTION_TAG_ELEMENT % ({'name': p['name'],
                                                                  'opt': 'use="required"',
                                                                  'min': p['values'][0],
                                                                  'max': p['values'][-1]
                                                                  }
                                                                 )
            else:
                params += LOC_SECTION_TAG_ELEMENT % (p['name'], 'xsd:integer', 'use="required"')

        attributes = {
                      'name': str(base.__name__),
                      'attributes': params
                      }

        xsd = XSD_LOCATIONS_GROUP % attributes
        newNode = type(str(base.__name__) + str(name) + node.name(), (base,), {'XSD': xsd, })
        setattr(newNode, 'IconFileName', 'YAPLCConfigurableLocation')
    else:
        newNode = None

    return newNode


def CreateLocationsGroupClass(name, base, node):

    if node is not None and node.parametrized():
        groupName = node.group()['name']
        if len(node.group()['values']) > 1:
            params = LOC_SECTION_RESTRICTION_TAG_ELEMENT % ({'name': groupName,
                                                             'opt': 'use="required"',
                                                             'min': node.group()['values'][0],
                                                             'max': node.group()['values'][-1]
                                                             }
                                                            )
            attributes = {'name': str(base.__name__),
                          'attributes': params
                          }
        else:
            attributes = {'name': str(base.__name__),
                          'attributes': LOC_SECTION_TAG_ELEMENT % (groupName, 'xsd:integer', 'use="required"')}

        xsd = XSD_LOCATIONS_GROUP % attributes
        NewGroup = type(str(base.__name__) + str(name) + node.name(), (base,), {'XSD': xsd, })
    else:
        NewGroup = base
        setattr(NewGroup, 'XSD', None)

    return NewGroup


class YAPLCTLocationsGroup(object):
    EditorType = ConfTreeNodeEditor

    XSD = None

    def __init__(self):

        """
        We are have to use different children for nodes
        """
        self.CTNChildrenTypes = []
        name = self.CTNType

        parser = getattr(self.CTNParent, 'YAPLCParser', None)
        if parser is not None:
            self.YAPLCParser = parser

        # let's parse some staff
        group = parser.getgroup(name)

        if group is None:
            raise ParseError("Group %s is None" % name)

        # fill with groups
        for sg in group.children():
            groupClass = CreateLocationsGroupClass(name, YAPLCTLocationsGroup, sg)
            grp = (sg.name(), groupClass, sg.name())
            if grp not in self.CTNChildrenTypes:
                self.CTNChildrenTypes.append(grp)

        # fill with locations
        for loc in group.locations():
            if loc.parametrized():
                locClass = CreateLocationClass(name, YAPLCTLocation, loc)
                ll = (loc.name(), locClass, loc.name())
                if ll not in self.CTNChildrenTypes:
                    self.CTNChildrenTypes.append(ll)

    def GetIconName(self):
        return "YAPLCGroup"


class YAPLConfigFile(CodeFile):
    """
    YAPLC Template Configuration file representation class
    Creates instance of root YAPLC node and nested child nodes, that represents groups and locations.
    """
    # XSD = """<?xml version="1.0" encoding="ISO-8859-1" ?>
    # <xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    #   <xsd:element name="YAPLCExtension" type="xsd:anyType" />
    # </xsd:schema>
    # """

    CODEFILE_NAME = "YAPLCFile"
    SECTIONS_NAMES = ["globals",
                      "locations"
                      ]

    EditorType = YAPLCConfigEditor

    """
    IEC Types mappings to internal types of YAPLC
    """
    IECTypes = {'X': 'BOOL',
                'B': 'BYTE',
                'W': 'WORD',
                'D': 'DWORD',
                'L': 'LWORD',
                'S': 'STRING'
                }

    """
    YAPLC Types size conversions
    """
    SizeConversion = {'X': 1, 'B': 8, 'W': 16, 'D': 32, 'L': 64}

    """
    YAPLC Locations mapping
    """
    LocationTypes = {'I': LOCATION_VAR_INPUT,
                     'Q': LOCATION_VAR_OUTPUT,
                     'M': LOCATION_VAR_MEMORY
                     }

    def __init__(self):

        """
        YAPLC SubNodes to ProjectController
        """
        self.CTNChildrenTypes = []

        self.ConfigTemplatePath = None

        CodeFile.__init__(self)

        parent = self.GetCTRoot()
        if parent is not None:
            target = parent.GetTarget().getcontent().getLocalTag()
            base_path = os.path.dirname(__file__)
            self.ConfigTemplatePath = os.path.join(base_path, '..', 'yaplctargets', target, 'extensions.cfg')

            if not os.path.isfile(self.ConfigTemplatePath):
                Warn(None, _("Target doesn't support YAPLC features."), _("Warning"))
                self.GetCTRoot().logger.write_error(
                    _("Couldn't create %s node.") % self.CTNName())
            else:
                try:
                    error = None
                    # let's add template variables if we start first time
                    if self.ConfigTemplatePath is not None:
                        try:
                            self.YAPLCParser = YAPLCConfigParser()
                            self.YAPLCParser.fparse(self.ConfigTemplatePath)
                            self.FillFromTemplate()
                        except ParseError as pe:
                            self.GetCTRoot().logger.write_error(
                                _("Couldn't read %s file because: %s") % self.CTNName() % pe.message())
                            error = unicode(pe.message())

                    else:
                        self.GetCTRoot().logger.write_error(_("Couldn't load templates path for target %s") %
                                                            parent.GetTarget().getcontent().getLocalTag())

                except Exception, exc:
                    error = unicode(exc)

                if error is not None:
                    self.GetCTRoot().logger.write_error(
                        _("Couldn't import old %s file.") % self.CTNName())

    def FillFromTemplate(self, ):
        for group in self.YAPLCParser.groups():

            if group.parametrized() or group.hasParametrized():
                NewGroup = CreateLocationsGroupClass('YAPLCTLocationsGroup', YAPLCTLocationsGroup, None)

                g = (group.name(), NewGroup, group.name())
                if g not in self.CTNChildrenTypes:
                    self.CTNChildrenTypes.append(g)

    def GetBaseTypes(self):
        return self.GetCTRoot().GetBaseTypes()

    def GetDataTypes(self, basetypes=False):
        return self.GetCTRoot().GetDataTypes(basetypes=basetypes)

    def GenerateNewName(self, format, start_idx):
        return self.GetCTRoot().GenerateNewName(
            None, None, format, start_idx,
            dict([(var.getname().upper(), True)
                  for var in self.CodeFile.variables.getvariable()]))

    def CodeFileName(self):
        return os.path.join(self.CTNPath(), "yaplcconfig.xml")

    def GetLocationsForGroup(self, group, parser, parent=None):
        locations = []

        for grp in group.children():
            if grp.parametrized():
                if parent is not None:
                    result = filter(lambda x: grp.name() == x['name'], parent['children'])
                    if len(result) > 0:
                        result[0]['children'] += self.GetLocationsForGroup(grp, parser, result[0])
                    continue
                else:
                    continue

            locations.append({
                "name": grp.name(),
                "type": LOCATION_GROUP,
                "size": 0,
                "IEC_type": '',
                "var_name": '',
                "location": "%s" % grp.group(),
                "description": "",
                "children": self.GetLocationsForGroup(grp, parser)})

        for loc in group.locations():
            if loc.parametrized():
                continue

            params = loc.parameters().values()
            for value in params[0]['values']:
                if group.parametrized():
                    lname = '{0}.{1}.{2}'.format(loc.name(), parent['location'], value)
                    location = '{0}.{1}.{2}'.format(loc.name()[1:], parent['location'], value)
                else:
                    lname = '{0}.{1}'.format(loc.name(), value)
                    location = '{0}{1}.{2}'.format(loc.datatype(), group.group(), value)

                for p in params[1:]:
                    lname += '.{0}'.format(p['values'][0])
                    location += '.{0}'.format(p['values'][0])

                locations.append({
                    "name": '%%%s' % lname,
                    "type": self.LocationTypes[loc.type()],
                    "size": self.SizeConversion[loc.datatype()],
                    "IEC_type": self.IECTypes[loc.datatype()],
                    "var_name": '_%s' % lname.replace('.', '_'),
                    "location": location,
                    "description": "",
                    "children": []})

        return locations

    def GetLocationsForNode(self, group, parser, node, args=[]):

        locations = []
        for child in node.IECSortedChildren():
            grp = parser.getgroup(child.CTNType)
            if grp is not None:
                gids = []
                if grp.parametrized():
                        v = getattr(child.YAPLCTLocationsGroup, grp.group()['name'])
                        if v is not None:
                            gids.append(str(v))
                else:
                    gids.append(str(grp.group()))

                locations.append({
                    "name": child.CTNType,
                    "type": LOCATION_GROUP,
                    "size": 0,
                    "IEC_type": '',
                    "var_name": '',
                    "location": "%s" % ".".join(gids),
                    "description": "",
                    "children": self.GetLocationsForNode(grp, parser, child, gids)})
            else:
                # this is a location
                loc = group.getlocation(child.CTNType)
                locs = []
                for p in loc.parameters().values():
                    v = getattr(child.YAPLCTLocation, p['name'])
                    locs.append(str(v))
                idx = args + locs
                vname = '_%s%s' % (child.CTNType, '.' + '.'.join(idx))
                vname = vname.replace('.', '_')
                locations.append({
                    "name": '%%%s' % (str(child.CTNType) + '.' + '.'.join(idx)),
                    "type": self.LocationTypes[loc.type()],
                    "size": self.SizeConversion[loc.datatype()],
                    "IEC_type": self.IECTypes[loc.datatype()],
                    "var_name": vname,
                    "location": '%s%s' % (loc.name()[1:], '.' + '.'.join(idx)),
                    "description": "",
                    "children": []})

        return locations

    def GetVariableLocationTree(self):
        current_location = self.GetCurrentLocation()

        locations = []

        if self.YAPLCParser is not None:
            parser = self.YAPLCParser

            # first add parametrized
            for child in self.IECSortedChildren():
                group = parser.getgroup(child.CTNType)
                if group is not None:
                    gids = []
                    if group.parametrized():
                        pass
                    else:
                        gids.append(group.group())
                        locations.append({
                            "name": group.name(),
                            "type": LOCATION_GROUP,
                            "size": 0,
                            "IEC_type": '',
                            "var_name": '',
                            "location": "%s" % group.group(),
                            "description": "",
                            "children": self.GetLocationsForNode(group, parser, child)})

            # extract static locations and groups
            for group in parser.groups():

                if group.parametrized():
                    continue

                result = filter(lambda x: group.name() == x['name'], locations)
                if len(result) > 0:
                    result[0]['children'] += self.GetLocationsForGroup(group, parser, result[0])
                else:
                    locations.append({
                        "name": group.name(),
                        "type": LOCATION_GROUP,
                        "size": 0,
                        "IEC_type": '',
                        "var_name": '',
                        "location": "%s" % group.group(),
                        "description": "",
                        "children": self.GetLocationsForGroup(group, parser)})

        return {"name": self.BaseParams.getName(),
                "type": LOCATION_CONFNODE,
                "location": ".".join([str(i) for i in current_location]) + ".x",
                "children": locations
                }

    def SetTextParts(self, parts):
        for section in self.SECTIONS_NAMES:
            section_code = parts.get(section)
            if section_code is not None:
                getattr(self.CodeFile, section).setanyText(section_code)

    def GetTextParts(self):
        return dict([(section, getattr(self.CodeFile, section).getanyText())
                     for section in self.SECTIONS_NAMES])

    def CTNTestModified(self):
        return self.ChangesToSave or not self.CodeFileIsSaved()

    def OnCTNSave(self, from_project_path=None):
        filepath = self.CodeFileName()

        xmlfile = open(filepath, "w")
        xmlfile.write(etree.tostring(
            self.CodeFile,
            pretty_print=True,
            xml_declaration=True,
            encoding='utf-8'))
        xmlfile.close()

        self.MarkCodeFileAsSaved()
        return True

    def CTNGlobalInstances(self):
        variables = self.CodeFileVariables(self.CodeFile)
        ret = [(variable.getname(),
                variable.gettype(),
                variable.getinitial())
               for variable in variables]
        ret.extend([("On" + variable.getname() + "Change", "python_poll", "")
                    for variable in variables
                    if variable.getonchange()])
        return ret

    # -------------------------------------------------------------------------------
    #                      Current Buffering Management Functions
    # -------------------------------------------------------------------------------

    """
    Return a copy of the codefile model
    """

    def Copy(self, model):
        return deepcopy(model)

    def CreateCodeFileBuffer(self, saved):
        self.Buffering = False
        self.CodeFileBuffer = UndoBuffer(self.CodeFileParser.Dumps(self.CodeFile), saved)

    def BufferCodeFile(self):
        self.CodeFileBuffer.Buffering(self.CodeFileParser.Dumps(self.CodeFile))

    def StartBuffering(self):
        self.Buffering = True

    def EndBuffering(self):
        if self.Buffering:
            self.CodeFileBuffer.Buffering(self.CodeFileParser.Dumps(self.CodeFile))
            self.Buffering = False

    def MarkCodeFileAsSaved(self):
        self.EndBuffering()
        self.CodeFileBuffer.CurrentSaved()

    def CodeFileIsSaved(self):
        return self.CodeFileBuffer.IsCurrentSaved() and not self.Buffering

    def LoadPrevious(self):
        self.EndBuffering()
        self.CodeFile = self.CodeFileParser.Loads(self.CodeFileBuffer.Previous())

    def LoadNext(self):
        self.CodeFile = self.CodeFileParser.Loads(self.CodeFileBuffer.Next())

    def GetBufferState(self):
        first = self.CodeFileBuffer.IsFirst() and not self.Buffering
        last = self.CodeFileBuffer.IsLast()
        return not first, not last
