import os

import pytest
from django.contrib.auth.models import User

# pytest-playwright's sync API runs its driver via a greenlet-based
# bridge to an asyncio event loop in a background thread. That's enough
# for Django's asyncio-safety check to (falsely) think DB access is
# happening from an async context once `live_server`/Playwright fixtures
# are involved, even though nothing here is actually concurrent. This is
# the documented escape hatch for that exact combination.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("admin", "admin@example.com", "password")
