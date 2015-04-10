#!/usr/bin/env python3
# Copyright © 2015 Andrew Wilcox and Elizabeth Myers.
# All rights reserved.
# This file is part of the PyIRC 3 project. See LICENSE in the root directory
# for licensing information.


from logging import getLogger

from PyIRC.extension import BaseExtension, hook


logger = getLogger(__name__)


class ServicesLogin(BaseExtension):

    """ Support services login.

    Use of this module is discouraged. Use the SASL module if at all
    possible. It is not possible to know if our authentication was
    a success or failure, because services may use any string to report
    back authentication results, and they are often localised depending on
    IRC network.

    It also creates a security hole, as you can never be 100% sure who or
    what you're talking to (though some networks support a full nick!user@host
    in the target to message a user).
    """

    def __init__(self, base, **kwargs):
        """ Initalise the module.

        Arguments:
            services_username: the username to use for authentication.
            services_password: the password to use for authentication.
            services_idenitfy_fmt: a format string using {username} and
                {password} to send the correct message to services.
            services_bot: The user to send authentication to (defaults to
                NickServ). Can be a full nick!user@host set for the networks
                that support or require this mechanism.
        """

        self.base = base

        self.username = kwargs.get("services_username", self.base.nick)
        password = kwargs["services_password"]  # Not for attr storage!

        # Usable with atheme and probably anope
        self.identify = kwargs.get("services_identify_fmt",
                                   "IDENTIFY {username} {password}")

        self.services_bot = kwargs.get("services_bot", "NickServ")

        # Cache format string
        self.identify = self.identify.format(username=self.username,
                                             password=password)

        self.authenticated = False

    @hook("commands", "NOTICE")
    @hook("commands", "PRIVMSG")
    def authenticate(self, event):
        if self.authenticated or not self.base.registered:
            return

        logger.debug("Authenticating to services bot %s with username %s",
                     self.services_bot, self.username)
        self.send("PRIVMSG", [self.services_bot, self.identify])

        # And STAY out! ;)
        self.authenticated = True

