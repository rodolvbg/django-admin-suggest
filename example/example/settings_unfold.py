"""The demo with django-unfold: ``DJANGO_SETTINGS_MODULE=example.settings_unfold``."""

from .settings import *  # noqa: F403
from .settings import INSTALLED_APPS

INSTALLED_APPS = ["unfold", *INSTALLED_APPS]

ROOT_URLCONF = "example.urls_unfold"
