"""The demo's admin on an Unfold site (see ``example.settings_unfold``)."""

from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.sites import UnfoldAdminSite

from django_admin_suggest import SearchSuggestionsMixin

from .models import Album, Image

site = UnfoldAdminSite(name="admin")


@admin.register(Album, site=site)
class AlbumAdmin(SearchSuggestionsMixin, ModelAdmin):
    search_fields = ("title",)
    search_suggestions = True


@admin.register(Image, site=site)
class ImageAdmin(SearchSuggestionsMixin, ModelAdmin):
    list_display = ("title", "album")
    search_fields = ("title", "album__title")
    search_suggestions = True
    search_suggestions_add = True
