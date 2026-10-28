# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-28

### Added

- `SearchSuggestionsMixin` (from django-admin-tables, where it was until
  0.1.2): the changelist's search box suggests the objects its search finds
  as one types, and choosing one opens its change page. One query per
  suggestion request; `get_search_suggestions()`,
  `get_search_suggestion_label()` and `get_search_suggestion_url()` to
  customize it. With `search_suggestions_add`, when nothing is found, a
  link to add it, with what was typed in a field. Its suggestions look like
  the admin's autocomplete fields (Select2's dropdown, in Django's admin and
  in Unfold). Spanish translation of its texts.
