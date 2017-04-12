import shlex
import collections
import os
from string import find
from string import split

"""
TODO: Syntax extensions
1. Enumerated parameters split by ',' sign placed inside square brackets.
2. Regions doesn't generate all values when created, but operates with min/max ranges.
3. Single value parameters interprets like a group id.
4. Range group parameters interprets like a tuple of groups.
5. Text labels are enclosed with quotes inside square brackets after value split by a column from value.
6. Correct group id detection.
7. Use meta-class to create more accurate and extensible parameters class.
8. Locations may have descriptive name. Optional for plain locations and required for parametrized.
"""

"""
YAPLC locations: Input, Memory, Output(Q)
"""
YAPLCLocationTypes = ['I', 'M', 'Q']

"""
YAPLC locations data types: bool, byte, word, double-word, long, string
"""
YAPLCLocationDataTypes = ['X', 'B', 'W', 'D', 'L', 'S']

"""
YAPLC location parameter types
"""
YAPLCParameterType = {'Number': 0, 'Range': 1, 'Items': 2}

"""
"""
YAPLCNameIllegal = ['.', ',', '"', '*', ':', '#', '@', '!', '(', ')', '{', '}']


class ParseError(BaseException):
    """ Exception reports parsing errors when processing YAPLC template files """

    def __init__(self, message=None):
        self._message = message

    def message(self):
        return self._message


class YAPLCLocationBase:

    def __init__(self):
        self._parameters = list()
        self._parametrized = False

    def addParameters(self, values, name=""):

        if find(values, '..') >= 0:
            # range of channels
            bounds = split(values, '..')

            if len(bounds) != 2:
                raise ParseError(_("Wrong range syntax"))

            if not bounds[0].isdigit() or not bounds[1].isdigit():
                raise ParseError(_("Incorrect bounds format %s..%s") % bounds[0] % bounds[1])

            lbound = int(bounds[0])
            rbound = int(bounds[1])

            self._parameters.append({"name": name,
                                     "type": 'Range',
                                     "min": lbound,
                                     "max": rbound
                                     })

        elif find(values, ',') >= 0:
            items = split(values, ',')

            self._parameters.append({"name": name,
                                     "type": 'Items',
                                     "items": items
                                     })
        else:
            self._parameters.append({"name": name,
                                     "type": 'Number',
                                     "value": values
                                     })

    def parameters(self):
        return self._parameters

    def parametrized(self):
        return self._parametrized


class YAPLCLocation(YAPLCLocationBase):
    """
    YAPLC location abstraction to represent an location described by syntax
    """

    def __init__(self, typestr, group, unique=False, *args):

        YAPLCLocationBase.__init__(self)

        self._descriptive = None

        if len(typestr) != 2:
            raise ParseError(_("Incorrect type coding %s") % typestr)

        if typestr[0] not in YAPLCLocationTypes:
            raise ParseError(_("Type %s not recognized") % typestr[0])
        else:
            self._type = typestr[0]

        if typestr[1] not in YAPLCLocationDataTypes:
            raise ParseError(_("Data type %s not recognized") % typestr[1])
        else:
            self._datatype = typestr[1]

        for p in args:
            if str(p).startswith('['):
                # this is named parameter
                param = str(p).rstrip(']').lstrip('[')
                name, value = param.split(':')
                # print name, value
                self.addParameters(value, name)
                self._parametrized = True
                if not self._descriptive:
                    raise ParseError(_("Parametrized locations requires descriptive name"))
            elif str(p).startswith('"'):
                # descriptive name of location
                self._descriptive = str(p).rstrip('"').lstrip('"')
                if any(s in self._descriptive for s in YAPLCNameIllegal):
                    raise ParseError(_("Illegal symbol in group's name: %s") % self._descriptive)
            elif str(p).isdigit():
                self.addParameters(p)
            else:
                # this is the unnamed range or items
                self.addParameters(p)

        self._unique = unique
        self._group = group  # group to this location

    def type(self):
        return self._type

    def datatype(self):
        return self._datatype

    def unique(self):
        return self._unique

    def descriptive(self):
        return self._descriptive

    def __str__(self):
        return '{0}{1}'.format(self._type, self._datatype)

    def name(self):
        return self.__str__()

    def __repr__(self):
        return self.__str__()


class YAPLCGroup(YAPLCLocationBase):
    """
    YAPLC group abstraction allow to store info about group extracted from DSL
    """

    def __init__(self, name, values=None, unique=False, parent=None, *args):

        YAPLCLocationBase.__init__(self)

        self._name = str(name).rstrip('"').lstrip('"')

        if any(s in self._name for s in YAPLCNameIllegal):
            raise ParseError(_("Illegal symbol in group's name: %s") % self._name)

        if len(values) > 1:
            raise ParseError(_("Too many parameters for group: %s") % self._name)

        for v in values:
            if str(v).startswith('['):
                param = str(v).rstrip(']').lstrip('[')
                name, value = param.split(':')
                self.addParameters(value, name)
                self._parametrized = True
            else:
                self.addParameters(v)

        self._unique = unique
        self._locations = list()
        self._parent = parent
        self._children = list()

    def name(self):
        return self._name

    def group(self):
        return None

    def append(self, location):
        self._locations.append(location)

    def locations(self):
        return self._locations

    def getlocation(self, name):
        for loc in self._locations:
            if loc.name() == name or loc.descriptive() == name:
                return loc

        return None

    def children(self):
        return self._children

    def unique(self):
        return self._unique

    def parent(self):
        return self._parent

    def hasParametrized(self):
        for child in self._children:
            if child.parametrized():
                return True
            else:
                return child.hasParametrized()

        for loc in self._locations:
            if loc.parametrized():
                return True

        return False

    def addsubgroup(self, group):
        self._children.append(group)


# YAPLC Extensions configuration parser
class YAPLCConfigParser:

    class yaplcparser(shlex.shlex):

        def __init__(self, instream=None, infile=None, posix=False):
            shlex.shlex.__init__(self, instream=instream, infile=infile, posix=posix)
            # add this tu usual shlex parser
            self.brackets = "[]"

        def read_token(self):
            quoted = False
            enclosed = False
            escapedstate = ' '
            while True:
                nextchar = self.instream.read(1)
                if nextchar == '\n':
                    self.lineno += 1
                if self.debug >= 3:
                    print "shlex: in state", repr(self.state), \
                        "I see character:", repr(nextchar)
                if self.state is None:
                    self.token = ''  # past end of file
                    break
                elif self.state == ' ':
                    if not nextchar:
                        self.state = None  # end of file
                        break
                    elif nextchar in self.whitespace:
                        if self.debug >= 2:
                            print "shlex: I see whitespace in whitespace state"
                        if self.token or (self.posix and quoted) or (self.posix and enclosed):
                            break  # emit current token
                        else:
                            continue
                    elif nextchar in self.commenters:
                        self.instream.readline()
                        self.lineno += 1
                    elif self.posix and nextchar in self.escape:
                        escapedstate = 'a'
                        self.state = nextchar
                    elif nextchar in self.wordchars:
                        self.token = nextchar
                        self.state = 'a'
                    elif nextchar in self.quotes:
                        if not self.posix:
                            self.token = nextchar
                        self.state = nextchar
                    elif self.whitespace_split:
                        self.token = nextchar
                        self.state = 'a'
                    elif nextchar in self.brackets:
                        self.token = nextchar
                        self.state = '['
                    else:
                        self.token = nextchar
                        if self.token or (self.posix and quoted) or (self.posix and enclosed):
                            break  # emit current token
                        else:
                            continue
                elif self.state in self.quotes:
                    quoted = True
                    if not nextchar:  # end of file
                        if self.debug >= 2:
                            print "shlex: I see EOF in quotes state"
                        # XXX what error should be raised here?
                        raise ValueError, "No closing quotation"
                    if nextchar == self.state:
                        if not self.posix:
                            self.token = self.token + nextchar
                            self.state = ' '
                            break
                        else:
                            self.state = 'a'
                    elif self.posix and nextchar in self.escape and \
                                    self.state in self.escapedquotes:
                        escapedstate = self.state
                        self.state = nextchar
                    else:
                        self.token = self.token + nextchar
                elif self.state in self.brackets:
                    enclosed = True
                    if not nextchar:  # end of file
                        if self.debug >= 2:
                            print "shlex: I see EOF in quotes state"
                        # XXX what error should be raised here?
                        raise ValueError, "No closing bracket"
                    if nextchar == ']':  # closing bracket
                        if not self.posix:
                            self.token = self.token + nextchar
                            self.state = ' '
                            break
                        else:
                            self.state = 'a'
                    elif self.posix and nextchar in self.escape and \
                                    self.state in self.escapedquotes:
                        escapedstate = self.state
                        self.state = nextchar
                    else:
                        self.token = self.token + nextchar
                elif self.state in self.escape:
                    if not nextchar:  # end of file
                        if self.debug >= 2:
                            print "shlex: I see EOF in escape state"
                        # XXX what error should be raised here?
                        raise ValueError, "No escaped character"
                    # In posix shells, only the quote itself or the escape
                    # character may be escaped within quotes.
                    if escapedstate in self.quotes and \
                                    nextchar != self.state and nextchar != escapedstate:
                        self.token = self.token + self.state
                    self.token = self.token + nextchar
                    self.state = escapedstate
                elif self.state == 'a':
                    if not nextchar:
                        self.state = None  # end of file
                        break
                    elif nextchar in self.whitespace:
                        if self.debug >= 2:
                            print "shlex: I see whitespace in word state"
                        self.state = ' '
                        if self.token or (self.posix and quoted) or (self.posix and enclosed):
                            break  # emit current token
                        else:
                            continue
                    elif nextchar in self.commenters:
                        self.instream.readline()
                        self.lineno += 1
                        if self.posix:
                            self.state = ' '
                            if self.token or (self.posix and quoted) or (self.posix and enclosed):
                                break  # emit current token
                            else:
                                continue
                    elif self.posix and nextchar in self.quotes:
                        self.state = nextchar
                    elif self.posix and nextchar in self.escape:
                        escapedstate = 'a'
                        self.state = nextchar
                    elif nextchar in self.wordchars or nextchar in self.quotes \
                            or self.whitespace_split or nextchar in self.brackets:
                        self.token = self.token + nextchar
                    else:
                        self.pushback.appendleft(nextchar)
                        if self.debug >= 2:
                            print "shlex: I see punctuation in word state"
                        self.state = ' '
                        if self.token:
                            break  # emit current token
                        else:
                            continue
            result = self.token
            self.token = ''
            if self.posix and not quoted and not enclosed and result == '':
                result = None
            if self.debug > 1:
                if result:
                    print "shlex: raw token=" + repr(result)
                else:
                    print "shlex: raw token=EOF"
            return result

    @staticmethod
    def parseline(line):
        """Parse single line read from settings file

        :param line: Line of text (string) to parse
        :return: list of tokens split from line
        """
        lexer = YAPLCConfigParser.yaplcparser(line)
        lexer.commenters = '#'
        lexer.wordchars += '.():,'

        return list(lexer)

    def groups(self):
        """Get groups parsed from configuration file

        :return: list of groups keys
        """
        return self._groups.values()

    def getgroup(self, name):

        def findgroup(name, group):
            if name == group.name():
                return group

            for g in group.children():
                if g.name() == name:
                    return g

                if len(g.children()) > 0:
                    return findgroup(name, g)

            return None

        group = None
        if name in self._groups:
            # in root groups
            group = self._groups[name]
        else:
            # in nested groups
            for g in self._groups.values():
                group = findgroup(name, g)
                if group is not None:
                    break

        return group

    def getlocations(self, group):
        """Get locations of specified group

        :param group: Group of locations
        :return: Locations list
        """
        if group in self._groups:
            return self._groups[group].locations()
        else:
            return None

    def addgroup(self, group):
        if group not in self._groups:
            self._groups[group.name()] = group

    def addlocation(self, group, location):
        if group in self._groups:
            self._groups.get(group).append(location)

    def __init__(self, dict_type=collections.defaultdict):
        self._dict = dict_type
        self._groups = self._dict()

    def fparse(self, fileName = None):
        if fileName is not None:
            try:
                with open(fileName) as f:
                    currentGroup = None
                    for line in f:
                        tokens = YAPLCConfigParser.parseline(line)

                        if tokens:
                            if tokens[0] == 'UGRP' or tokens[0] == 'GRP':
                                rest = []

                                if len(tokens) < 3:
                                    raise ParseError("Arguments number for group less than required")
                                elif len(tokens) >= 3:
                                    rest = tokens[2:]

                                # begin of the unique group/end of previous
                                if tokens[1] in self._groups:
                                    if self._groups[tokens[1]].unique():
                                        raise ParseError(_("Has the same unique group %s") % tokens[1])

                                if currentGroup is not None:
                                    grp = YAPLCGroup(tokens[1], rest, (tokens[0] == 'UGRP'), currentGroup)
                                    currentGroup.addsubgroup(grp)
                                else:
                                    grp = YAPLCGroup(tokens[1], rest, (tokens[0] == 'UGRP'), None)
                                    self.addgroup(grp)  # also add to flat root groups table

                                currentGroup = grp

                            elif tokens[0] == 'LOC' or tokens[0] == 'ULOC':
                                # non-unique location description
                                if currentGroup is None:
                                    raise ParseError(_("Location %s without group") % tokens[0])
                                if currentGroup.unique():
                                    loc = YAPLCLocation(tokens[1], currentGroup,
                                                        (tokens[0] == 'ULOC'), *tokens[2:])
                                else:
                                    # non-unique group could have no GID and parameters only
                                    loc = YAPLCLocation(tokens[1], currentGroup,
                                                        (tokens[0] == 'ULOC'), *tokens[2:])
                                currentGroup.append(loc)

                            elif tokens[0] == 'ENDGRP':
                                # close current group and try to return to parent group
                                if currentGroup is None:
                                    raise ParseError(_("Illegal end of group"))

                                currentGroup = currentGroup.parent()

                            else:
                                raise ParseError(_("Illegal instruction: %s") % tokens[0])

                    if currentGroup is not None:
                        raise ParseError(_("Group %s has not been closed properly!") % currentGroup.name())

            except IOError:
                raise ParseError(_("No template file for current target"))


if __name__ == '__main__':
    parser = YAPLCConfigParser()
    path = os.path.join(os.path.dirname(__file__),
                        '..', 'yaplctargets', 'nuc247',
                        r'extensions.cfg')
    try:
        parser.fparse(path)
    except ParseError as pe:
        print pe.message()

    for grp in parser.groups():
        print grp
        print grp.locations()
