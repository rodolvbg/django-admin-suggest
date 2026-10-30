from django.contrib import admin

from django_admin_suggest import AutocompleteAddMixin, SearchSuggestionsMixin

from .models import Album, Image


@admin.register(Album)
class AlbumAdmin(SearchSuggestionsMixin, admin.ModelAdmin):
    search_fields = ("title",)
    ordering = ("title",)
    search_suggestions = True


@admin.register(Image)
class ImageAdmin(AutocompleteAddMixin, SearchSuggestionsMixin, admin.ModelAdmin):
    list_display = ("title", "album")
    # The search box suggests images as one types; choosing one opens it.
    search_fields = ("title", "album__title")
    search_suggestions = True
    # Nothing found: "+ Add “…”", the add page with it as the title.
    search_suggestions_add = True
    # Its album: an autocomplete field; nothing found, "+ Add “…”" adds it.
    autocomplete_fields = ("album",)
    autocomplete_add = True
