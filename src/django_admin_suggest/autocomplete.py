from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.admin.options import BaseModelAdmin
from django.contrib.admin.widgets import AutocompleteMixin, RelatedFieldWidgetWrapper
from django.forms import Media
from django.utils.translation import gettext

from .search import SearchSuggestionsMixin, search_add_field

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models import Field
    from django.forms import Field as FormField
    from django.http import HttpRequest


class AutocompleteAddMixin(BaseModelAdmin):
    """``ModelAdmin`` (or inline) mixin: an autocomplete field that finds
    nothing offers to add what was typed::

        class AppointmentAdmin(AutocompleteAddMixin, admin.ModelAdmin):
            autocomplete_fields = ("patient",)
            autocomplete_add = True

    "+ Add “…”", under Select2's "No results found", opens the field's own
    "add" link (the admin's popup; Unfold's modal) with what was typed in
    a field of the add page; once saved, it's chosen, as the admin does.
    Only where that link is: for those who may add one.

    The field: ``get_autocomplete_add_field()``, by default the related
    admin's search field (``search_add_field()``; with
    ``SearchSuggestionsMixin``, its ``get_search_suggestion_add_field()``).
    """

    #: ``True``: every autocomplete field; or the names of those that offer it.
    autocomplete_add: bool | Sequence[str] = False

    def get_autocomplete_add_field(
        self, request: HttpRequest, db_field: Field[Any, Any]
    ) -> str | None:
        """The related model's field that gets what was typed: the related
        admin's first search field that is an editable field (or, with
        ``SearchSuggestionsMixin``, its ``get_search_suggestion_add_field()``).
        None: the add page as it is."""
        model = db_field.remote_field.model  # type: ignore[union-attr]  # A relation.
        related_admin = self.admin_site._registry.get(model)
        if related_admin is None:
            return None
        if isinstance(related_admin, SearchSuggestionsMixin):
            return related_admin.get_search_suggestion_add_field(request)
        return search_add_field(model, related_admin.get_search_fields(request))

    def formfield_for_dbfield(
        self, db_field: Field[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> FormField | None:
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        widget = getattr(formfield, "widget", None)
        if (
            isinstance(widget, RelatedFieldWidgetWrapper)
            and widget.can_add_related
            and isinstance(widget.widget, AutocompleteMixin)
            and (
                self.autocomplete_add is True
                or (
                    not isinstance(self.autocomplete_add, bool)
                    and db_field.name in self.autocomplete_add
                )
            )
        ):
            attrs = widget.widget.attrs
            attrs["data-django-admin-suggest-add"] = gettext("Add “%(term)s”")
            field = self.get_autocomplete_add_field(request, db_field)
            if field:
                attrs["data-django-admin-suggest-add-field"] = field
        return formfield

    @property
    def media(self) -> Media:
        media = super().media
        if self.autocomplete_add:
            media += Media(
                css={"all": ["django_admin_suggest/autocomplete.css"]},
                js=["django_admin_suggest/autocomplete.js"],
            )
        return media
