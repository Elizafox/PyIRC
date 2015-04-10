#!/usr/bin/env python3
# Copyright © 2015 Andrew Wilcox and Elizabeth Myers.
# All rights reserved.
# This file is part of the PyIRC 3 project. See LICENSE in the root directory
# for licensing information.


"""Enumeration of IRC server features and extensions

ISUPPORT is a non-standard but widely supported IRC extension that is used to
advertise what a server supports to a client. Whilst non-standard, most
servers follow a standard format for many parameters.

The following should be safe:

- CHANTYPES (value is a string)
- PREFIX (value is of format "(modes)symbols for modes")
- NETWORK (value is a string)
- CASEMAPPING (ascii or rfc1459)
- CHANMODES (list of values enumerating modes into four distinct classes,
  respectively: list modes, modes that send a parameter, modes that send a
  parameter only when set, and parameterless modes)

The following are common but not guaranteed:

- INVEX (no parameters)
- EXCEPTS (no parameters)
- TARGMAX (command:targets,command2:targets2,...)
- EXTBAN (a string, "prefix,extban prefixes")
"""


from logging import getLogger

from PyIRC.extension import BaseExtension, hook
from PyIRC.numerics import Numerics
from PyIRC.auxparse import isupport_parse


logger = getLogger(__name__)


class ISupport(BaseExtension):

    """ Parse ISUPPORT attributes into useful things.

    Parsing is done according to auxparse.isupport_parse semantics.

    The following attributes are available:

    supported
        parsed ISUPPORT data from the server. Do note that because ISUPPORT is
        technically non-standard, users should be prepared for data that does
        not conform to any implied standard.
    """

    def __init__(self, base, **kwargs):
        self.base = base

        # State
        self.supported = {}

    @hook("hooks", "disconnected")
    def close(self, event):
        self.supported.clear()

    @hook("commands", Numerics.RPL_ISUPPORT)
    def isupport(self, event):
        """ Handle ISUPPORT event """

        # To differentiate between really old ircd servers
        # (RPL_BOUNCE=005 on those)
        if not event.line.params[-1].endswith('server'):
            logger.warning("Really old IRC server detected!")
            logger.warning("It's probably fine but things might break.")
            return

        values = event.line.params[1:-1]
        self.supported.update(isupport_parse(values))

