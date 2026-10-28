import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const SCRIPT =
    "../../src/django_admin_suggest/static/django_admin_suggest/search.js";

const CONFIG = {
    url: "/admin/gallery/image/search-suggestions/",
    minLength: 2,
    texts: { label: "Suggestions", empty: "Nothing found." },
};

const RESULTS = [
    { id: "1", text: "Snowy peak", url: "/admin/gallery/image/1/change/" },
    { id: "2", text: "Cabin", url: "/admin/gallery/image/2/change/" },
];

function page(config = CONFIG) {
    const json =
        config === null
            ? ""
            : `<script id="django-admin-suggest-search" type="application/json">${
                  typeof config === "string" ? config : JSON.stringify(config)
              }</script>`;
    document.body.innerHTML = `${json}<form id="changelist-search"><div><input type="text" id="searchbar" name="q"></div></form>`;
}

async function load(readyState = "complete") {
    vi.spyOn(document, "readyState", "get").mockReturnValue(readyState);
    vi.resetModules();
    await import(SCRIPT);
}

function answer(results = RESULTS, ok = true) {
    return vi.fn(async () => ({
        ok,
        status: ok ? 200 : 500,
        json: async () => ({ results }),
    }));
}

const input = () => document.getElementById("searchbar");
const list = () =>
    document.getElementById("django-admin-suggest-search-suggestions");
const dropdown = () =>
    document.querySelector(".django-admin-suggest-search-dropdown");
const options = () => [...list().querySelectorAll('[role="option"]')];

async function type(value) {
    input().value = value;
    input().dispatchEvent(new Event("input"));
    await vi.advanceTimersByTimeAsync(200);
}

function key(name) {
    const event = new KeyboardEvent("keydown", { key: name, cancelable: true });
    input().dispatchEvent(event);
    return event;
}

describe("search.js", () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it("makes the search box a combobox", async () => {
        page();
        await load();
        expect(input().getAttribute("role")).toBe("combobox");
        expect(input().getAttribute("aria-controls")).toBe(list().id);
        expect(input().getAttribute("aria-expanded")).toBe("false");
        expect(input().getAttribute("autocomplete")).toBe("off");
        expect(list().getAttribute("role")).toBe("listbox");
        expect(list().getAttribute("aria-label")).toBe("Suggestions");
        expect(dropdown().hidden).toBe(true);
        // Select2's markup: the admin's autocomplete fields' look.
        expect(dropdown().className).toBe(
            "select2-container select2-container--admin-autocomplete " +
                "select2-container--open django-admin-suggest-search-dropdown",
        );
        expect(list().className).toBe("select2-results__options");
        expect(list().parentElement.className).toBe("select2-results");
        expect(
            input().parentElement.classList.contains(
                "django-admin-suggest-search",
            ),
        ).toBe(true);
        // Once, if loaded twice.
        await load();
        expect(document.querySelectorAll('[role="listbox"]')).toHaveLength(1);
    });

    it("suggests what the server finds, as one types", async () => {
        const fetch = answer();
        vi.stubGlobal("fetch", fetch);
        page();
        await load();
        await type("s");
        expect(fetch).not.toHaveBeenCalled();
        await type(" snow ");
        expect(fetch).toHaveBeenCalledOnce();
        const [url, init] = fetch.mock.calls[0];
        expect(url).toBe(`${CONFIG.url}?q=snow`);
        expect(init.credentials).toBe("same-origin");
        expect(dropdown().hidden).toBe(false);
        expect(input().getAttribute("aria-expanded")).toBe("true");
        expect(options().map((o) => o.textContent)).toEqual([
            "Snowy peak",
            "Cabin",
        ]);
        expect(options()[0].className).toBe("select2-results__option");
        expect(dropdown().style.width).toMatch(/px$/);
        expect(dropdown().style.left).toBe("0px");
        const link = options()[0].querySelector("a");
        expect(link.getAttribute("href")).toBe(RESULTS[0].url);
        expect(link.tabIndex).toBe(-1);

        // Shorter again: closed.
        await type("s");
        expect(dropdown().hidden).toBe(true);
    });

    it("says when there's nothing", async () => {
        vi.stubGlobal("fetch", answer([]));
        page();
        await load();
        await type("zz");
        expect(options()).toHaveLength(0);
        expect(list().textContent).toBe("Nothing found.");
        expect(list().firstElementChild.className).toBe(
            "select2-results__option select2-results__message",
        );
        expect(key("ArrowDown").defaultPrevented).toBe(false);
        expect(key("Enter").defaultPrevented).toBe(false);
    });

    it("offers to add what isn't found", async () => {
        const add = {
            text: "Add “Lake”",
            url: "/admin/gallery/image/add/?title=Lake",
        };
        vi.stubGlobal(
            "fetch",
            vi.fn(async () => ({
                ok: true,
                status: 200,
                json: async () => ({ results: [], add }),
            })),
        );
        const click = vi
            .spyOn(HTMLAnchorElement.prototype, "click")
            .mockImplementation(() => {});
        page();
        await load();
        await type("Lake");
        expect(list().firstElementChild.textContent).toBe("Nothing found.");
        expect(options()).toHaveLength(1);
        expect(options()[0].className).toBe(
            "select2-results__option django-admin-suggest-search-add",
        );
        const link = options()[0].querySelector("a");
        expect(link.textContent).toBe(add.text);
        expect(link.getAttribute("href")).toBe(add.url);
        expect(key("ArrowDown").defaultPrevented).toBe(true);
        expect(key("Enter").defaultPrevented).toBe(true);
        expect(click.mock.contexts[0]).toBe(link);
    });

    it("waits for a pause, and forgets an old answer", async () => {
        let resolve;
        const fetch = vi.fn(
            () =>
                new Promise((done) => {
                    resolve = done;
                }),
        );
        vi.stubGlobal("fetch", fetch);
        page();
        await load();
        input().value = "sn";
        input().dispatchEvent(new Event("input"));
        input().value = "sno";
        input().dispatchEvent(new Event("input"));
        await vi.advanceTimersByTimeAsync(200);
        expect(fetch).toHaveBeenCalledOnce();
        input().value = "snow";
        resolve({ ok: true, json: async () => ({ results: RESULTS }) });
        await vi.advanceTimersByTimeAsync(0);
        expect(dropdown().hidden).toBe(true);
    });

    it("cancels what it asked before, and survives errors", async () => {
        const signals = [];
        vi.stubGlobal(
            "fetch",
            vi.fn((_url, init) => {
                signals.push(init.signal);
                return new Promise(() => {});
            }),
        );
        page();
        await load();
        await type("sn");
        await type("sno");
        expect(signals[0].aborted).toBe(true);
        expect(signals[1].aborted).toBe(false);

        vi.stubGlobal("fetch", answer(RESULTS, false));
        await type("snow");
        expect(dropdown().hidden).toBe(true);
    });

    it("is chosen with the keyboard", async () => {
        vi.stubGlobal("fetch", answer());
        const click = vi
            .spyOn(HTMLAnchorElement.prototype, "click")
            .mockImplementation(() => {});
        page();
        await load();
        await type("snow");
        expect(key("ArrowDown").defaultPrevented).toBe(true);
        expect(input().getAttribute("aria-activedescendant")).toBe(
            options()[0].id,
        );
        expect(options()[0].getAttribute("aria-selected")).toBe("false");
        expect(options()[0].className).toBe(
            "select2-results__option select2-results__option--highlighted",
        );
        key("ArrowDown");
        expect(options()[0].className).toBe("select2-results__option");
        key("ArrowDown"); // Round to the first.
        expect(
            options()[0].classList.contains(
                "select2-results__option--highlighted",
            ),
        ).toBe(true);
        key("ArrowUp"); // And back to the last.
        expect(
            options()[1].classList.contains(
                "select2-results__option--highlighted",
            ),
        ).toBe(true);
        key("ArrowUp");
        expect(
            options()[0].classList.contains(
                "select2-results__option--highlighted",
            ),
        ).toBe(true);
        expect(key("a").defaultPrevented).toBe(false);
        expect(key("Enter").defaultPrevented).toBe(true);
        expect(click).toHaveBeenCalledOnce();
        expect(click.mock.contexts[0].getAttribute("href")).toBe(
            RESULTS[0].url,
        );

        // Escape closes; then the keys are the input's again.
        expect(key("Escape").defaultPrevented).toBe(true);
        expect(dropdown().hidden).toBe(true);
        expect(input().hasAttribute("aria-activedescendant")).toBe(false);
        expect(key("Escape").defaultPrevented).toBe(false);
        expect(key("ArrowDown").defaultPrevented).toBe(false);
        expect(key("ArrowUp").defaultPrevented).toBe(false);
    });

    it("searches as always with Enter and nothing chosen", async () => {
        vi.stubGlobal("fetch", answer());
        page();
        await load();
        await type("snow");
        expect(key("Enter").defaultPrevented).toBe(false);
    });

    it("is chosen with the mouse, keeping the focus", async () => {
        vi.stubGlobal("fetch", answer());
        page();
        await load();
        await type("snow");
        const [first, second] = options();
        second.dispatchEvent(new MouseEvent("mousemove"));
        expect(second.classList).toContain(
            "select2-results__option--highlighted",
        );
        expect(first.classList).not.toContain(
            "select2-results__option--highlighted",
        );
        const down = new MouseEvent("mousedown", { cancelable: true });
        second.dispatchEvent(down);
        expect(down.defaultPrevented).toBe(true);
        // Leaving the box closes it.
        input().dispatchEvent(new Event("blur"));
        expect(dropdown().hidden).toBe(true);
    });

    it("goes under the box when the box draws the field (Unfold)", async () => {
        vi.stubGlobal("fetch", answer());
        page();
        await load();
        input().style.border = "none";
        await type("snow");
        expect(dropdown().style.left).toBe("0px");
        expect(dropdown().style.top).toBe("0px"); // (jsdom has no layout)
        // Tailwind's reset: a border, 0 wide.
        input().style.border = "0 solid";
        await type("snowy");
        expect(dropdown().style.left).toBe("0px");
    });

    it("scrolls the chosen one into view", async () => {
        vi.stubGlobal("fetch", answer());
        const scroll = vi.fn();
        HTMLElement.prototype.scrollIntoView = scroll;
        page();
        await load();
        await type("snow");
        key("ArrowDown");
        expect(scroll).toHaveBeenCalledWith({ block: "nearest" });
        delete HTMLElement.prototype.scrollIntoView;
    });

    it("does nothing without its configuration or a search box", async () => {
        page(null);
        await load();
        expect(list()).toBe(null);
        expect(dropdown()).toBe(null);
        page("{nope");
        await load();
        expect(list()).toBe(null);
        document.body.innerHTML = `<script id="django-admin-suggest-search" type="application/json">${JSON.stringify(CONFIG)}</script>`;
        await load();
        expect(list()).toBe(null);
    });

    it("waits for the page when it's still loading", async () => {
        page();
        await load("loading");
        expect(list()).toBe(null);
        document.dispatchEvent(new Event("DOMContentLoaded"));
        expect(list()).not.toBe(null);
    });
});
