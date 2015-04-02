#!/usr/bin/env python3
# Copyright © 2015 Andrew Wilcox and Elizabeth Myers.
# All rights reserved.
# This file is part of the PyIRC3 project. See LICENSE in the root directory
# for licensing information.

from abc import ABCMeta, abstractmethod
from collections import defaultdict
from operator import itemgetter
from logging import getLogger

from numerics import Numerics
from line import Line


PRIORITY_DONTCARE = 0
PRIORITY_FIRST = -1
PRIORITY_LAST = 1


EVENT_OK = None  # default
EVENT_CANCEL = 1  # End processing
EVENT_TERMINATE_SOON = 2  # Disconnect
EVENT_TERMINATE_NOW = 3  # Quit


EVENT_CONNECTED = 1  # Connected to server
EVENT_DISCONNECTED = 2  # Disconnected


logger = getLogger(__name__)


class BaseExtension:

    priority = PRIORITY_DONTCARE

    def __init__(self, base, **kwargs):
        self.base = base
    
        self.implements = {}
        self.hooks = {}


class BasicRFC(BaseExtension):
    """ Basic RFC1459 doodads """

    priority = PRIORITY_FIRST

    def __init__(self, base, **kwargs):
        self.base = base

        self.implements = {
            "NOTICE" : self.connected,
            "PING" : self.pong,
            Numerics.RPL_WELCOME : self.welcome,
        }

        self.hooks = {
            EVENT_CONNECTED : self.handshake,
            EVENT_DISCONNECTED : self.disconnected,
        }

    def connected(self, line):
        self.base.connected = True

    def handshake(self):
        self.base.send("USER", [self.base.user, "*", "*", self.base.gecos])
        self.base.send("NICK", [self.base.nick])

    def disconnected(self):
        self.base.connected = False

    def pong(self, line):
        self.base.send("PONG", line.params)

    def welcome(self, line):
        self.base.registered = True
    

class IRCBase(metaclass=ABCMeta):

    """ The base IRC class meant to be used as a base for more concrete
    implementations. """

    def __init__(self, serverport, user, nick, gecos, extensions, **kwargs):
        """ Initialise the IRC base.

        Arguments:
        - serverport - server/port combination, like passed to socket.connect
        - user - username to send to the server (identd may override this)
        - nick - nickname to use
        - extensions - list of default extensions to use (BasicRFC recommended)
        
        Keyword arguments:
        - ssl - whether or not to use SSL
        - other extensions may provide their own
        """

        self.server, self.port = serverport
        self.user = user
        self.nick = nick
        self.gecos = gecos
        self.ssl = kwargs.get("ssl", False)

        self.extensions = list(extensions)

        self.kwargs = kwargs
        
        # Basic state
        self.connected = False
        self.registered = False
        
        self.build_dispatch_cache()

    def build_dispatch_cache(self):
        """ Enumerate present extensions and build the dispatch cache.
        
        You should only need to call this method if you modify the extensions
        list.
        """

        self.hooks = defaultdict(list)
        self.dispatch = defaultdict(list)
        self.extensions_inst = []

        for order, e in enumerate(self.extensions):
            extinst = e(self, **self.kwargs)

            self.extensions_inst.append(extinst)
            
            logger.info("Loading extension: %s", extinst.__class__.__name__)

            priority = extinst.priority

            for command, callback in extinst.implements.items():
                if isinstance(command, Numerics):
                    command = command.value

                command = command.lower()

                self.dispatch[command].append([priority, order, callback])
                self.dispatch[command].sort()
                
                logger.debug("Command callback added: %s", command)

            for hook, callback in extinst.hooks.items():
                self.hooks[hook].append([priority, order, callback])
                self.hooks[hook].sort()

                logger.debug("Hook callback added: %s", command)
            
            logger.info("Loaded extension: %s", extinst.__class__.__name__)

    def connect(self):
        """ Do the connection handshake """

        for hook in self.hooks[EVENT_CONNECTED]:
            hook[2]()

    def close(self):
        """ Do the connection teardown """

        for hook in self.hooks[EVENT_DISCONNECTED]:
            hook[2]()

    def recv(self, line):
        """ Receive a line """

        command = line.command.lower()

        fnlist = self.dispatch[command]
        if not fnlist:
            return

        for fn in fnlist:
            ret = fn[2](line)
            if ret == EVENT_CANCEL:
                return
            elif ret == EVENT_TERMINATE_SOON:
                self.send("QUIT", ["Plugin requested termination"])
                return
            elif ret == EVENT_TERMINATE_NOW:
                # FIXME - maybe should raise?
                quit()

    @abstractmethod
    def send(self, command, params):
        """ Send a line """

        return Line(command=command, params=params)

    @abstractmethod
    def schedule(self, time, callback):
        raise NotImplementedError()
