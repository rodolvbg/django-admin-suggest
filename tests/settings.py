"""The demo's settings, for the tests."""

import tempfile
from pathlib import Path

from example.settings import *  # noqa: F403
from example.settings import TEMPLATES

# A file, not in memory: the end-to-end tests' server answers from several
# threads, and an in-memory database is one connection they'd all share
# (closing it as the server stops, a request's thread would fail).
_DB = str(Path(tempfile.mkdtemp(prefix="django-admin-suggest-")) / "test.sqlite3")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _DB,
        "TEST": {"NAME": _DB},
    }
}

# A project's own changelist template (test_search.py).
TEMPLATES[0]["DIRS"] = [Path(__file__).parent / "templates"]
