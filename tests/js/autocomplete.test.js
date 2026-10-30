import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

const SCRIPT =
    "../../src/django_admin_suggest/static/django_admin_suggest/autocomplete.js";

// The admin's jQuery and Select2 (the versions it ships), as globals, and
// django.jQuery as admin/js/jquery.init.js makes it.
beforeAll(() => {
    const require = createRequire(import.meta.url);
    for (const file of ["jquery/dist/jquery.js", "select2/dist/js/select2.full.js"]) {
        (0, eval)(readFileSync(require.resolve(file), "utf8"));
    }
    window.django = { jQuery: window.jQuery.noConflict(true) };
});

const $ = () => window.django.jQuery;

function page({ multiple = false, link = true, field = "title" } = {}) {
    const attrs = [
        'data-django-admin-suggest-add="Add “%(term)s”"',
        field ? `data-django-admin-suggest-add-field="${field}"` : "",
        multiple ? "multiple" : "",
    ].join(" ");
    document.body.innerHTML = `
        <select id="id_album" name="album" ${attrs}>
            <option value=""></option>
            <option value="1">Holiday</option>
        </select>
        ${link ? '<a id="add_id_album" href="/admin/gallery/album/add/?_to_field=id&amp;_popup=1">Add</a>' : ""}`;
    return document.getElementById("id_album");
}

async function load(readyState = "complete") {
    vi.spyOn(document, "readyState", "get").mockReturnValue(readyState);
    vi.resetModules();
    await import(SCRIPT);
}

function open(select) {
    $()(select).select2();
    $()(select).select2("open");
    return $()(select).data("select2");
}

function search(instance, term) {
    const field =
        instance.$dropdown.find(".select2-search__field")[0] ||
        instance.$container.find(".select2-search__field")[0];
    field.value = term;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    return field;
}

const offered = () =>
    document.querySelectorAll(".django-admin-suggest-autocomplete-add");

function enter(target) {
    const event = new KeyboardEvent("keydown", {
        key: "Enter",
        bubbles: true,
        cancelable: true,
    });
    target.dispatchEvent(event);
    return event;
}

describe("autocomplete.js", () => {
    afterEach(() => {
        $()(document).off("select2:opening");
        for (const select of document.querySelectorAll("select")) {
            if ($()(select).data("select2")) $()(select).select2("destroy");
        }
        document.body.innerHTML = "";
        vi.restoreAllMocks();
    });

    it("offers what was typed when nothing is found", async () => {
        await load();
        const instance = open(page());
        search(instance, "Lake");
        expect([...offered()].map((item) => item.textContent)).toEqual([
            "+ Add “Lake”",
        ]);
        expect(
            instance.$results.find(".select2-results__message").length,
        ).toBe(1);
    });

    it("not while something is found", async () => {
        await load();
        const instance = open(page());
        search(instance, "Holi");
        expect(offered()).toHaveLength(0);
    });

    it("opens the field's add link, with it in the field, and closes", async () => {
        await load();
        const select = page();
        const instance = open(select);
        search(instance, "Lake & co");
        const link = document.getElementById("add_id_album");
        const clicked = vi.fn((event) => {
            event.preventDefault();
            return link.getAttribute("href");
        });
        link.addEventListener("click", clicked);
        offered()[0].click();
        const href = new URL(clicked.mock.results[0].value, "http://x");
        expect(href.searchParams.get("title")).toBe("Lake & co");
        expect(href.searchParams.get("_popup")).toBe("1");
        // The link as it was.
        expect(link.getAttribute("href")).toBe(
            "/admin/gallery/album/add/?_to_field=id&_popup=1",
        );
        expect(instance.isOpen()).toBe(false);
    });

    it("without a field, the add page as it is", async () => {
        await load();
        const instance = open(page({ field: "" }));
        search(instance, "Lake");
        const link = document.getElementById("add_id_album");
        const hrefs = [];
        link.addEventListener("click", (event) => {
            event.preventDefault();
            hrefs.push(link.getAttribute("href"));
        });
        offered()[0].click();
        expect(hrefs).toEqual([
            "/admin/gallery/album/add/?_to_field=id&_popup=1",
        ]);
    });

    it("Enter adds it, before Select2", async () => {
        await load();
        const instance = open(page());
        const field = search(instance, "Lake");
        const link = document.getElementById("add_id_album");
        const clicked = vi.fn((event) => event.preventDefault());
        link.addEventListener("click", clicked);
        expect(enter(field).defaultPrevented).toBe(true);
        expect(clicked).toHaveBeenCalledOnce();
    });

    it("other keys, or Enter with nothing offered, are Select2's", async () => {
        await load();
        const instance = open(page());
        const field = search(instance, "Holi");
        const other = new KeyboardEvent("keydown", {
            key: "a",
            bubbles: true,
            cancelable: true,
        });
        field.dispatchEvent(other);
        expect(other.defaultPrevented).toBe(false);
        // Enter reaches Select2's own listener, on the field.
        const select2 = vi.fn();
        field.addEventListener("keydown", select2);
        enter(field);
        expect(select2).toHaveBeenCalledOnce();
    });

    it("not once it's closed", async () => {
        await load();
        const select = page();
        const instance = open(select);
        search(instance, "Lake");
        $()(select).select2("close");
        const link = document.getElementById("add_id_album");
        const clicked = vi.fn((event) => event.preventDefault());
        link.addEventListener("click", clicked);
        enter(instance.$container[0]);
        expect(clicked).not.toHaveBeenCalled();
    });

    it("a multiple field: its search is in the field", async () => {
        await load();
        const instance = open(page({ multiple: true }));
        const field = search(instance, "Lake");
        expect(offered()).toHaveLength(1);
        const link = document.getElementById("add_id_album");
        const clicked = vi.fn((event) => event.preventDefault());
        link.addEventListener("click", clicked);
        enter(field);
        expect(clicked).toHaveBeenCalledOnce();
    });

    it("nothing typed, or no add link: nothing offered", async () => {
        await load();
        let instance = open(page({ link: false }));
        search(instance, "Lake");
        expect(offered()).toHaveLength(0);
        $()("#id_album").select2("destroy");

        const select = page();
        select.innerHTML = "";
        instance = open(select);
        search(instance, "");
        expect(instance.$results.find(".select2-results__message").length).toBe(
            1,
        );
        expect(offered()).toHaveLength(0);
    });

    it("only for its own message, and bound once", async () => {
        await load();
        const select = page();
        const instance = open(select);
        $()(select).select2("close");
        $()(select).select2("open");
        search(instance, "Lake");
        expect(offered()).toHaveLength(1);
        instance.trigger("results:message", { message: "errorLoading" });
        expect(offered()).toHaveLength(0);
    });

    it("a select2:opening of no Select2 is nothing", async () => {
        await load();
        const select = page();
        $()(select).trigger("select2:opening");
        expect(select.dataset.djangoAdminSuggestBound).toBeUndefined();
    });

    it("waits for the page", async () => {
        await load("loading");
        let instance = open(page());
        search(instance, "Lake");
        expect(offered()).toHaveLength(0);
        $()("#id_album").select2("destroy");
        document.dispatchEvent(new Event("DOMContentLoaded"));
        instance = open(page());
        search(instance, "Lake");
        expect(offered()).toHaveLength(1);
    });
});
