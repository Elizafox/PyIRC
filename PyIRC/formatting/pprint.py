# Copyright © 2015 Andrew Wilcox and Elizabeth Myers.
# All rights reserved.
# This file is part of the PyIRC 3 project. See LICENSE in the root directory
# for licensing information.


"""'Pretty' printer for IRC messages.

This module contains a mixin,
:py:class:`~PyIRC.formatting.pprint.PrettyPrintedIRC`, that integrates with I/O
backends to display messages flowing in and out in a way pleasing to the eye on
most ANSI-compatible terminals.

"""

from datetime import datetime
import os

from PyIRC.base import IRCBase
from PyIRC.formatting.formatters import ANSIFormatter, XTerm256ColourFormatter
from PyIRC.line import Hostmask
from PyIRC.numerics import Numerics
from PyIRC.signal import event


class PrettyPrintedIRCMixin(IRCBase):
    """Pretty print lines sent and received."""
    # pylint: disable=abstract-method

    def _printf(self, msg):
        """Print formatted messages.

        Am I writing C yet?

        :param msg:
            The message.
        """

        # Why + \x0f?  Because we want to make sure formatting that is
        # improperly terminated doesn't affect further lines.
        print(self._pp_formatter.format(msg + "\x0f"))

    def nick_colour(self, nick):
        """Colourise a nick."""
        colours = [10, 6, 3, 5, 12, 14, 11, 13, 9, 2]
        colour = sum(ord(char) for char in nick) % len(colours)
        formatted = "\x03{},1{}\x0f".format(colours[colour], nick)
        return self._pp_formatter.format(formatted)

    @event("commands", "PRIVMSG")
    @event("commands", "NOTICE")
    def msg(self, _, line):
        """Handle PRIVMSG and NOTICE."""
        mask = line.hostmask
        if mask.nick:
            nick = mask.nick
        elif mask.host:
            # This is for server-sent messages.  For example, the NOTICE
            # sent before registration, or any oper snotes.
            nick = mask.host
        else:
            nick = str(mask)  # give up

        # target of NOTICE/PRIVMSG is always the first param
        target = line.params[0]

        # format nick based on NOTICE or PRIVMSG
        if line.command.upper() == 'NOTICE':
            nickstr = "-{nick}-"
        else:
            nickstr = "<{nick}>"
        nickstr = nickstr.format(nick=self.nick_colour(nick))

        # message is always last param
        message = line.params[-1]

        self._printf("[{}] {} {}".format(target, nickstr, message))

    @event("commands", "JOIN")
    def join(self, _, line):
        """Handle the JOIN line."""
        joiner = self.nick_colour(line.hostmask.nick)

        if joiner is None:
            # a server can't really join a room itself, so something's wrong
            return

        target = line.params[0]

        self._printf("*** {} has joined {}".format(joiner, target))

    @event("commands", "PART")
    def part(self, _, line):
        """Handle a PART line."""
        parter = self.nick_colour(line.hostmask.nick)

        if len(line.params) > 0:
            reason = ' ({})'.format(line.params[-1])
        else:
            reason = ''

        target = line.params[0]

        self._printf("*** {} has left {}{}".format(parter, target, reason))

    @event("commands", "KICK")
    def kick(self, _, line):
        """Handle a KICK line."""
        flats = self.nick_colour(line.hostmask.nick)
        victim = self.nick_colour(line.params[1])

        if len(line.params) > 1:
            reason = ' ({})'.format(line.params[-1])
        else:
            reason = ''

        target = line.params[0]

        msg = "*** {} has been KICKED from {} by {}{}".format(victim, target,
                                                              flats, reason)
        self._printf(msg)

    @event("commands", "QUIT")
    def quit(self, _, line):
        """Handle a QUIT line."""
        if len(line.params) > 0:
            okbye = ' ({})'.format(line.params[-1])
        else:
            okbye = ''

        target = line.hostmask.nick

        self._printf("*** {} has left IRC{}".format(target, okbye))

    @event("commands", Numerics.RPL_MOTDSTART)
    @event("commands", Numerics.RPL_MOTD)
    def motd(self, _, line):
        """Handle MOTD"""
        self._printf("MOTD: {}".format(line.params[-1]))

    @event("commands", Numerics.RPL_ENDOFMOTD)
    def motd_end(self, _, line):
        """Handle end of MOTD"""
        # pylint: disable=unused-argument
        self._printf("End of MOTD")

    @event("commands", Numerics.RPL_MYINFO)
    def my_info(self, _, line):
        """Show the server name and version."""
        if len(line.params) < 3:
            return

        server = self.nick_colour(line.params[1])
        version = "\x02{}\x02".format(line.params[2])

        self._printf("Connected to {} (running {}).".format(server, version))

    @event("commands", Numerics.RPL_TOPIC)
    @event("commands", "TOPIC")
    def topic(self, _, line):
        """We have a topic :)"""
        if line.command.lower() == "topic":
            channel = line.params[0]
            person = self.nick_colour(line.hostmask.nick)
            fmt = "*** {person} set topic of {channel} to: {topic}"
        else:
            channel = line.params[1]
            person = None
            fmt = "*** Topic of {channel} is: {topic}"

        topic = self._pp_formatter.format(line.params[-1])
        self._printf(fmt.format(channel=channel, person=person, topic=topic))

    @event("commands", Numerics.RPL_NOTOPIC)
    def no_topic(self, _, line):
        """We don't have a topic :("""
        channel = line.params[1]
        self._printf("*** Topic of {} is not set.".format(channel))

    @event("commands", Numerics.RPL_TOPICWHOTIME)
    def topic_details(self, _, line):
        """Show the details of a topic."""
        channel = line.params[1]
        setter = self.nick_colour(Hostmask.parse(line.params[2]).nick)
        set_on = str(datetime.utcfromtimestamp(int(line.params[3])))
        self._printf("*** Topic of {} set by {} on {}.".format(channel, setter,
                                                               set_on))

    @event("commands", Numerics.RPL_ENDOFNAMES)
    def maybe_show_names(self, _, line):
        """Show the nicks on a channel, if ChannelTrack is loaded."""
        channel = line.params[1]

        if 'ChannelTrack' not in self.extensions:
            return
        if channel not in self.extensions['ChannelTrack'].channels:
            return

        chan = self.extensions['ChannelTrack'].get_channel(channel)
        users = [n for n in chan.users.keys()]
        users.sort()
        userstr = ', '.join(self.nick_colour(str(nick)) for nick in users)
        self._printf("*** Chatting on {}: [{}]".format(channel, userstr))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'xterm' in os.environ.get('TERM', 'vt100').lower():
            self._pp_formatter = XTerm256ColourFormatter()
        else:
            self._pp_formatter = ANSIFormatter()
        self._pp_in_str = self._pp_formatter.format("\x036,1-->\x0f ")
        self._pp_out_str = self._pp_formatter.format("\x036,1<--\x0f ")

        self.handled = set()

        for slot in self.signals.get_bound(self):
            (hclass, event_name) = slot.signal.name
            if hclass != 'commands':
                continue
            self.handled.add(event_name)

        self.ignored = {'001', '002', '003', '005',  # Welcome crap
                        # Absolutely nobody cares
                        'CAP', 'PONG',
                        # WHOIS crap
                        '276', '307', '308', '309', '310', '311', '312', '313',
                        '316', '317', '318', '319', '320', '330', '335', '337',
                        '338', '343', '378', '379', '671', '672',
                        # I cannae imagine the tosser who would want to pretty
                        # print WHO.
                        '354', '315',
                        # we don't care about the actual NAMES reply...
                        # we will use ENDOFNAMES if ChannelTrack is loaded.
                        '353',}

    def recv(self, line):
        if line.command not in self.handled | self.ignored:
            formatted = self._pp_in_str

            if line.command.isnumeric() and len(line.command) == 3:
                cmd = '{} [{}]'.format(Numerics(line.command).name,
                                       line.command)
            else:
                cmd = line.command

            if cmd.startswith("ERR_"):
                formatted += "\x02\x034,1!!!\x03 {}\x0f ".format(cmd)
            else:
                formatted += cmd + ' '

            formatted += ' '.join(line.params)
            self._printf(formatted)
        return super().recv(line)
