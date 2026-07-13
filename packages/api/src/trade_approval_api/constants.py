"""Shared string constants for the API layer.

Only strings that are referenced in more than one place (or must stay in sync
across code and tests) live here; one-off literals stay inline where they read
more clearly.
"""
USER_ID_HEADER = "X-User-Id"


TRADES_PREFIX = "/trades"
