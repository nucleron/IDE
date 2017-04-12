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
from yaplcparser import YAPLCParameterType
from PLCControler import LOCATION_CONFNODE, LOCATION_VAR_INPUT, LOCATION_VAR_OUTPUT, LOCATION_VAR_MEMORY, LOCATION_GROUP
from yaplcparser import ParseError
from editors.ConfTreeNodeEditor import ConfTreeNodeEditor
from itertools import product
import shutil


def Warn(parent, message, caption='Warning!'):
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
LOC_SECTION_ENUMERATION = """<xsd:enumeration value="%s"/>\n"""
LOC_SECTION_ENUMERATION_TAG_ELEMENT = """<xsd:attribute name="%(name)s" %(opt)s>
                                    <xsd:simpleType>
                                        <xsd:restriction base="xsd:string">
                                            %(enumerations)s
                                        </xsd:restriction>
                                    </xsd:simpleType>
                                </xsd:attribute>\n"""


def PrepareParametrizedXSDNode(name, base, node):
    """
    Prepare XSD scheme for location with variable parameters
    :param name: Name of the node
    :param base: Base class for the node
    :param node: Parent node
    :return: Prepared XSD node class
    """
    params = ''
    for p in node.parameters():
        if not p['name']:
            continue

        if p['type'] == 'Range':
            params += LOC_SECTION_RESTRICTION_TAG_ELEMENT % ({'name': p['name'],
                                                              'opt': 'use="required"',
                                                              'min': p['min'],
                                                              'max': p['max']
                                                              }
                                                             )

        elif p['type'] == 'Items':
            enums = ""
            for item in p['items']:
                enums += LOC_SECTION_ENUMERATION % item

            params += LOC_SECTION_ENUMERATION_TAG_ELEMENT % ({'name': p['name'],
                                                              'opt': 'use="required"',
                                                              'enumerations': enums
                                                              })

        elif p['type'] == 'Number':
            params += LOC_SECTION_TAG_ELEMENT % (p['name'], 'xsd:integer', 'use="required"')

    attributes = {
        'name': str(base.__name__),
        'attributes': params
    }

    xsd = XSD_LOCATIONS_GROUP % attributes
    newNode = type(str(base.__name__) + str(name) + node.name(), (base,), {'XSD': xsd, })

    return newNode


def CreateLocationClass(name, base, node):
    """
    Creates location class
    :param name: Name of location
    :param base: Base class of location
    :param node: Parent node of location
    :return: Prepared XSD class for location
    """
    if node.parametrized():
        newNode = PrepareParametrizedXSDNode(name, base, node)
        setattr(newNode, 'IconFileName', 'YAPLCConfigurableLocation')
    else:
        newNode = None

    return newNode


def CreateLocationsGroupClass(name, base, node):
    """
    Create group location class
    :param name: Name of location group
    :param base: Base class of location group
    :param node: Parent node of location class
    :return: Prepared XSD class for location group
    """
    if node and node.parametrized():
        NewGroup = PrepareParametrizedXSDNode(name, base, node)
    else:
        NewGroup = base
        setattr(NewGroup, 'XSD', None)

    return NewGroup


def CreateGroupNode(node, group, name):
    if group.parametrized() or group.hasParametrized():
        groupClass = CreateLocationsGroupClass(name, YAPLCTLocationsGroup, group)

    if group.parametrized():
        grp = (group.name(), groupClass, group.name())
        if grp not in node.CTNChildrenTypes:
            node.CTNChildrenTypes.append(grp)
    elif group.hasParametrized():
        params = JoinParameters(group.parameters())
        for s in params:
            sName = '%s.%s' % (group.name(), '.'.join(str(x) for x in s))
            grp = (sName, groupClass, sName)
            if grp not in node.CTNChildrenTypes:
                node.CTNChildrenTypes.append(grp)


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
        if name.find('.') > 0:
            group = parser.getgroup(name[:name.find('.')])
        else:
            group = parser.getgroup(name)

        if group is None:
            raise ParseError("Group %s is None" % name)

        for sg in group.children():
            CreateGroupNode(self, sg, name)

        # fill with locations
        for loc in group.locations():
            if loc.parametrized():
                locClass = CreateLocationClass(name, YAPLCTLocation, loc)
                if loc.descriptive():
                    ll = (loc.descriptive(), locClass, loc.name())
                else:
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
                    _("Couldn't create %s node.\n") % self.CTNName())
            else:
                try:
                    error = None
                    # let's add template variables if we start first time
                    if self.ConfigTemplatePath is not None:
                        self.YAPLCParser = YAPLCConfigParser()
                        self.YAPLCParser.fparse(self.ConfigTemplatePath)
                        self.FillFromTemplate()
                    else:
                        self.GetCTRoot().logger.write_error(_("Couldn't load templates path for target %s\n") %
                                                            parent.GetTarget().getcontent().getLocalTag())
                except ParseError as pe:
                    self.GetCTRoot().logger.write_error(
                        _("Couldn't read %s file because: %s\n") % (self.CTNName(), pe.message()))
                    error = unicode(pe.message())

                except Exception, exc:
                    error = unicode(exc)

                if error is not None:
                    self.GetCTRoot().logger.write_error(
                        _("Couldn't import old %s file.") % self.CTNName())

    def FillFromTemplate(self):
        for group in self.YAPLCParser.groups():
            CreateGroupNode(self, group, 'YAPLCTLocationsGroup')

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

    def FindParametrizedGroupParameters(self, name, baseNode=None):
        result = dict()

        if not baseNode:
            baseNode = self

        for child in baseNode.IECSortedChildren():
            if child.CTNType == name:
                grp = self.YAPLCParser.getgroup(child.CTNType)
                if grp is not None:
                    if grp.parametrized():
                        for p in grp.parameters():
                            v = getattr(child.YAPLCTLocationsGroup, p['name'])
                            if v is not None:
                                result[p['name']] = v
                return result
            else:
                result = self.FindParametrizedGroupParameters(name, child)

        return result

    def GetLocationsForGroup(self, group, parser, parent=None, args=[]):
        locations = []

        for grp in group.children():
            if parent:
                if grp.parametrized():
                    result = filter(lambda x: x['name'].startswith(grp.name()), parent['children'])
                    if result:
                        lst = list(args)
                        lst.append(result[0]['location'])   # Add my current location
                        result[0]['children'] += self.GetLocationsForGroup(grp, parser, result[0], lst)
                else:
                    combined = JoinParameters(grp.parameters())

                    for line in combined:
                        groupLocation = '.'.join(str(x) for x in line)
                        lname = '{0}.{1}'.format(grp.name(), groupLocation)

                        result = filter(lambda x: x['name'].startswith(lname), parent['children'])
                        if result:
                            lst = list()
                            lst.append(result[0]['location'])
                            result[0]['children'] += self.GetLocationsForGroup(grp, parser, result[0], args + lst)
                        else:
                            locations.append({
                                "name": lname,
                                "type": LOCATION_GROUP,
                                "size": 0,
                                "IEC_type": '',
                                "var_name": '',
                                "location": "%s" % groupLocation,
                                "description": "",
                                "children": self.GetLocationsForGroup(grp, parser, None, args + list(line))})

            else:
                if grp.parametrized():  # Parametrized groups evaluated here
                    continue

                combined = JoinParameters(grp.parameters())

                for line in combined:
                    groupLocation = '.'.join(str(x) for x in line)
                    lname = '{0}.{1}'.format(grp.name(), groupLocation)

                    locations.append({
                        "name": lname,
                        "type": LOCATION_GROUP,
                        "size": 0,
                        "IEC_type": '',
                        "var_name": '',
                        "location": "%s" % groupLocation,
                        "description": "",
                        "children": self.GetLocationsForGroup(grp, parser, None, args + list(line))})

        # Locations processing
        if group.parametrized() and not parent:
            pass
        else:

            for loc in group.locations():
                if loc.parametrized():
                    continue

                combLocs = JoinParameters(loc.parameters())

                for line in combLocs:
                    indexes = args + list(line)
                    lname = '{0}'.format(loc.name() + '.'.join(str(x) for x in indexes))
                    location = lname[1:]

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
            if child.CTNType.find('.') > 0:
                name = child.CTNType[:child.CTNType.find('.')]
                suffix = child.CTNType[child.CTNType.find('.') + 1:]
            else:
                name = child.CTNType
            grp = parser.getgroup(name)
            if grp:
                gids = dict()
                if grp.parametrized():
                    for p in grp.parameters():
                        if not p['name']:
                            continue
                        v = getattr(child.YAPLCTLocationsGroup, p['name'])
                        if v is not None:
                            gids[p['name']] = v

                if gids:
                    groups = JoinParameters(grp.parameters(), gids)
                else:
                    groups = list()
                    groups.append(suffix.split('.'))

                for g in groups:
                    subLocations = self.GetLocationsForNode(grp, parser, child, args + list(g))

                    if subLocations or grp.parametrized():
                        locationString = '%s' % '.'.join(str(x) for x in g)
                        locations.append({
                            "name": '%s.%s' % (name, locationString),
                            "type": LOCATION_GROUP,
                            "size": 0,
                            "IEC_type": '',
                            "var_name": '',
                            "location": "%s" % locationString,
                            "description": "",
                            "children": subLocations})
            else:
                loc = group.getlocation(child.CTNType)
                locs = dict()
                for p in loc.parameters():
                    if p['name']:
                        v = getattr(child.YAPLCTLocation, p['name'])
                        locs[p['name']] = v

                params = JoinParameters(loc.parameters(), locs)

                for pp in params:
                    idx = args + list(pp)
                    vname = '_%s%s' % (loc.name(), '.'.join(str(x) for x in idx))
                    vname = vname.replace('.', '_')
                    locations.append({
                        "name": '%%%s' % (str(loc.name()) + '.'.join(str(x) for x in idx)),
                        "type": self.LocationTypes[loc.type()],
                        "size": self.SizeConversion[loc.datatype()],
                        "IEC_type": self.IECTypes[loc.datatype()],
                        "var_name": vname,
                        "location": '%s%s' % (loc.name()[1:], '.'.join(str(x) for x in idx)),
                        "description": "",
                        "children": []})

        return locations

    def GetVariableLocationTree(self):
        current_location = self.GetCurrentLocation()

        locations = []

        if self.YAPLCParser is not None:
            parser = self.YAPLCParser

            locations += self.GetLocationsForNode(None, parser, self)

            # extract static locations and groups
            for group in parser.groups():
                # if group.parametrized():
                #     continue

                result = filter(lambda x: x['name'].startswith(group.name()), locations)
                if result:
                    lst = list()
                    lst.append(result[0]['location'])
                    result[0]['children'] += self.GetLocationsForGroup(group, parser, result[0], lst)
                else:
                    groups = JoinParameters(group.parameters())

                    for g in groups:
                        groupLocation = "%s" % '.'.join(str(x) for x in g)
                        locations.append({
                            "name": group.name() + '.' + groupLocation,
                            "type": LOCATION_GROUP,
                            "size": 0,
                            "IEC_type": '',
                            "var_name": '',
                            "location": groupLocation,
                            "description": "",
                            "children": self.GetLocationsForGroup(group, parser, None, list(g))})

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


def JoinParameters(parameters, args={}):
    lists = list()
    for p in parameters:
        if p['name'] and p['name'] in args:
            lst = list()
            lst.append(args[p['name']])
            lists.append(lst)
        else:
            if p['type'] == 'Number':
                # add value to all lines
                lst = list()
                lst.append(p['value'])
                lists.append(lst)

            elif p['type'] == 'Range':
                lst = list()
                for v in range(p['min'], p['max'] + 1):
                    lst.append(v)

                lists.append(lst)

            elif p['type'] == 'Items':
                lst = list()
                for v in p['items']:
                    lst.append(v)
                lists.append(lst)

    return product(*lists)
