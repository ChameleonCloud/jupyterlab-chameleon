from collections import namedtuple
import os
import sqlite3

from .exception import ArtifactNotFoundError, DuplicateArtifactError

import logging
LOG = logging.getLogger(__name__)

DATABASE_NAME = 'chameleon'

ARTIFACT_COLUMNS = ['id', 'path', 'deposition_repo', 'ownership']
Artifact = namedtuple('Artifact', ARTIFACT_COLUMNS)


class DB:
    def __init__(self, database=None):
        if not database:
            raise ValueError('A database path is required')
        try:
            os.makedirs(os.path.dirname(database), exist_ok=True)
        except:
            LOG.exception(f'Failed to lazy-create DB path {database}')
        self.database = database

    def list_artifacts(self):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(f'select {",".join(ARTIFACT_COLUMNS)} from artifacts')
            return [dict(Artifact(*row)._asdict()) for row in cur.fetchall()]

    def insert_artifact(self, artifact: Artifact):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                (f'insert into artifacts ({",".join(ARTIFACT_COLUMNS)}) '
                 'values (?, ?, ?, ?)'),
                tuple(artifact))

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
            updates = [f'{col}=?' for col in ARTIFACT_COLUMNS].join(',')
            cur.execute(f'update artifacts set {updates} where path=?',
                tuple(artifact) + (path,))

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)
