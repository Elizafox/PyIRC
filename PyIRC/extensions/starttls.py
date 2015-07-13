#!/usr/bin/env python3
# Copyright © 2015 Andrew Wilcox and Elizabeth Myers.
# All rights reserved.
# This file is part of the PyIRC 3 project. See LICENSE in the root directory
# for licensing information.


"""Automatic SSL negotiation.

It's a little like the ESMTP STARTTLS command, but the server does not
forget all of the client state after it is issued. Therefore, it should
be issued as quickly as possible.

"""


from logging import getLogger

from taillight.signal import Signal, SignalDefer

from PyIRC.extension import BaseExtension
from PyIRC.numerics import Numerics


_logger = getLogger(__name__)


class StartTLS(BaseExtension):

    """Support for the STARTTLS extension.

    Not all I/O backends support this, notably :py:class:`~PyIRC.io.asyncio`.

    """

    requires = ["CapNegotiate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.tls_event = None

        if not self.ssl:
            self.caps = {
                "tls": [],
            }

    @Signal(("hooks", "disconnected")).add_wraps()
    def close(self, caller):
        self.tls_event = None

    @Signal(("cap_perform", "ack")).add_wraps(priority=-1000)
    def starttls(self, caller, caps):
        # This must come before anything else in the chain
        if self.ssl:
            # Unnecessary
            return

        if self.tls_event:
            return

        if "tls" in caps:
            self.tls_event = event
            self.send("STARTTLS", None)
            raise SignalDefer()

    @Signal(("commands", Numerics.RPL_STARTTLS)).add_wraps()
    def wrap(self, caller, line):
        _logger.info("Performing STARTTLS initiation...")
        self.wrap_ssl()

        cap_negotiate = self.base.cap_negotiate
        signal = Signal(("cap_perform", "ack"))
        if signal.last_status == signal.STATUS_DEFER:
            self.call_event("cap_perform", "ack")

    @Signal(("commands", Numerics.ERR_STARTTLS)).add_wraps()
    def abort(self, caller, line):
        _logger.critical("STARTTLS initiation failed, connection not secure")

        cap_negotiate = self.base.cap_negotiate
        signal = Signal(("cap_perform", "ack"))
        if signal.last_status == signal.STATUS_DEFER:
            self.call_event("cap_perform", "ack")
