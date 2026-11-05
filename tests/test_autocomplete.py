"""AutocompleteAddMixin: an autocomplete field that finds nothing offers to
add it."""

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase
from gallery.models import Album, Image

from django_admin_suggest import AutocompleteAddMixin, SearchSuggestionsMixin

ADD = 'data-django-admin-suggest-add="Add “%(term)s”"'


class TestAutocompleteAdd(TestCase):
    """The example's ImageAdmin: its album, an autocomplete field."""

    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")

    def setUp(self):
        self.client.force_login(self.user)

    def add_page(self):
        response = self.client.get("/admin/gallery/image/add/")
        assert response.status_code == 200
        return response.content.decode()

    def test_the_field_offers_it_with_where_it_goes(self):
        html = self.add_page()
        assert ADD in html
        # The album admin's search field (SearchSuggestionsMixin's).
        assert 'data-django-admin-suggest-add-field="title"' in html
        assert "django_admin_suggest/autocomplete.js" in html
        assert "django_admin_suggest/autocomplete.css" in html

    def test_not_for_those_who_may_not_add_albums(self):
        staff = User.objects.create_user("staff", password="pw", is_staff=True)
        staff.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["add_image", "view_album", "view_image"]
            )
        )
        self.client.force_login(staff)
        assert "data-django-admin-suggest-add" not in self.add_page()


class Site(admin.AdminSite):
    pass


def field_attrs(admin_class, site, name="album"):
    model_admin = admin_class(Image, site)
    request = RequestFactory().get("/")
    request.user = User(is_superuser=True, is_active=True, is_staff=True)
    field = model_admin.formfield_for_dbfield(Image._meta.get_field(name), request)
    return model_admin, request, field.widget.widget.attrs


class TestOptions(TestCase):
    def site(self, album_admin=admin.ModelAdmin):
        site = Site()
        site.register(
            Album,
            type(
                "AlbumAdmin",
                (album_admin,),
                {
                    "search_fields": ("^title",),
                },
            ),
        )
        return site

    def test_its_related_admins_search_field(self):
        class ImageAdmin(AutocompleteAddMixin, admin.ModelAdmin):
            autocomplete_fields = ("album",)
            autocomplete_add = True

        _, _, attrs = field_attrs(ImageAdmin, self.site())
        assert attrs["data-django-admin-suggest-add-field"] == "title"

    def test_when_empty_by_default_or_its_own(self):
        class ImageAdmin(AutocompleteAddMixin, admin.ModelAdmin):
            autocomplete_fields = ("album",)
            autocomplete_add = True

        _, _, attrs = field_attrs(ImageAdmin, self.site())
        assert attrs["data-django-admin-suggest-add-when"] == "empty"
        ImageAdmin.autocomplete_add_when = "no_exact"
        _, _, attrs = field_attrs(ImageAdmin, self.site())
        assert attrs["data-django-admin-suggest-add-when"] == "no_exact"
        ImageAdmin.autocomplete_add_when = "sometimes"
        with self.assertRaisesMessage(ImproperlyConfigured, "'sometimes' is not"):
            field_attrs(ImageAdmin, self.site())

    def test_or_the_one_it_adds_with(self):
        class AlbumAdmin(SearchSuggestionsMixin, admin.ModelAdmin):
            search_suggestions_add = "title"

        class ImageAdmin(AutocompleteAddMixin, admin.ModelAdmin):
            autocomplete_fields = ("album",)
            autocomplete_add = ("album",)

        _, _, attrs = field_attrs(ImageAdmin, self.site(AlbumAdmin))
        assert attrs["data-django-admin-suggest-add-field"] == "title"

    def test_none_the_add_page_as_it_is(self):
        class ImageAdmin(AutocompleteAddMixin, admin.ModelAdmin):
            autocomplete_fields = ("album",)
            autocomplete_add = True

            def get_autocomplete_add_field(self, request, db_field):
                return None

        _, _, attrs = field_attrs(ImageAdmin, self.site())
        assert "data-django-admin-suggest-add" in attrs
        assert "data-django-admin-suggest-add-field" not in attrs

    def test_only_the_fields_named(self):
        class ImageAdmin(AutocompleteAddMixin, admin.ModelAdmin):
            autocomplete_fields = ("album",)
            autocomplete_add = ("other",)

        model_admin, _, attrs = field_attrs(ImageAdmin, self.site())
        assert "data-django-admin-suggest-add" not in attrs
        assert "autocomplete.js" in str(model_admin.media)

    def test_off(self):
        class ImageAdmin(AutocompleteAddMixin, admin.ModelAdmin):
            autocomplete_fields = ("album",)

        model_admin, _, attrs = field_attrs(ImageAdmin, self.site())
        assert "data-django-admin-suggest-add" not in attrs
        assert "autocomplete.js" not in str(model_admin.media)

    def test_an_unregistered_model_has_no_field(self):
        class ImageAdmin(AutocompleteAddMixin, admin.ModelAdmin):
            pass

        model_admin = ImageAdmin(Image, Site())
        request = RequestFactory().get("/")
        field = Image._meta.get_field("album")
        assert model_admin.get_autocomplete_add_field(request, field) is None


class TestInline(TestCase):
    def test_on_an_inline(self):
        class ImageInline(AutocompleteAddMixin, admin.TabularInline):
            model = Image
            autocomplete_fields = ("album",)
            autocomplete_add = True

        site = Site()
        site.register(
            Album,
            type(
                "AlbumAdmin",
                (admin.ModelAdmin,),
                {
                    "search_fields": ("title",),
                },
            ),
        )
        inline = ImageInline(Album, site)
        request = RequestFactory().get("/")
        request.user = User(is_superuser=True, is_active=True, is_staff=True)
        field = inline.formfield_for_dbfield(Image._meta.get_field("album"), request)
        assert (
            field.widget.widget.attrs["data-django-admin-suggest-add-field"] == "title"
        )
        assert "autocomplete.js" in str(inline.media)
