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

function page({
    multiple = false,
    link = true,
    field = "title",
    when = "",
    options = ["Holiday"],
} = {}) {
    const attrs = [
        'data-django-admin-suggest-add="Add “%(term)s”"',
        field ? `data-django-admin-suggest-add-field="${field}"` : "",
        when ? `data-django-admin-suggest-add-when="${when}"` : "",
        multiple ? "multiple" : "",
    ].join(" ");
    document.body.innerHTML = `
        <select id="id_album" name="album" ${attrs}>
            <option value=""></option>
            ${options.map((text, i) => `<option value="${i + 1}">${text}</option>`).join("")}
        </select>
        ${link ? '<a id="add_id_album" href="/admin/gallery/album/add/?_to_field=id&amp;_popup=1">Add</a>' : ""}`;
    return document.getElementById("id_album");
}

async function load(readyState = "complete") {
    vi.spyOn(document, "readyState", "get").mockReturnValue(readyState);
    vi.resetModules();
    await import(SCRIPT);
}

function open(select, options = {}) {
    $()(select).select2(options);
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

const highlighted = () =>
    [...document.querySelectorAll(".select2-results__option--highlighted")].map(
        (item) => item.textContent,
    );

function key(target, which) {
    const event = new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        keyCode: which,
        which,
    });
    target.dispatchEvent(event);
    return event;
}
const ENTER = 13;
const DOWN = 40;

/** The mouse lets go of it: Select2 chooses it. */
function choose(item) {
    item.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
}

/** The add link's clicks, kept from opening: its href at each. */
function clicks() {
    const link = document.getElementById("add_id_album");
    const hrefs = [];
    link.addEventListener("click", (event) => {
        event.preventDefault();
        hrefs.push(link.getAttribute("href"));
    });
    return hrefs;
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
        // The one to choose: highlighted, Select2's active one.
        expect(highlighted()).toEqual(["+ Add “Lake”"]);
    });

    it("not while something is found, by default", async () => {
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
        const hrefs = clicks();
        const changes = vi.fn();
        $()(select).on("change", changes);
        choose(offered()[0]);
        const href = new URL(hrefs[0], "http://x");
        expect(href.searchParams.get("title")).toBe("Lake & co");
        expect(href.searchParams.get("_popup")).toBe("1");
        // The link as it was; nothing chosen.
        expect(document.getElementById("add_id_album").getAttribute("href")).toBe(
            "/admin/gallery/album/add/?_to_field=id&_popup=1",
        );
        expect(instance.isOpen()).toBe(false);
        expect(changes).not.toHaveBeenCalled();
        expect(select.value).toBe("");
    });

    it("without a field, the add page as it is", async () => {
        await load();
        const instance = open(page({ field: "" }));
        search(instance, "Lake");
        const hrefs = clicks();
        choose(offered()[0]);
        expect(hrefs).toEqual(["/admin/gallery/album/add/?_to_field=id&_popup=1"]);
    });

    it("Enter adds it", async () => {
        await load();
        const instance = open(page());
        const field = search(instance, "Lake");
        const hrefs = clicks();
        expect(key(field, ENTER).defaultPrevented).toBe(true);
        expect(hrefs).toHaveLength(1);
    });

    it("always: after those found; Enter, the first; the arrows reach it", async () => {
        await load();
        const select = page({ when: "always", options: ["Lake", "Lakeside"] });
        const instance = open(select);
        const field = search(instance, "lake");
        expect(
            [...instance.$results.find(".select2-results__option")].map(
                (item) => item.textContent,
            ),
        ).toEqual(["Lake", "Lakeside", "+ Add “lake”"]);
        expect(highlighted()).toEqual(["Lake"]);
        key(field, DOWN);
        key(field, DOWN);
        expect(highlighted()).toEqual(["+ Add “lake”"]);
        const hrefs = clicks();
        key(field, ENTER);
        expect(hrefs).toHaveLength(1);
        expect(select.value).toBe("");

        // Enter on one found: chosen, as always.
        $()(select).select2("destroy");
        const again = page({ when: "always", options: ["Lake", "Lakeside"] });
        key(search(open(again), "lake"), ENTER);
        expect(again.value).toBe("1");
        expect(hrefs).toHaveLength(1);
    });

    it("no_exact: unless one found is what was typed", async () => {
        await load();
        const instance = open(
            page({ when: "no_exact", options: ["Juan  Pérez", "Juana"] }),
        );
        search(instance, "Juan");
        expect([...offered()].map((item) => item.textContent)).toEqual([
            "+ Add “Juan”",
        ]);
        search(instance, "juana");
        expect(offered()).toHaveLength(0);
        search(instance, "JUAN  pérez");
        expect(offered()).toHaveLength(0);
        search(instance, "Pedro"); // Nothing found: offered.
        expect(offered()).toHaveLength(1);
    });

    it("after the last page", async () => {
        await load();
        const select = page({ when: "always", options: [] });
        let next = null;
        const pages = {
            1: { results: [{ id: 1, text: "Lake" }], pagination: { more: true } },
            2: { results: [{ id: 2, text: "Lakeside" }] },
        };
        const instance = open(select, {
            ajax: {
                delay: 0,
                transport: (params, success) => {
                    const page = params.data.page || 1;
                    // The next page, once it's let through.
                    if (page === 1) success(pages[1]);
                    else next = () => success(pages[page]);
                    return { abort() {} };
                },
                data: (params) => ({ term: params.term, page: params.page }),
            },
        });
        search(instance, "lake");
        await new Promise((resolve) => setTimeout(resolve, 10));
        expect(offered()).toHaveLength(0);
        expect(next).not.toBe(null); // Select2 asked for it.
        next();
        expect(
            [...instance.$results.find("[aria-selected]")].map(
                (item) => item.textContent,
            ),
        ).toEqual(["Lake", "Lakeside", "+ Add “lake”"]);
    });

    it("other keys, or Enter with nothing offered, are Select2's", async () => {
        await load();
        const select = page();
        const instance = open(select);
        const field = search(instance, "Holi");
        expect(key(field, 65).defaultPrevented).toBe(false);
        key(field, ENTER);
        expect(select.value).toBe("1");
    });

    it("a multiple field: its search is in the field", async () => {
        await load();
        const instance = open(page({ multiple: true }));
        const field = search(instance, "Lake");
        expect(offered()).toHaveLength(1);
        const hrefs = clicks();
        key(field, ENTER);
        expect(hrefs).toHaveLength(1);
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

    it("once, bound once; another's choice is Select2's", async () => {
        await load();
        const select = page();
        const instance = open(select);
        $()(select).select2("close");
        $()(select).select2("open");
        search(instance, "Lake");
        search(instance, "Lakes");
        expect([...offered()].map((item) => item.textContent)).toEqual([
            "+ Add “Lakes”",
        ]);
        instance.trigger("results:message", { message: "errorLoading" });
        expect(offered()).toHaveLength(0);
        // A selecting of no data of ours, or none at all.
        $()(select).trigger("select2:selecting");
        $()(select).val("1").trigger("change");
        expect(select.value).toBe("1");
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
