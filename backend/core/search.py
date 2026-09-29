"""Accent insensitive search for every DRF viewset.

Typing ``azu`` must find ``Azúcar``. Django's ``icontains`` is case insensitive
but accent sensitive, and SQLite has no ``unaccent``, so this module registers
an equivalent scalar function on each new connection and ships a
``SearchFilter`` that compares against the accent stripped value.

The same normalisation is applied to both sides, so ``azucar``, ``AZUCAR`` and
``Azúcar`` are all equivalent. ``ñ`` folds to ``n``, which means ``ano`` also
finds ``año`` and vice versa.
"""

import unicodedata

from django.db import connection
from django.db.backends.signals import connection_created
from django.db.models import F, Func, Q
from rest_framework.filters import SearchFilter

#: DRF search prefixes mapped to the ORM lookups this filter can express.
PREFIX_LOOKUPS = {
    '^': 'istartswith',
    '=': 'iexact',
    '@': 'icontains',
    '': 'icontains',
}

#: Shortest accent stripped term that is safe to compare. Below this the
#: normalised needle matches nearly every row ("ñ" becomes "n").
MIN_UNACCENT_LENGTH = 2

_unaccent_ready = False


def strip_accents(value) -> str:
    """Return ``value`` without diacritics, lowercased for comparison."""
    if value is None:
        return ''
    decomposed = unicodedata.normalize('NFKD', str(value))
    return ''.join(char for char in decomposed if not unicodedata.combining(char)).lower()


class Unaccent(Func):
    """SQL ``UNACCENT(col)``; provided by the connection callback below."""

    function = 'UNACCENT'
    arity = 1


def register_unaccent(sender, connection, **kwargs) -> None:
    """Install the ``unaccent`` SQL function on every new connection."""
    global _unaccent_ready
    try:
        if connection.vendor == 'sqlite':
            connection.connection.create_function(
                'unaccent', 1, strip_accents, deterministic=True
            )
        elif connection.vendor == 'postgresql':
            # Best effort: the extension may not be installed yet.
            with connection.cursor() as cursor:
                cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent')
        else:
            return
    except Exception:  # pragma: no cover - driver or permission dependent
        return
    _unaccent_ready = True


def unaccent_ready() -> bool:
    """True when the current connection can evaluate ``UNACCENT()``."""
    global _unaccent_ready
    if not _unaccent_ready:
        # Covers connections opened before this module was imported.
        try:
            connection.connection.create_function(
                'unaccent', 1, strip_accents, deterministic=True
            )
        except Exception:  # pragma: no cover
            return False
        _unaccent_ready = True
    return True


connection_created.connect(register_unaccent, dispatch_uid='mayu.core.search.unaccent')


class UnaccentSearchFilter(SearchFilter):
    """``SearchFilter`` that ignores accents across every ``search_fields``.

    Falls back to plain ``icontains`` on the raw column if the ``unaccent``
    function is unavailable, so a search never fails with a SQL error.
    """

    def filter_queryset(self, request, queryset, view):
        search_fields = getattr(view, 'search_fields', None)
        if not search_fields:
            return queryset

        terms = self.get_search_terms(request)
        if not terms:
            return queryset

        for term in terms:
            queryset = self._apply_term(queryset, search_fields, term)
        return queryset

    def _apply_term(self, queryset, search_fields, term):
        raw = str(term).strip()
        needle = strip_accents(raw)
        if not needle:
            return queryset

        # A needle that collapses to a single character would match almost
        # anything: "ñ" normalises to "n". Keep the original, accent bearing
        # term for those so the search stays precise.
        use_unaccent = unaccent_ready() and len(needle) >= MIN_UNACCENT_LENGTH
        condition = Q()

        for index, entry in enumerate(search_fields):
            prefix, _, field = str(entry).partition('=')
            if prefix not in PREFIX_LOOKUPS:
                prefix, field = '', str(entry)
            field = field.strip()
            if not field:
                continue
            lookup = PREFIX_LOOKUPS[prefix]
            if use_unaccent:
                alias = f'_unaccent_{index}'
                queryset = queryset.annotate(**{alias: Unaccent(F(field))})
                condition |= Q(**{f'{alias}__{lookup}': needle})
            else:
                condition |= Q(**{f'{field}__{lookup}': raw})

        return queryset.filter(condition) if condition else queryset
