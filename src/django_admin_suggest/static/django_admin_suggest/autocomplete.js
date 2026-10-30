/**
 * AutocompleteAddMixin: an autocomplete field (Select2) that finds nothing
 * offers to add what was typed, "+ Add “…”" under "No results found". It
 * opens the field's own "add" link, with what was typed in a field of the
 * add page: the admin's popup, or Unfold's modal (both read the link's
 * href as it's clicked); once saved, the admin chooses it.
 *
 * Its field: data-django-admin-suggest-add (the text, "%(term)s" the term)
 * and data-django-admin-suggest-add-field (the add page's field), on the
 * <select>.
 */
(() => {
    const CLASS = "django-admin-suggest-autocomplete-add";

    function searchField(instance) {
        // A single choice searches in the dropdown; a multiple one, in the
        // field itself.
        return (
            instance.$dropdown.find(".select2-search__field")[0] ||
            instance.$container.find(".select2-search__field")[0]
        );
    }

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

    function offer(select, instance) {
        const term = (searchField(instance)?.value || "").trim();
        if (!term || !document.getElementById(`add_${select.id}`)) return;
        const item = document.createElement("li");
        item.id = `${select.id}-${CLASS}`;
        // Select2's look of the option one would choose; without
        // aria-selected, Select2 doesn't take it for one of its own.
        item.className = `select2-results__option select2-results__option--highlighted ${CLASS}`;
        item.setAttribute("role", "option");
        item.textContent = `+ ${select.dataset.djangoAdminSuggestAdd.replace(
            "%(term)s",
            term,
        )}`;
        item.addEventListener("click", () => add(select, instance, term));
        instance.$results.append(item);
    }

    function bind(select) {
        const instance = django.jQuery(select).data("select2");
        if (!instance || select.dataset.djangoAdminSuggestBound) return;
        select.dataset.djangoAdminSuggestBound = "on";
        instance.on("results:message", (params) => {
            if (params.message === "noResults") offer(select, instance);
        });
        // Enter adds it: before Select2, which would choose its highlighted
        // option (none of its own).
        const enter = (event) => {
            const item = document.getElementById(`${select.id}-${CLASS}`);
            if (event.key !== "Enter" || !item || !instance.isOpen()) return;
            event.preventDefault();
            event.stopPropagation();
            item.click();
        };
        instance.$dropdown[0].addEventListener("keydown", enter, true);
        instance.$container[0].addEventListener("keydown", enter, true);
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
