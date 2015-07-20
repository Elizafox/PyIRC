# Copyright © 2013-2015 Elizabeth Myers.  All rights reserved.
# This file is part of the PyIRC 3 project. See LICENSE in the root directory
# for licensing information.


""" Parsing for various IRC mini-languages.

IRC has a mini-language/grammar fetish and uses them extensively to compensate
for the fact that RFC1459 frames are deficient, to be excessively generous.

This module has various parsers for some of them (by no means exhaustive - and
that's probably not even possible, given everyone and their dog seems to love
inventing new ones for no discernible reason).

Hopefully one day this module will disappear, when IRC gets a sane framing
format. Until that day comes, this needs to be here.
"""


from collections import namedtuple
from functools import lru_cache
from logging import getLogger
from string import ascii_letters, digits
from types import SimpleNamespace

import re

from PyIRC.line import Line, Hostmask


_logger = getLogger(__name__)


prefix_match = re.compile(r"\(([A-Za-z0-9]+)\)(.+)")
numletters = ascii_letters + digits


@lru_cache(maxsize=16)
def _extban_compile(char, extbans):
    # TODO - inspircd chained extbans (BLEH)
    return re.compile("{char}([{extbans}]):(.*)".format(**locals()))


def extban_parse(string, supported_extban):
    reg = _extban_compile(*supported_extban)
    match = reg.match(string)
    return match.groups() if match else None


def banmask_parse(string, supported_extban):
    """Normalise a ban mask into either an extban or nick!user@host set"""
    ret = SimpleNamespace()
    ret.nick = ret.user = ret.host = None

    extban = extban_parse(string, supported_extban)
    if extban:
        # Unpack
        ret.extban, ret.extban_target = extban
        return ret

    ret.extban = ret.extban_target = None

    try:
        hostmask = Hostmask.parse(string)
    except Exception:
        return ret

    if not hostmask:
        return ret

    ret.nick, ret.user, ret.host = (hostmask.nick, hostmask.username,
                                    hostmask.host)
    return ret


ParsedPrefix = namedtuple("ParsedPrefix", "mode_to_prefix prefix_to_mode")


@lru_cache(maxsize=16)
def prefix_parse(prefix):
    """Parse ISUPPORT PREFIX extension into mode : prefix and vice versa.

    :param prefix:
        Prefix string to parse (e.g., ``(ov)@+``)

    .. note::
        If prefix and modes are not properly balanced, ``ValueError`` will be
        raised.

    >>> [sorted(p.items()) for p in prefix_parse("(ov)@+")]
    [[('o', '@'), ('v', '+')], [('+', 'v'), ('@', 'o')]]
    >>> [sorted(p.items()) for p in prefix_parse("(qahov)~&%@+")]
    ... # doctest: +ELLIPSIS
    [[('a', '&'), ..., ('~', 'q')]]
    >>> prefix_parse("(ov)@+")[1]["@"]
    'o'
    >>> prefix_parse("(ov)@+")[0]["o"]
    '@'
    >>> prefix_parse("(o)@+")
    Traceback (most recent call last):
        ...
    ValueError: Unbalanced modes and prefixes
    """
    ret = ParsedPrefix(dict(), dict())

    match = prefix_match.match(prefix)
    if not match:
        return ret

    modes, values = match.groups()
    if len(modes) != len(values):
        raise ValueError("Unbalanced modes and prefixes")

    for k, v in zip(modes, values):
        ret.mode_to_prefix[k] = v
        ret.prefix_to_mode[v] = k

    return ret


def mode_parse(modes, params, modegroups, prefix):
    """Parse IRC mode strings.

    A generator that yields (modechar, param, adding).  param may be `None`.
    `adding` will either be `True` or `False`, depending on what is happening
    to the mode.

    :param modes:
        Initial string of modes (should resemble +blah/-blah or some such).

    :param params:
        Parameters for the modes, likely the remaining parameters after modes.

    :param modegroups:
        The item from the isupport string CHANMODES.

    :param prefix:
        The mode prefixes from the isupport string PREFIX, optionally parsed
        by prefix_parse.

    >>> modegroups = ("beIq", "k", "flj", "ac")
    >>> prefixmodes = "(ov)@+"
    >>> f = lambda x: [(char, param, adding) for char, param, adding in x]
    >>> f(mode_parse("+oba", ("a", "b"), modegroups, prefixmodes))
    [('o', 'a', True), ('b', 'b', True), ('a', None, True)]
    >>> f(mode_parse("+o-o", ("a", "a"), modegroups, prefixmodes))
    [('o', 'a', True), ('o', 'a', False)]
    >>> f(mode_parse("+k-k", ("test",), modegroups, prefixmodes))
    [('k', 'test', True), ('k', None, False)]
    >>> f(mode_parse("+bf-k+b", ("a", "b", "c"), modegroups, prefixmodes))
    [('b', 'a', True), ('f', 'b', True), ('k', None, False), ('b', 'c', True)]
    >>> prefixmodes = prefix_parse(prefixmodes)
    >>> f(mode_parse("+ov-v", ("a", "b", "c"), modegroups, prefixmodes))
    [('o', 'a', True), ('v', 'b', True), ('v', 'c', False)]

    """
    if isinstance(prefix, ParsedPrefix):
        prefix = prefix.mode_to_prefix
    else:
        prefix = prefix_parse(prefix).mode_to_prefix

    params = list(params)

    status = ''.join(mode for mode in prefix if mode in ascii_letters)

    # Groups of modes
    group_pop_add = modegroups[0] + modegroups[1] + modegroups[2] + status
    group_pop_remove = modegroups[0] + modegroups[2] + status

    adding = True
    group = group_pop_add
    for char in modes:
        if char == '+':
            adding = True
            group = group_pop_add
            continue
        elif char == '-':
            adding = False
            group = group_pop_remove
            continue

        param = None
        if char in group:
            param = params.pop(0)

        yield (char, param, adding)


def status_prefix_parse(string, prefix):
    """Parse a string containing status sigils.

    :param string:
        Nick or channel containing leading sigils.

    :param prefix:
        The mode prefixes from ISupport.supported['PREFIX'], optionally parsed
        by :py:func:`prefix_parse`.

    :returns: (status, string) tuple, where `status` is a set of the statuses.
              `string` is the string with all leading status sigils removed.

    >>> status_prefix_parse("@#channel", "(ov)@+")
    ({'o'}, '#channel')
    >>> status_prefix_parse("+#ch@nnel", "(ov)@+")
    ({'v'}, '#ch@nnel')
    >>> status_prefix_parse("+#", "(ov)@+")
    ({'v'}, '#')
    >>> modes, channel = status_prefix_parse("@+#", "(ov)@+")
    >>> sorted(modes), channel
    (['o', 'v'], '#')

    """
    if isinstance(prefix, ParsedPrefix):
        prefix = prefix.prefix_to_mode
    else:
        prefix = prefix_parse(prefix).prefix_to_mode

    modes = set()

    while string[0] in prefix:
        prefix_char, string = string[0], string[1:]
        modes.add(prefix[prefix_char])
    return (modes, string)


@lru_cache(maxsize=32)
def who_flag_parse(flags):
    """Parse WHO flags.

    :param flags:
        Flags to parse.

    :returns:
        A namespace object containing the following attributes:

        :operator:
            Whether or not the user is an operator.

        :away:
            Whether or not the user is away.

        :modes:
            A set of the user's present modes (prefixes).

    """
    ret = SimpleNamespace(operator=False, away=False, modes=set())
    ret.operator = False

    for char in flags:
        if char == '*':
            ret.operator = True
        elif char == "G":
            ret.away = True
        elif char == "H":
            ret.away = False
        elif char not in numletters:
            ret.modes.add(char)
        else:
            _logger.debug("No known way to handle WHO flag %s", char)

    return ret


@lru_cache(maxsize=128)
def userhost_parse(mask):
    """Parse a USERHOST reply.

    :returns:
        An object with the following attributes set:

        :hostmask:
            :py:class:`~PyIRC.line.Hostmask` of the user. This may be a cloak.

        :operator:
            Whether or not the user is an operator. False does not mean they
            are not an operator, as operators may be hidden on the server.

        :away:
            Whether or not the user is away.

    """
    if not mask:
        raise ValueError("Need a mask to parse")

    ret = SimpleNamespace(hostmask=None, operator=None, away=None)

    nick, sep, userhost = mask.partition('=')
    if not sep:
        return ret

    if nick.endswith('*'):
        nick = nick[:-1]
        ret.operator = True

    if userhost.startswith(('+', '-')):
        away, userhost = userhost[0], userhost[:1]
        ret.away = (away == '+')

    # user@host
    username, sep, host = userhost.partition('@')
    if not sep:
        host = username
        username = None

    ret.hostmask = Hostmask(nick=nick, username=username, host=host)

    return ret


def isupport_parse(params):
    """Parse an ISUPPORT string into a dictionary. Uses the params derived
    from line :py:attr:`~PyIRC.line.Line.params`.

    >>> isupport_parse(["CHANTYPES=a,b,cdefg"])
    {'CHANTYPES': ('a', 'b', 'cdefg')}
    >>> isupport_parse(["EXCEPTS"])
    {'EXCEPTS': True}
    >>> isupport_parse(["PREFIX=(ov)@+"])
    {'PREFIX': '(ov)@+'}
    >>> isupport_parse(["EXTBAN=,ABCNOQRSTUcjmprsz"])
    {'EXTBAN': ('', 'ABCNOQRSTUcjmprsz')}
    >>> isupport_parse(["MAXLIST=ACCEPT:5"])
    {'MAXLIST': {'ACCEPT': '5'}}
    >>> sorted(isupport_parse(["MAXLIST=ACCEPT:,TEST:5"])["MAXLIST"].items())
    [('ACCEPT', None), ('TEST', '5')]
    >>> sorted((k,v) for k, v in isupport_parse(["EXCEPTS", "INVEX"]).items())
    [('EXCEPTS', True), ('INVEX', True)]
    """
    supported = dict()

    for param in params:
        # Split into key : value pair
        key, _, value = param.partition('=')

        if not value:
            _logger.debug("ISUPPORT [k]: %s", key)
            supported[key] = True
            continue

        # Split values into CSV's
        # For each CSV, parse into pairs of val : data
        ret_dict = {}
        ret_list = []
        for v in value.split(','):
            val, sep, data = v.rpartition(':')
            if sep:
                if not data:
                    data = None

                ret_dict[val] = data
            else:
                ret_list.append(data)

        ret_list = tuple(ret_list)
        if len(ret_list) == 1:
            # No use in having a list.
            ret_list = ret_list[0]

        if ret_dict:
            if ret_list:
                # This case should be rare if not nonexistent.
                supported[key] = (ret_dict, ret_list)
            else:
                supported[key] = ret_dict
        elif ret_list:
            supported[key] = ret_list
        else:
            supported[key] = True

        _logger.debug("ISUPPORT [k:v]: %s:%r", key, supported[key])

    return supported


class CTCPMessage:

    r"""Represent a CTCP message.

    >>> CTCPMessage("PRIVMSG", "PING", "#Sporks", "lol")
    ... # doctest: +ELLIPSIS
    CTCPMessage(...='PRIVMSG', ...='PING', ...='#Sporks', ...='lol')
    >>> CTCPMessage("PRIVMSG", "PING", "#Sporks", "lol").line
    ... # doctest: +ELLIPSIS
    Line(..., command='PRIVMSG', params=['#Sporks', '\x01PING lol\x01'])
    >>> line = Line(tags=None, hostmask=None, command='PRIVMSG',
    ... params=['#test', '\x01TEST TEST\x01'])
    >>> CTCPMessage.parse(line)
    ... # doctest: +ELLIPSIS
    CTCPMessage(msgtype='PRIVMSG', ...='TEST', ...='#test', param='TEST')
    """

    __slots__ = ('msgtype', 'command', 'target', 'param')

    def __init__(self, msgtype, command, target, param):
        """Initalise the CTCPMessage instance.

        :param msgtype:
            The type of message received, either PRIVMSG or NOTICE.

        :param command:
            The CTCP command used (e.g., PING, TIME, VERSION).

        :param target:
            The target of this given CTCP request or response.

        :param param:
            The param(s) of the CTCP message, with no parsing attempted.

        """
        self.msgtype = msgtype
        self.command = command
        self.target = target
        self.param = param

    @classmethod
    def parse(cls, line):
        """Return a new :py:class:`~PyIRC.auxparse.CTCPMessage` from
        the :py:class:`~PyIRC.line.Line` instance specified.
        """
        message = line.params[1]

        if not message.startswith("\x01") or not message.endswith("\x01"):
            return None

        message = message[1:-1]  # chop off \x01 at beginning and end
        (command, _, param) = message.partition(' ')
        param = param.strip()
        if not param:
            param = None

        if not line.hostmask or not line.hostmask.nick:
            target = line.params[0]
        else:
            target = line.hostmask.nick

        return cls(line.command.upper(), command.upper(), target, param)

    @property
    def line(self):
        """Return a :py:class:`~PyIRC.line.Line` instance representing this
        CTCP message"""
        message = '\x01{} {}\x01'.format(self.command, self.param)
        return Line(command=self.msgtype, params=[self.target, message])

    def __repr__(self):
        return "CTCPMessage(msgtype={}, command={}, target={}, " \
            "param={})".format(repr(self.msgtype), repr(self.command),
                               repr(self.target), repr(self.param))
