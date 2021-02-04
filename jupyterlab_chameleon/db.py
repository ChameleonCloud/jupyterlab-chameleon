from dataclasses import astuple, dataclass, fields
from importlib import resources
import os
import sqlite3

from .exception import ArtifactNotFoundError, DuplicateArtifactError

import logging
LOG = logging.getLogger(__name__)

DATABASE_NAME = 'chameleon'

@dataclass
class Artifact:
    id: str
    path: str
    deposition_repo: str
    ownership: str

ARTIFACT_COLUMNS = [f.name for f in fields(Artifact)]

class DB:
    IN_MEMORY = ':memory:'

    def __init__(self, database=None):
        if not database:
            raise ValueError('A database path is required')

        if database != DB.IN_MEMORY:
            try:
                os.makedirs(os.path.dirname(database), exist_ok=True)
            except OSError:
                LOG.exception(f'Failed to lazy-create DB path {database}')

        self.database = database
        self._conn = None

    def build_schema(self):
        with resources.open_text(__package__, 'db_schema.sql') as f:
            with self.connect() as conn:
                conn.executescript(f.read())

    def reset(self):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute('delete from artifacts')

    def list_artifacts(self):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(f'select {",".join(ARTIFACT_COLUMNS)} from artifacts')
            return [Artifact(*row) for row in cur.fetchall()]

    def insert_artifact(self, artifact: Artifact):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                (f'insert into artifacts ({",".join(ARTIFACT_COLUMNS)}) '
                 'values (?, ?, ?, ?)'),
                astuple(artifact))

    def update_artifact(self, artifact: Artifact):
        path = artifact.path
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute('select id from artifacts where path = ?', (path,))
            found = cur.fetchall()
            if len(found) > 1:
                raise DuplicateArtifactError(
                    'Multiple artifacts already found at %s', path)
            elif found and found[0][0] is not None:
                raise DuplicateArtifactError(
                    'Would create duplicate artifact at %s: %s', path, found[0][0])
            elif not found:
                raise ArtifactNotFoundError(
                    'Cannot find artifact at %s', path)
            updates = ','.join([f'{col}=?' for col in ARTIFACT_COLUMNS])
            cur.execute(f'update artifacts set {updates} where path=?',
                astuple(artifact) + (path,))

    def connect(self) -> sqlite3.Connection:
        if not self._conn:
            self._conn = sqlite3.connect(self.database)
        return self._conn
