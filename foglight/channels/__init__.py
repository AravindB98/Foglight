"""Channel registry bootstrap.

Importing this package registers every shipped channel. The ``mock`` channel
(offline sample data) always registers so the system runs with zero setup;
the rest register but report ``check() == False`` until their tool, key or
cookie is available, so `foglight doctor` can show an honest status board.
"""

from .base import Channel, register, get, all_channels, search  # noqa: F401

# Importing each module triggers its @register decorator.
from . import mock      # noqa: F401  (always available, offline)
from . import rss       # noqa: F401
from . import web       # noqa: F401
from . import github    # noqa: F401
from . import youtube   # noqa: F401
from . import reddit    # noqa: F401
from . import domain    # noqa: F401  (passive domain/entity intelligence)
from . import files     # noqa: F401  (local file/document ingestion)

__all__ = ["Channel", "register", "get", "all_channels", "search"]
