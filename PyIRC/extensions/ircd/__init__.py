from collections import namedtuple


__all__ = ["base"]


Extban = namedtuple("Extban", "ban target")
"""A parsed extban."""


BanEntry = namedtuple("BanEntry", "mask setter duration reason")
"""A result from a ban lookup"""
