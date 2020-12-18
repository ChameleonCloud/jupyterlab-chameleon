from dataclasses import asdict
import os

import pytest

from .db import Artifact, DB
from .exception import ArtifactNotFoundError, DuplicateArtifactError


class TestDB:
    no_id = Artifact(
        id=None, path='./foo', deposition_repo='repo', ownership='ownership')
    with_id = Artifact(
        id='1', path='./foo', deposition_repo='repo', ownership='ownership')
    duplicate = Artifact(
        id='2', path='./foo', deposition_repo='repo', ownership='ownership')

    def init_db(self, database=DB.IN_MEMORY):
        db = DB(database)
        db.build_schema()
        return db

    def test_lazy_create_path(self, tmpdir):
        self.init_db(f'{tmpdir}/subfolder/mydb')
        assert os.path.exists(f'{tmpdir}/subfolder')

    def test_insert(self):
        db = self.init_db()
        db.insert_artifact(self.no_id)
        assert db.list_artifacts()[0] == self.no_id

    def test_update_id(self):
        db = self.init_db()
        db.insert_artifact(self.no_id)
        db.update_artifact(self.with_id)
        assert db.list_artifacts()[0] == self.with_id

    def test_update_duplicate(self):
        db = self.init_db()
        db.insert_artifact(self.no_id)
        db.insert_artifact(self.no_id)
        with pytest.raises(DuplicateArtifactError):
            db.update_artifact(self.with_id)

    def test_update_change_id(self):
        db = self.init_db()
        db.insert_artifact(self.with_id)
        with pytest.raises(DuplicateArtifactError):
            db.update_artifact(self.duplicate)

    def test_update_missing(self):
        db = self.init_db()
        with pytest.raises(ArtifactNotFoundError):
            db.update_artifact(self.with_id)

    def test_reset(self):
        db = self.init_db()
        db.insert_artifact(self.no_id)
        db.reset()
        assert len(db.list_artifacts()) == 0
