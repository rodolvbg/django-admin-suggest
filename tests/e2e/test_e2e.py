"""Real-browser end-to-end tests: the script and the endpoint are
unit-tested elsewhere (tests/js/, tests/test_search.py); this file is about
the two working together, through an actual browser, against a real
running Django server.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import modify_settings, override_settings
from gallery.models import Album, Image
from playwright.sync_api import Page, expect


class _AdminE2ETestCase(StaticLiveServerTestCase):
    """Shared setup for browser tests against the example admin: log in
    once per test and build the Album/Image fixtures most of them start
    from, instead of each test repeating the same few lines.

    ``StaticLiveServerTestCase`` (a ``TransactionTestCase`` under the
    hood, with static files served too — needed since these tests load
    a real page that pulls in our JS) already runs each test in its own
    transaction the way ``@pytest.mark.django_db(transaction=True)``
    does, so that marker isn't needed here; it also gives
    ``self.live_server_url`` in place of the ``live_server`` fixture.
    pytest-playwright's ``page`` fixture still needs pytest's own
    injection, which doesn't reach unittest-style test methods as an
    extra parameter — so it's grabbed once per test via this autouse
    fixture instead, and stashed on ``self``.
    """

    @pytest.fixture(autouse=True)
    def _inject_page(self, page: Page) -> None:
        self.page = page

    def tearDown(self) -> None:
        # Close the page before the test database is flushed (after
        # tearDown): a request still in flight, or one the page makes later,
        # would otherwise reach the server once its data, or its database
        # connection, is gone, breaking this test or the next one.
        page = getattr(self, "page", None)
        if page is not None and not page.is_closed():
            # Its routes first (a CSP test adds some): none left mid-request.
            page.unroute_all(behavior="ignoreErrors")
            page.close()
        super().tearDown()

    def login(self) -> None:
        get_user_model().objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        self.page.goto(f"{self.live_server_url}/admin/login/?next=/admin/")
        self.page.fill('input[name="username"]', "admin")
        self.page.fill('input[name="password"]', "password")
        self.page.click('#login-form [type="submit"]')
        expect(self.page).to_have_url(f"{self.live_server_url}/admin/")

    def create_album(self, *, images: tuple[str, ...] = ()) -> Album:
        album = Album.objects.create(title="Holiday")
        for title in images:
            Image.objects.create(album=album, title=title)
        return album


class TestSearchSuggestions(_AdminE2ETestCase):
    """The example's ImageAdmin: its search box suggests images."""

    def test_choosing_a_suggestion_opens_it(self):
        self.create_album(images=("Beach", "Beach bar", "City"))
        self.login()
        page = self.page
        page.goto(f"{self.live_server_url}/admin/gallery/image/")

        search = page.locator("#searchbar")
        search.press_sequentially("bea")
        options = page.locator("#django-admin-suggest-search-suggestions [role=option]")
        expect(options).to_have_text(["Beach", "Beach bar"])
        expect(search).to_have_attribute("aria-expanded", "true")

        # The keyboard: the second one.
        search.press("ArrowDown")
        search.press("ArrowDown")
        search.press("Enter")
        bar = Image.objects.get(title="Beach bar")
        expect(page).to_have_url(
            f"{self.live_server_url}/admin/gallery/image/{bar.pk}/change/"
        )

        # The mouse.
        page.go_back()
        page.locator("#searchbar").fill("")
        page.locator("#searchbar").press_sequentially("city")
        page.locator(
            "#django-admin-suggest-search-suggestions a", has_text="City"
        ).click()
        city = Image.objects.get(title="City")
        expect(page).to_have_url(
            f"{self.live_server_url}/admin/gallery/image/{city.pk}/change/"
        )

    def test_enter_without_choosing_searches_as_always(self):
        self.create_album(images=("Beach", "City"))
        self.login()
        page = self.page
        page.goto(f"{self.live_server_url}/admin/gallery/image/")
        search = page.locator("#searchbar")
        search.press_sequentially("city")
        expect(page.locator("#django-admin-suggest-search-suggestions")).to_be_visible()
        search.press("Escape")
        expect(page.locator("#django-admin-suggest-search-suggestions")).to_be_hidden()
        search.press("Enter")
        expect(page).to_have_url(re.compile(r"\?q=city$"))
        expect(page.locator("#result_list tbody tr")).to_have_count(1)

    def test_adds_what_isnt_found(self):
        self.create_album(images=("Beach",))
        self.login()
        page = self.page
        page.goto(f"{self.live_server_url}/admin/gallery/image/")
        search = page.locator("#searchbar")
        search.press_sequentially("Lake")
        expect(page.get_by_role("option", name="+ Add “Lake”")).to_be_visible()
        search.press("ArrowDown")
        search.press("Enter")
        expect(page).to_have_url(re.compile(r"/image/add/\?title=Lake$"))
        expect(page.locator("input[name=title]")).to_have_value("Lake")


class TestAutocompleteAdd(_AdminE2ETestCase):
    """The example's ImageAdmin: its album, an autocomplete field, offers to
    add the album it doesn't find."""

    def open_album_field(self):
        page = self.page
        page.goto(f"{self.live_server_url}/admin/gallery/image/add/")
        page.locator("#id_album + .select2").click()
        return page.locator(".select2-container--open .select2-search__field")

    def test_adds_the_album_it_doesnt_find_and_chooses_it(self):
        self.create_album()
        self.login()
        page = self.page
        search = self.open_album_field()
        search.press_sequentially("Lake")
        add = page.locator(".django-admin-suggest-autocomplete-add")
        expect(add).to_have_text("+ Add “Lake”")
        expect(page.locator(".select2-results__message")).to_be_visible()

        # The admin's popup, its title filled.
        with page.expect_popup() as info:
            add.click()
        popup = info.value
        expect(popup).to_have_url(re.compile(r"/album/add/\?.*title=Lake"))
        expect(popup.locator("input[name=title]")).to_have_value("Lake")
        popup.locator("input[name=_save]").click()

        # Once saved, chosen.
        lake = Album.objects.get(title="Lake")
        expect(page.locator("#id_album")).to_have_value(str(lake.pk))
        expect(page.locator("#select2-id_album-container")).to_have_text(
            re.compile("Lake")
        )

    def test_enter_adds_it(self):
        self.login()
        page = self.page
        search = self.open_album_field()
        search.press_sequentially("Pond")
        expect(page.locator(".django-admin-suggest-autocomplete-add")).to_be_visible()
        with page.expect_popup() as info:
            search.press("Enter")
        expect(info.value.locator("input[name=title]")).to_have_value("Pond")
        # The link as it was.
        expect(page.locator("#add_id_album")).not_to_have_attribute(
            "href", re.compile("Pond")
        )

    def test_not_while_it_finds_some(self):
        self.create_album()
        self.login()
        page = self.page
        search = self.open_album_field()
        search.press_sequentially("Holi")
        expect(
            page.locator(".select2-results__option", has_text="Holiday")
        ).to_be_visible()
        expect(page.locator(".django-admin-suggest-autocomplete-add")).to_have_count(0)


@modify_settings(INSTALLED_APPS={"prepend": "unfold"})
@override_settings(ROOT_URLCONF="example.urls_unfold")
class TestAutocompleteAddUnfold(_AdminE2ETestCase):
    """The same, in Unfold: its "add" link opens a modal (an iframe)."""

    def test_adds_it_in_unfolds_modal_and_chooses_it(self):
        self.login()
        page = self.page
        page.goto(f"{self.live_server_url}/admin/gallery/image/add/")
        page.locator("#id_album + .select2").click()
        search = page.locator(".select2-container--open .select2-search__field")
        search.press_sequentially("Lake")
        add = page.locator(".django-admin-suggest-autocomplete-add")
        expect(add).to_have_text("+ Add “Lake”")

        add.click()

        modal = page.frame_locator("iframe.related-modal-frame")
        expect(modal.locator("input[name=title]")).to_have_value("Lake")
        modal.locator("button[name=_save]").click()

        expect(page.locator("#id_album option:checked")).to_have_text("Lake")
        lake = Album.objects.get(title="Lake")
        expect(page.locator("#id_album")).to_have_value(str(lake.pk))
        expect(page.locator("iframe.related-modal-frame")).to_be_hidden()
