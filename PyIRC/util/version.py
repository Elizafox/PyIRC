# Copyright © 2013-2019 A. Wilcox and Elizabeth Myers.
# All rights reserved.
# This file is part of the PyIRC3 project. See LICENSE in the root directory
# for licensing information.


"""PyIRC version information."""


try:
    import pkg_resources
except ImportError:
    pkg_resources = None

import subprocess

from collections import namedtuple


def _gitversion():
    """Determine the current git checkout, if any."""
    try:
        command = ["git", "log", "-1", "--pretty=format:%h"]
        return subprocess.check_output(command).decode()
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


MAJOR = 3
MINOR = 2
STATUS = "beta"
GITVERSION = _gitversion()

VersionType = namedtuple("Version", "major minor status gitversion")


VERSION = VersionType(MAJOR, MINOR, STATUS, GITVERSION)
""" Current PyIRC version

Attributes:
    major: Current major version. Set to 3 for PyIRC 3.
    minor: Current minor version.
    status: Release status (alpha, beta, release)
    gitversion: Current git revision, may be set to "unknown"
"""


def _versionstr():
    """Create the version string from the current parameters."""
    try:
        req = pkg_resources.require("PyIRC")  # pylint: disable=not-callable
        return req[0].version
    except pkg_resources.DistributionNotFound:
        return "{major}.{minor}-{status[0]}[{gitversion}]".format(**globals())


VERSIONSTR = _versionstr()
"""Current PyIRC version string. Obtained from the package whenever
possible, but may be generated from constants.

.. warning::
    Do not rely on this format remaining stable, use
    :py:data::`~PyIRC.util.version.version` instead!
"""
