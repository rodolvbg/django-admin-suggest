/**
 * SearchSuggestionsMixin: the changelist's search box suggests the objects
 * it finds as one types (an ARIA combobox); choosing one, with the mouse or
 * the keyboard, opens its change page. Enter without choosing one searches
 * as always. It may offer to add what was typed (its add page): when
 * nothing is found, or after those found, as the server says. Its
 * configuration: the JSON of #django-admin-suggest-search.
 *
 * The suggestions look like the admin's autocomplete fields: Select2's
 * dropdown (its markup and classes, on the admin's stylesheets, and
 * Unfold's), without Select2 itself: the search box stays a text box.
 */
(() => {
    const DELAY = 200;

    function config() {
        const node = document.getElementById("django-admin-suggest-search");
        try {
            return node ? JSON.parse(node.textContent) : null;
        } catch {
            return null;
        }
    }

    function setup() {
        const options = config();
        const input = document.getElementById("searchbar");
        if (!options || !input || input.dataset.djangoAdminSuggestSearch)
            return;
        input.dataset.djangoAdminSuggestSearch = "on";

        const span = (className) => {
            const node = document.createElement("span");
            node.className = className;
            return node;
        };
        const container = span(
            "select2-container select2-container--admin-autocomplete " +
                "select2-container--open django-admin-suggest-search-dropdown",
        );
        const dropdown = span("select2-dropdown select2-dropdown--below");
        const results = span("select2-results");
        const list = document.createElement("ul");
        list.id = "django-admin-suggest-search-suggestions";
        list.className = "select2-results__options";
        list.setAttribute("role", "listbox");
        list.setAttribute("aria-label", options.texts.label);
        results.append(list);
        dropdown.append(results);
        container.append(dropdown);
        container.hidden = true;
        const box = input.parentElement;
        box.classList.add("django-admin-suggest-search");
        box.append(container);

        input.setAttribute("role", "combobox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-controls", list.id);
        input.setAttribute("aria-expanded", "false");
        input.setAttribute("autocomplete", "off");

        let timer = null;
        let request = null;
        let links = [];
        let active = -1;

        function close() {
            container.hidden = true;
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
            active = -1;
        }

        function highlight(index) {
            active = index;
            // As Select2: highlighted by its class; aria-selected stays for
            // a chosen value (Unfold draws a check on it). The active one is
            // aria-activedescendant's.
            links.forEach((link, i) => {
                link.parentElement.classList.toggle(
                    "select2-results__option--highlighted",
                    i === index,
                );
            });
            input.setAttribute(
                "aria-activedescendant",
                links[index].parentElement.id,
            );
            links[index].parentElement.scrollIntoView?.({ block: "nearest" });
        }

        function show(found, add) {
            links = [];
            active = -1;
            list.replaceChildren();
            if (!found.length) {
                const empty = document.createElement("li");
                empty.className =
                    "select2-results__option select2-results__message";
                empty.textContent = options.texts.empty;
                list.append(empty);
            }
            // Adding it is one more option, the last.
            const items = add ? [...found, { ...add, add: true }] : found;
            items.forEach((result, index) => {
                const item = document.createElement("li");
                item.id = `${list.id}-${index}`;
                item.className = result.add
                    ? "select2-results__option django-admin-suggest-search-add"
                    : "select2-results__option";
                item.setAttribute("role", "option");
                item.setAttribute("aria-selected", "false");
                const link = document.createElement("a");
                link.href = result.url;
                link.textContent = result.text;
                link.tabIndex = -1;
                // Kept focus: the input's blur doesn't close it first.
                item.addEventListener("mousedown", (event) =>
                    event.preventDefault(),
                );
                item.addEventListener("mousemove", () => highlight(index));
                item.append(link);
                list.append(item);
                links.push(link);
            });
            // Under the search field, as wide as it (as Select2 places it):
            // the input, or the box around it when that draws the field
            // (Unfold's input has no border of its own).
            const border = getComputedStyle(input);
            const field =
                border.borderTopStyle === "none" ||
                Number.parseFloat(border.borderTopWidth) === 0
                    ? box
                    : input;
            const top = field === box ? 0 : input.offsetTop;
            const left = field === box ? 0 : input.offsetLeft;
            container.style.left = `${left}px`;
            container.style.top = `${top + field.offsetHeight}px`;
            container.style.width = `${field.offsetWidth}px`;
            container.hidden = false;
            input.setAttribute("aria-expanded", "true");
        }

        async function suggest() {
            const term = input.value.trim();
            request?.abort();
            if (term.length < options.minLength) {
                close();
                return;
            }
            request = new AbortController();
            try {
                const response = await fetch(
                    `${options.url}?q=${encodeURIComponent(term)}`,
                    {
                        headers: { Accept: "application/json" },
                        credentials: "same-origin",
                        signal: request.signal,
                    },
                );
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                // Typed on meanwhile: this answer is old.
                if (input.value.trim() !== term) return;
                show(data.results, data.add);
            } catch {
                close(); // Aborted, or failed: the search still works.
            }
        }

        input.addEventListener("input", () => {
            clearTimeout(timer);
            timer = setTimeout(suggest, DELAY);
        });

        input.addEventListener("keydown", (event) => {
            const open = !container.hidden;
            if (event.key === "ArrowDown" && open && links.length) {
                event.preventDefault();
                highlight((active + 1) % links.length);
            } else if (event.key === "ArrowUp" && open && links.length) {
                event.preventDefault();
                highlight(active <= 0 ? links.length - 1 : active - 1);
            } else if (event.key === "Enter" && open && active >= 0) {
                event.preventDefault();
                links[active].click();
            } else if (event.key === "Escape" && open) {
                event.preventDefault();
                close();
            }
        });

        input.addEventListener("blur", close);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setup);
    } else {
        setup();
    }
})();
