#!/usr/bin/env python3
# Copyright © 2015 Andrew Wilcox and Elizabeth Myers.
# All rights reserved.
# This file is part of the PyIRC3 project. See LICENSE in the root directory
# for licensing information.


from collections.abc import Mapping
from functools import partial

from PyIRC.base import BaseExtension, EVENT_DISCONNECTED
from PyIRC.numerics import Numerics


class Autojoin(BaseExtension):

    """ Autojoin a bunch of channels, with some throttle """

    def __init__(self, base, **kwargs):
        """ Initialise the autojoin extension

        Keyword arguments:
        - join - a mapping or list of channels to join, if a mapping, the keys
          are the channels and the values are the channel keys
        - autojoin_wait_start - how much time to wait for autojoin to begin
        - autojoin_wait_interval - how long to wait between joins
        """

        self.base = base

        self.commands = {
            Numerics.RPL_WELCOME : self.autojoin,
        }

        self.hooks = {
            EVENT_DISCONNECTED : self.close,
        }

        self.join_dict = kwargs['join']

        # If a list is passed in for join_dict, we will use a comprehension
        # to set null keys
        if not isinstance(self.join_dict, Mapping):
            self.join_dict = {channel : None for channel in self.join_dict}

        # Should be sufficient for end of MOTD
        self.wait_start = kwargs.get('autojoin_wait_start', 0.75)

        # Default is 4 per second
        self.wait_interval = kwargs.get('autojoin_wait_interval', 0.25)

        # Used for unexpected disconnect
        self.sched = []

    def do_join(self, params):
        self.send("JOIN", params)
        self.sched.pop(0)

    def autojoin(self, line):
        # Should be sufficient for end of MOTD and such
        t = self.wait_start

        for channel, key in self.join_dict.items():
            if key is None:
                params = [channel]
            else:
                params = [channel, key]

            sched = self.schedule(t, partial(self.do_join, params))
            self.sched.append(sched)

            t += self.wait_interval

    def close(self):
        for sched in self.sched:
            try:
                self.unschedule(sched)
            except ValueError:
                pass

        self.sched.clear()
