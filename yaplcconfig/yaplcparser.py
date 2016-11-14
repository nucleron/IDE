import shlex
import collections
import os
from string import find
from string import split


"""
YAPLC locations: Input, Memory, Output(Q)
"""
YAPLCLocationTypes = ['I', 'M', 'Q']

"""
YAPLC locations data types: bool, byte, word, double-word, long, string
"""
YAPLCLocationDataTypes = ['X', 'B', 'W', 'D', 'L', 'S']


class ParseError(BaseException):
    """ Exception reports parsing errors when processing YAPLC template files """

    def __init__(self, message=None):
        self._message = message

    def message(self):
        return self._message


class YAPLCLocation:

    def __init__(self, typestr, gid, unique=False, *args):

        self._parameters = dict()
        self._parametrized = False

        def addParameters(values, pcount, name=""):
            if find(values, '..') < 0:
                self._parameters[pcount] = {"name": name,
                                            "values": values
                                            }
            else:
                # range of channels
                bounds = split(values, '..')

                if len(bounds) != 2:
                    raise ParseError(_("Wrong range syntax"))

                if not bounds[0].isdigit() or not bounds[1].isdigit():
                    raise ParseError(_("Incorrect bounds format %s..%s") % bounds[0] % bounds[1])

                lbound = int(bounds[0])
                rbound = int(bounds[1]) + 1  # to include right-most value of range

                if lbound < 0 or rbound < 0 or lbound > rbound:
                    raise ParseError(_("Incorrect bounds format %s..%s") % bounds[0] % bounds[1])

                vals = list()
                for index in range(lbound, rbound):
                    vals.append(index)

                self._parameters[pcount] = {"name": name,
                                            "values": vals
                                            }

        pcount = 0

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
                addParameters(value, pcount, name)
                pcount += 1
                self._parametrized = True

            elif str(p).isdigit():
                addParameters(p, pcount)
                pcount += 1
            else:
                # this is the range
                addParameters(p, pcount)
                pcount += 1

        self._unique = unique
        # self._postfixes = list(args)
        self._gid = gid  # group ID

    def type(self):
        return self._type

    def datatype(self):
        return self._datatype

    def parameters(self):
        return self._parameters

    def unique(self):
        return self._unique

    def parametrized(self):
        return self._parametrized

    def __str__(self):
        return '{0} {1}'.format(self._type, self._datatype)

    def name(self):
        return '{0}{1}{2}'.format(self._type, self._datatype, self._gid)

    def __repr__(self):
        return self.__str__()


class YAPLCGroup:

    def __init__(self, name, gid=None, unique=False, parent=None, *args):

        self._parameters = dict()
        self._parametrized = False

        def setGroupParameter(values, name):
            if find(values, '..') < 0:
                self._groupid = {"name": name,
                                 "values": values
                                 }
            else:
                # range of channels
                bounds = split(values, '..')

                if len(bounds) != 2:
                    raise ParseError(_("Wrong range syntax"))

                if not bounds[0].isdigit() or not bounds[1].isdigit():
                    raise ParseError(_("Incorrect bounds format %s..%s") % bounds[0] % bounds[1])

                lbound = int(bounds[0])
                rbound = int(bounds[1]) + 1  # to include right-most value of range

                if lbound < 0 or rbound < 0 or lbound > rbound:
                    raise ParseError(_("Incorrect bounds format %s..%s") % bounds[0] % bounds[1])

                vals = list()
                for index in range(lbound, rbound):
                    vals.append(index)

                self._groupid = {"name": name,
                                 "values": vals
                                 }

        self._name = str(name).rstrip('"').lstrip('"')

        if str(gid).startswith('['):
            param = str(gid).rstrip(']').lstrip('[')
            name, value = param.split(':')
            setGroupParameter(value, name)
            self._parametrized = True
        else:
            self._groupid = gid

        self._unique = unique
        self._locations = list()
        # support for nested groups
        self._parent = parent
        self._children = list()

    def name(self):
        return self._name

    def group(self):
        return self._groupid

    def append(self, location):
        self._locations.append(location)

    def locations(self):
        return self._locations

    def getlocation(self, name):
        for loc in self._locations:
            if loc.name() == name:
                return loc

        return None

    def children(self):
        return self._children

    def unique(self):
        return self._unique

    def parent(self):
        return self._parent

    def parametrized(self):
        return self._parametrized

    def hasParametrized(self):
        for child in self._children:
            if child.parametrized():
                return True

        for loc in self._locations:
            if loc.parametrized():
                return True

        return False

    def addsubgroup(self, group):
        # TODO: refactor this to make unique locations protection available
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
                    self.lineno = self.lineno + 1
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
                        self.lineno = self.lineno + 1
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
                        self.lineno = self.lineno + 1
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
        lexer.wordchars += '.():'

        return list(lexer)

    def groups(self):
        """Get groups parsed from configuration file

        :return: list of groups keys
        """
        return self._groups.values()

    def getgroup(self, name):

        def findgroup(name, group):
            for g in group.children():
                if len(g.children()) > 0:
                    return findgroup(name, g)

                if g.name() == name:
                    return g

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
                                # begin of the unique group/end of previous
                                if tokens[1] in self._groups:
                                    if self._groups[tokens[1]].unique():
                                        raise ParseError(_("Has the same unique group %s") % tokens[1])

                                if currentGroup is not None:
                                    grp = YAPLCGroup(tokens[1], tokens[2], (tokens[0] == 'UGRP'), currentGroup)
                                    currentGroup.addsubgroup(grp)
                                else:
                                    grp = YAPLCGroup(tokens[1], tokens[2], (tokens[0] == 'UGRP'))
                                    self.addgroup(grp)  # also add to flat root groups table

                                currentGroup = grp

                            elif tokens[0] == 'LOC' or tokens[0] == 'ULOC':
                                # non-unique location description
                                if currentGroup is None:
                                    raise ParseError(_("Location %s without group") % tokens[0])
                                if currentGroup.unique():
                                    loc = YAPLCLocation(tokens[1], currentGroup.group(),
                                                        (tokens[0] == 'ULOC'), *tokens[2:])
                                else:
                                    # non-unique group could have no GID and parameters only
                                    loc = YAPLCLocation(tokens[1], currentGroup.parent().group(),
                                                        (tokens[0] == 'ULOC'), *tokens[2:])
                                currentGroup.append(loc)

                            elif tokens[0] == 'ENDGRP':
                                # close current group and try to return to parent group
                                if currentGroup is None:
                                    raise ParseError(_("Illegal end of group"))

                                currentGroup = currentGroup.parent()

                            else:
                                pass

                    if currentGroup is not None:
                        raise ParseError(_("Group %s has not been closed properly!") % currentGroup.name())

            except IOError:
                raise ParseError(_("No template file for current target"))


if __name__ == '__main__':
    parser = YAPLCConfigParser()
    path = os.path.join(os.path.dirname(__file__),
                        '..', 'yaplctargets', 'yaplcThree',
                        r'extensions.cfg')
    parser.fparse(path)

    for grp in parser.groups():
        print grp
        print grp.locations()
