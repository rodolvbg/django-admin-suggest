"""Suggestions as one types, for the Django admin."""

from .autocomplete import AutocompleteAddMixin
from .search import SearchSuggestionsMixin, search_add_field

__all__ = ["AutocompleteAddMixin", "SearchSuggestionsMixin", "search_add_field"]

__version__ = "0.1.1"
