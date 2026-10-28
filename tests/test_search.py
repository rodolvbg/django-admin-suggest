"""SearchSuggestionsMixin: the changelist's search box suggests objects."""

import json
import re
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import translation
from gallery.models import Album, Image

from django_admin_suggest import SearchSuggestionsMixin

URL = "/admin/gallery/image/search-suggestions/"


def config(html):
    match = re.search(
        r'<script id="django-admin-suggest-search" type="application/json">'
        r"(.*?)</script>",
        html,
    )
    return json.loads(match.group(1)) if match else None


class TestSearchSuggestions(TestCase):
    """The example's ImageAdmin: images by their title or their album's."""

    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        winter = Album.objects.create(title="Winter")
        summer = Album.objects.create(title="Summer")
        cls.peak = Image.objects.create(album=winter, title="Snowy peak")
        cls.cabin = Image.objects.create(album=winter, title="Cabin")
        cls.beach = Image.objects.create(album=summer, title="Beach")

    def setUp(self):
        self.client.force_login(self.user)

    def suggest(self, term, client=None):
        response = (client or self.client).get(URL, {"q": term})
        assert response.status_code == 200
        return response.json()["results"]

    def test_what_the_search_finds_with_where_it_leads(self):
        results = self.suggest("winter")
        assert results == [
            {
                "id": str(image.pk),
                "text": image.title,
                "url": reverse("admin:gallery_image_change", args=(image.pk,)),
            }
            # The changelist's order: the model's (by id, here).
            for image in sorted([self.peak, self.cabin], key=lambda i: i.pk)
        ]
        assert [r["text"] for r in self.suggest("  BEACH ")] == ["Beach"]
        assert self.suggest("nothing like it") == []

    def test_too_short_nothing(self):
        assert self.suggest("w") == []
        assert self.suggest("  ") == []

    def test_one_query_at_most_a_few(self):
        for n in range(12):
            Image.objects.create(album=self.peak.album, title=f"Snow {n}")
        model_admin = admin.site._registry[Image]
        request = RequestFactory().get(URL)
        request.user = self.user
        with self.assertNumQueries(1):
            found = list(model_admin.get_search_suggestions(request, "snow"))
        assert len(found) == 8

    def test_its_page_has_its_configuration_and_script(self):
        html = self.client.get("/admin/gallery/image/").content.decode()
        assert config(html) == {
            "url": URL,
            "minLength": 2,
            "texts": {"label": "Suggestions", "empty": "Nothing found."},
        }
        assert "django_admin_suggest/search.js" in html
        assert "django_admin_suggest/search.css" in html
        # The look of the admin's autocomplete fields.
        assert "admin/css/vendor/select2/select2.min.css" in html
        assert "admin/css/autocomplete.css" in html
        # Not in a popup: there, choosing an object picks it.
        popup = self.client.get("/admin/gallery/image/", {"_popup": "1"})
        assert config(popup.content.decode()) is None

    def test_only_for_who_may_see_them(self):
        clerk = User.objects.create_user("clerk", password="pw", is_staff=True)
        self.client.force_login(clerk)
        assert self.client.get(URL, {"q": "winter"}).status_code == 403
        clerk.user_permissions.add(Permission.objects.get(codename="view_image"))
        self.client.force_login(User.objects.get(pk=clerk.pk))
        assert len(self.suggest("winter")) == 2
        self.client.logout()
        assert self.client.get(URL, {"q": "winter"}).status_code == 302


class Plain(SearchSuggestionsMixin, admin.ModelAdmin):
    """Off by default."""

    search_fields = ("title",)


class Labelled(SearchSuggestionsMixin, admin.ModelAdmin):
    search_fields = ("title", "album__title")
    search_suggestions = True
    ordering = ("-title",)

    def get_search_suggestion_label(self, request, obj):
        return f"{obj.title} · {obj.album}"

    def get_search_suggestion_url(self, request, obj):
        # Only those of Winter lead somewhere.
        if obj.album.title != "Winter":
            return None
        return super().get_search_suggestion_url(request, obj)


class Albums(SearchSuggestionsMixin, admin.ModelAdmin):
    """Through a reverse relation: an album as many times as its images."""

    search_fields = ("title", "images__title")
    search_suggestions = True


class Unsearchable(SearchSuggestionsMixin, admin.ModelAdmin):
    search_suggestions = True


class TestOptions(TestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        winter = Album.objects.create(title="Winter")
        Image.objects.create(album=winter, title="Snowy peak")
        Image.objects.create(album=winter, title="Cabin")
        Image.objects.create(album=Album.objects.create(title="Summer"), title="Sun")

    def request(self, term=""):
        request = RequestFactory().get("/", {"q": term})
        request.user = self.user
        return request

    def test_select2_unminified_in_debug(self):
        with self.settings(DEBUG=True):
            media = str(Labelled(Image, admin.site).media)
        assert "admin/css/vendor/select2/select2.css" in media

    def test_off_by_default(self):
        model_admin = Plain(Image, admin.site)
        assert model_admin.uses_search_suggestions is False
        names = [getattr(url, "name", None) for url in model_admin.get_urls()]
        assert "gallery_image_search_suggestions" not in names
        assert "search-suggestions" not in str(model_admin.media)

    def test_its_label_url_and_order(self):
        model_admin = Labelled(Image, admin.site)
        response = model_admin.search_suggestions_view(self.request("n"))
        assert json.loads(response.content) == {"results": []}
        # Found through a relation: each image once, in the admin's order.
        response = model_admin.search_suggestions_view(self.request("in"))
        texts = [r["text"] for r in json.loads(response.content)["results"]]
        assert texts == ["Snowy peak · Winter", "Cabin · Winter"]

    def test_what_isnt_to_be_suggested(self):
        model_admin = Labelled(Image, admin.site)
        response = model_admin.search_suggestions_view(self.request("su"))
        assert json.loads(response.content) == {"results": []}  # Summer's.

    def test_each_once(self):
        model_admin = Albums(Album, admin.site)
        found = model_admin.get_search_suggestions(self.request(), "a")
        assert [album.title for album in found] == ["Winter"]
        response = model_admin.search_suggestions_view(self.request("ca"))
        assert [r["text"] for r in json.loads(response.content)["results"]] == [
            "Winter"
        ]

    def test_without_search_fields_nothing(self):
        model_admin = Unsearchable(Image, admin.site)
        response = model_admin.search_suggestions_view(self.request("winter"))
        assert json.loads(response.content) == {"results": []}
        cl = model_admin.get_changelist_instance(self.request())
        assert model_admin.get_search_suggestions_config(self.request(), cl) is None

    def test_without_its_change_url(self):
        site = admin.AdminSite(name="elsewhere")
        model_admin = Labelled(Image, site)  # Not registered: no URLs.
        image = Image.objects.get(title="Cabin")
        assert model_admin.get_search_suggestion_url(self.request(), image) is None
        clerk = User.objects.create_user("clerk", is_staff=True)
        request = self.request()
        request.user = clerk
        assert (
            SearchSuggestionsMixin.get_search_suggestion_url(
                admin.site._registry[Image], request, image
            )
            is None
        )


class Adding(SearchSuggestionsMixin, admin.ModelAdmin):
    search_fields = ("album__title", "title__iexact")
    search_suggestions = True
    search_suggestions_add = True


class AddingCaption(Adding):
    search_suggestions_add = "caption"


class AddingUnprefilled(Adding):
    # A relation, transforms, an unknown name and the id: none to fill.
    search_fields = ("album", "title__lower", "title__lower__exact", "nothing", "id")

    def get_search_suggestions(self, request, term):
        return Image.objects.none()  # Not searchable as they are.


class TestAdding(TestCase):
    """``search_suggestions_add``: when nothing is found, a link to add it."""

    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        Image.objects.create(album=Album.objects.create(title="Winter"), title="Cabin")

    def suggest(self, model_admin, term, user=None):
        request = RequestFactory().get("/", {"q": term})
        request.user = user or self.user
        return json.loads(model_admin.search_suggestions_view(request).content)

    def test_offered_when_nothing_is_found_with_what_was_typed(self):
        data = self.suggest(Adding(Image, admin.site), "Lake & co")
        add = reverse("admin:gallery_image_add")
        assert data == {
            "results": [],
            "add": {"text": "Add “Lake & co”", "url": f"{add}?title=Lake+%26+co"},
        }

    def test_not_when_something_is_found(self):
        data = self.suggest(Adding(Image, admin.site), "cabin")
        assert len(data["results"]) == 1
        assert "add" not in data

    def test_in_the_field_it_names(self):
        data = self.suggest(AddingCaption(Image, admin.site), "Lake")
        assert data["add"]["url"].endswith("/add/?caption=Lake")

    def test_the_add_page_as_it_is_without_a_field_to_fill(self):
        data = self.suggest(AddingUnprefilled(Image, admin.site), "Lake")
        assert data["add"]["url"] == reverse("admin:gallery_image_add")

    def test_only_for_who_may_add(self):
        viewer = User.objects.create_user("viewer", is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename="view_image"))
        assert "add" not in self.suggest(Adding(Image, admin.site), "Lake", viewer)

    def test_off_by_default_or_without_its_add_url(self):
        assert "add" not in self.suggest(Labelled(Image, admin.site), "Lake")
        site = admin.AdminSite(name="elsewhere")  # Not registered: no URLs.
        assert "add" not in self.suggest(Adding(Image, site), "Lake")

    def test_the_add_page_fills_the_field(self):
        self.client.force_login(self.user)
        data = self.suggest(Adding(Image, admin.site), "Lake")
        response = self.client.get(data["add"]["url"])
        assert response.context["adminform"].form.initial["title"] == "Lake"


class TestChangelistTemplate(TestCase):
    """The changelist keeps the admin's template, and adds the configuration."""

    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")

    def setUp(self):
        self.client.force_login(self.user)

    def test_extends_the_template_the_admin_would_use(self):
        response = self.client.get("/admin/gallery/image/")
        assert response.templates[0].name == "django_admin_suggest/change_list.html"
        names = [template.name for template in response.templates]
        assert "admin/change_list.html" in names

    def test_another_changelist_template_is_kept(self):
        model_admin = admin.site._registry[Image]
        with patch.object(
            model_admin, "change_list_template", "gallery/image_change_list.html"
        ):
            html = self.client.get("/admin/gallery/image/").content.decode()
        assert "<p>The project's own changelist.</p>" in html
        assert config(html) is not None

    def test_a_redirect_passes_as_it_is(self):
        # An unknown lookup: the admin redirects to ?e=1.
        response = self.client.get("/admin/gallery/image/", {"nothing": "1"})
        assert response.status_code == 302

    def test_in_spanish(self):
        with translation.override("es"):
            html = self.client.get("/admin/gallery/image/").content.decode()
        assert config(html)["texts"] == {
            "label": "Sugerencias",
            "empty": "No se encontró nada.",
        }
