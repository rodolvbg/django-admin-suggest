"""Real-browser end-to-end tests: the script and the endpoint are
unit-tested elsewhere (tests/js/, tests/test_search.py); this file is about
the two working together, through an actual browser, against a real
running Django server.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
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
        self.page.goto(f"{self.live_server_url}/admin/login/")
        self.page.fill('input[name="username"]', "admin")
        self.page.fill('input[name="password"]', "password")
        self.page.click('input[type="submit"]')
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
