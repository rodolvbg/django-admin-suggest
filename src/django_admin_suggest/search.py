from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.conf import settings
from django.contrib.admin import ModelAdmin
from django.contrib.admin.options import IS_POPUP_VAR, BaseModelAdmin
from django.contrib.admin.utils import quote
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.forms import Media
from django.http import JsonResponse, QueryDict
from django.template.loader import select_template
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, path, reverse
from django.utils.translation import gettext

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.contrib.admin.views.main import ChangeList
    from django.db.models import Model, QuerySet
    from django.http import HttpRequest, HttpResponse
    from django.urls import URLPattern


def search_add_field(model: type[Model], search_fields: Sequence[str]) -> str | None:
    """The first of ``search_fields`` that is an editable field of ``model``
    (``^title`` and ``title__iexact`` too: ``title``): the one what was
    searched for goes in, adding it. None: none is."""
    for name in search_fields:
        field_name, *lookups = name.lstrip("^=@").split("__")
        try:
            field = model._meta.get_field(field_name)
        except FieldDoesNotExist:
            continue
        if field.is_relation or field.auto_created or not field.editable:
            continue
        # Its own lookup at most (title__iexact), not a transform's.
        if len(lookups) > 1 or (lookups and not field.get_lookup(lookups[0])):
            continue
        return field.name
    return None


class SearchSuggestionsMixin(BaseModelAdmin):
    """``ModelAdmin`` mixin: the changelist's search box suggests the
    objects it finds as one types, and choosing one opens its change page::

        class BookAdmin(SearchSuggestionsMixin, admin.ModelAdmin):
            search_fields = ("title", "author__name")
            search_suggestions = True

    The suggestions are what the changelist's search would find: its
    ``get_search_results()`` (``search_fields``, their ``^``, ``=`` and
    ``@`` prefixes, and anything that overrides it), on
    ``get_queryset(request)``, in the changelist's order. One query, of
    ``search_suggestions_limit`` objects at most. Enter without choosing one
    searches as always.

    ``get_search_suggestion_label()`` and ``get_search_suggestion_url()``
    say how each one shows and where it leads; ``get_search_suggestions()``
    which they are.

    The changelist is rendered with ``search_suggestions_template``, which
    extends the one the admin would use (``change_list_template``, or
    another package's, included) and adds the script's configuration. The
    ``# type: ignore[misc]`` on ``super()`` calls is because only the
    concrete ``ModelAdmin`` declares them.

    With ``search_suggestions_add``, when nothing is found it offers to add
    it: a link to the add page, with what was typed in a field (``True``:
    the first of ``search_fields`` that is a field of the model; a name:
    that field). Only for those who may add; ``get_search_suggestion_add_url()``
    changes where it leads.
    """

    #: Whether the search box suggests objects.
    search_suggestions = False
    #: How many, at most.
    search_suggestions_limit = 8
    #: The characters typed before it suggests any.
    search_suggestions_min_length = 2
    #: When nothing is found, a link to add it: ``True`` (what was typed in
    #: the first of ``search_fields`` that is a field of the model), or the
    #: field's name.
    search_suggestions_add: bool | str = False
    #: The changelist's template: the admin's, and the script's configuration.
    search_suggestions_template = "django_admin_suggest/change_list.html"

    @property
    def uses_search_suggestions(self) -> bool:
        return bool(self.search_suggestions) and isinstance(self, ModelAdmin)

    def get_search_suggestions(self, request: HttpRequest, term: str) -> QuerySet[Any]:
        """The objects suggested for ``term``: those the changelist's search
        finds, in its order."""
        queryset = self.get_queryset(request)
        found, may_have_duplicates = self.get_search_results(  # type: ignore[attr-defined]
            request, queryset, term
        )
        if may_have_duplicates:
            # As the changelist does: each object once, whatever it joined.
            found = queryset.filter(pk__in=found.values("pk"))
        ordering = self.get_ordering(request)
        if ordering:
            found = found.order_by(*ordering)
        return found[: self.search_suggestions_limit]

    def get_search_suggestion_label(self, request: HttpRequest, obj: Model) -> str:
        """How a suggestion shows: the object, as the admin names it."""
        return str(obj)

    def get_search_suggestion_url(self, request: HttpRequest, obj: Model) -> str | None:
        """Where choosing it leads: its change page (read-only, for those who
        may only view it). None: it isn't suggested."""
        if not self.has_view_or_change_permission(request, obj):
            return None
        opts = self.model._meta
        name = f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_change"
        try:
            return reverse(name, args=(quote(obj.pk),))
        except NoReverseMatch:
            return None

    def get_search_suggestion_add_field(self, request: HttpRequest) -> str | None:
        """The field the add page gets what was typed in: the one of
        ``search_suggestions_add``, or (``True``) the first of
        ``search_fields`` that is an editable field of the model (``^title``
        and ``title__iexact`` too: ``title``). None: the add page as it is."""
        if isinstance(self.search_suggestions_add, str):
            return self.search_suggestions_add
        return search_add_field(
            self.model,
            self.get_search_fields(request),  # type: ignore[attr-defined]
        )

    def get_search_suggestion_add_url(
        self, request: HttpRequest, term: str
    ) -> str | None:
        """Where adding what wasn't found leads: the add page, with ``term``
        in its field (``get_search_suggestion_add_field()``). None: not
        offered (it's off, or one may not add)."""
        if not self.search_suggestions_add or not self.has_add_permission(request):
            return None
        opts = self.model._meta
        try:
            url = reverse(
                f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_add"
            )
        except NoReverseMatch:
            return None
        field = self.get_search_suggestion_add_field(request)
        if field:
            query = QueryDict(mutable=True)
            query[field] = term
            url = f"{url}?{query.urlencode()}"
        return url

    # The endpoint ------------------------------------------------------------

    def get_urls(self) -> list[URLPattern]:
        urls = super().get_urls()  # type: ignore[misc]
        if not self.uses_search_suggestions:
            return urls
        opts = self.model._meta
        return [
            path(
                "search-suggestions/",
                self.admin_site.admin_view(self.search_suggestions_view),
                name=f"{opts.app_label}_{opts.model_name}_search_suggestions",
            ),
            *urls,
        ]

    def search_suggestions_view(self, request: HttpRequest) -> JsonResponse:
        """``?q=``: the suggestions, as ``{"results": [{id, text, url}]}``;
        none, and adding is offered: ``"add": {text, url}`` too."""
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        term = request.GET.get("q", "").strip()
        if len(term) < self.search_suggestions_min_length or not (
            self.get_search_fields(request)  # type: ignore[attr-defined]
        ):
            return JsonResponse({"results": []})
        results = []
        for obj in self.get_search_suggestions(request, term):
            url = self.get_search_suggestion_url(request, obj)
            if url:
                results.append(
                    {
                        "id": str(obj.pk),
                        "text": self.get_search_suggestion_label(request, obj),
                        "url": url,
                    }
                )
        data: dict[str, Any] = {"results": results}
        add = None if results else self.get_search_suggestion_add_url(request, term)
        if add:
            data["add"] = {
                "text": gettext("Add “%(term)s”") % {"term": term},
                "url": add,
            }
        return JsonResponse(data)

    # The changelist ----------------------------------------------------------

    @property
    def media(self) -> Media:
        media = super().media
        if self.uses_search_suggestions:
            # The look of the admin's autocomplete fields: Select2's (minified
            # unless DEBUG, as the admin's own widgets load it).
            extra = "" if settings.DEBUG else ".min"
            media += Media(
                css={
                    "all": [
                        f"admin/css/vendor/select2/select2{extra}.css",
                        "admin/css/autocomplete.css",
                        "django_admin_suggest/search.css",
                    ]
                },
                js=["django_admin_suggest/search.js"],
            )
        return media

    def get_search_suggestions_config(
        self, request: HttpRequest, cl: ChangeList
    ) -> dict[str, Any] | None:
        """The script's configuration for the changelist; None: no
        suggestions (off, nothing to search, or in a popup, where choosing
        an object picks it for a field)."""
        if (
            not self.uses_search_suggestions
            or not cl.search_fields
            or IS_POPUP_VAR in request.GET
        ):
            return None
        opts = self.model._meta
        return {
            "url": reverse(
                f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_search_suggestions"
            ),
            "minLength": self.search_suggestions_min_length,
            "texts": {
                "label": gettext("Suggestions"),
                "empty": gettext("Nothing found."),
            },
        }

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        response = super().changelist_view(request, extra_context)  # type: ignore[misc]
        if not isinstance(response, TemplateResponse) or response.is_rendered:
            return response
        context = response.context_data or {}
        cl = context.get("cl")
        config = self.get_search_suggestions_config(request, cl) if cl else None
        if not config:
            return response
        # The admin's changelist_view() renders a name or a list of names.
        template_name = cast("str | Sequence[str]", response.template_name)
        context["django_admin_suggest_parent"] = select_template(
            [template_name] if isinstance(template_name, str) else template_name
        )
        context["django_admin_suggest_search"] = config
        response.template_name = self.search_suggestions_template
        return response
