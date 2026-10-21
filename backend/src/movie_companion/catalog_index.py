"""One bounded, revision-aware prepared snapshot of authoritative SQLite metadata."""
from threading import Lock

from .catalog_search import PreparedCatalog


class SavedCatalogIndex:
    def __init__(self, store):
        self.store = store
        self._lock = Lock()
        self._revision = None
        self._snapshot = None

    def get(self):
        with self._lock:
            revision = self.store.search_revision()
            if self._snapshot is not None and revision == self._revision:
                return self._snapshot
            # Do not label a snapshot current if a writer changed the DB during its read.
            for _ in range(3):
                before = self.store.search_revision()
                snapshot = PreparedCatalog(self.store.identity_movies())
                after = self.store.search_revision()
                if before == after:
                    self._snapshot, self._revision = snapshot, after
                    return snapshot
            self._revision = None
            return snapshot

    def suggest(self, query):
        return self.get().suggestions.suggest(query)
