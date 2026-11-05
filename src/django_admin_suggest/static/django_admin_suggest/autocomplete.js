/**
 * AutocompleteAddMixin: an autocomplete field (Select2) offers to add what
 * was typed, "+ Add “…”": under "No results found", or (by its "when")
 * after the objects found too. It opens the field's own "add" link, with
 * what was typed in a field of the add page: the admin's popup, or Unfold's
 * modal (both read the link's href as it's clicked); once saved, the admin
 * chooses it.
 *
 * It's one more of Select2's options (its data marked as this one): the
 * arrows and the mouse reach it, Enter or a click on it adds; choosing it
 * is stopped (select2:selecting) before Select2 would take it for a value.
 *
 * Its field: data-django-admin-suggest-add (the text, "%(term)s" the term),
 * data-django-admin-suggest-add-field (the add page's field) and
 * data-django-admin-suggest-add-when ("empty", "always", "no_exact"), on
 * the <select>.
 */
(() => {
    const CLASS = "django-admin-suggest-autocomplete-add";
    const OPTION = ".select2-results__option[aria-selected]";

    const normal = (text) => text.trim().replace(/\s+/g, " ").toLowerCase();

    function add(select, instance, term) {
        const link = document.getElementById(`add_${select.id}`);
        instance.close();
        const href = link.getAttribute("href");
        const field = select.dataset.djangoAdminSuggestAddField;
        if (field) {
            const url = new URL(link.href);
            url.searchParams.set(field, term);
            link.setAttribute("href", url.href);
        }
        link.click();
        link.setAttribute("href", href);
    }

    /** Whether to offer it, by its "when", with what's found. */
    function offers(select, found, term) {
        const when = select.dataset.djangoAdminSuggestAddWhen;
        if (when === "always") return true;
        if (when === "no_exact") {
            const typed = normal(term);
            return found.every((text) => normal(text) !== typed);
        }
        return found.length === 0; // "empty"
    }

    function offer(select, instance, params) {
        // Select2 empties its results for a new search: once, the last.
        const results = instance.$results[0];
        // Pages yet to come: after the last of them.
        if (params.data.pagination?.more) return;
        const term = (params.query.term || "").trim();
        if (!term || !document.getElementById(`add_${select.id}`)) return;
        const utils = django.jQuery.fn.select2.amd.require("select2/utils");
        const found = [...results.querySelectorAll(OPTION)].map(
            (option) => utils.GetData(option, "data").text,
        );
        if (!offers(select, found, term)) return;

        const text = `+ ${select.dataset.djangoAdminSuggestAdd.replace(
            "%(term)s",
            term,
        )}`;
        const item = document.createElement("li");
        item.id = `${select.id}-${CLASS}`;
        item.className = `select2-results__option ${CLASS}`;
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", "false");
        item.textContent = text;
        utils.StoreData(item, "data", {
            id: "",
            text,
            _resultId: item.id,
            djangoAdminSuggestAdd: term,
        });
        results.append(item);
        // Nothing else to choose: this one, for Enter.
        if (!found.length) django.jQuery(item).trigger("mouseenter");
    }

    function bind(select) {
        const instance = django.jQuery(select).data("select2");
        if (!instance || select.dataset.djangoAdminSuggestBound) return;
        select.dataset.djangoAdminSuggestBound = "on";
        // After Select2's own listeners: its options are there.
        instance.on("results:all", (params) => offer(select, instance, params));
        instance.on("results:append", (params) =>
            offer(select, instance, params),
        );
        django.jQuery(select).on("select2:selecting", (event) => {
            const term = event.params?.args?.data?.djangoAdminSuggestAdd;
            if (term === undefined) return;
            event.preventDefault(); // Not a value.
            add(select, instance, term);
        });
    }

    function setup() {
        // Select2's events are jQuery's: a native listener doesn't hear them.
        django
            .jQuery(document)
            .on("select2:opening", "select[data-django-admin-suggest-add]", (
                event,
            ) => bind(event.target));
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setup);
    } else {
        setup();
    }
})();
