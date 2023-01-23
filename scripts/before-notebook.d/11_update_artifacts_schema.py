#!/usr/bin/env python
import sqlite3

from dataclasses import fields
from jupyterlab_chameleon import db

try:
    with sqlite3.connect("/work/.chameleon/chameleon.db") as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(artifacts);")
        columns = cur.fetchall()
        column_names = [c[1] for c in columns]

        expected_fields = fields(db.LocalArtifact)
        expected_columns = []
        type_map = {
          str: "text"  
        }

        for field in expected_fields:
            if field.name not in column_names:
                print(f"Migrating artifact database, adding '{field.name}' column")
                column_type = type_map[field.type]
                cur.execute(f"ALTER TABLE artifacts ADD COLUMN {field.name} {column_type};")
        cur.close()
except sqlite3.OperationalError:
    # If database does not exist, no migration to run.
    pass