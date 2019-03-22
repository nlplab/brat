from simstring.database.base import BaseDatabase
import sqlite3

_CREATE_STRINGS_SQL = u"""
CREATE TABLE IF NOT EXISTS strings (
  id INTEGER PRIMARY KEY,
  string TEXT UNIQUE
);
"""

_CREATE_FEATURES_SQL = u"""
CREATE TABLE IF NOT EXISTS features (
  id INTEGER PRIMARY KEY,
  size INTEGER,
  feature TEXT,
  string_id INTEGER
);
"""

_INDEX_FEATURES_SQL = u"""
CREATE INDEX IF NOT EXISTS features_index
ON features (size, feature);
"""

_INSERT_STRING_SQL = u"""
INSERT INTO strings (string) VALUES (?);
"""

_INSERT_FEATURE_SQL = u"""
INSERT INTO features (size, feature, string_id) VALUES (?, ?, ?);
"""

_FIND_STRINGS_SQL = u"""
SELECT string
FROM strings
JOIN features ON features.string_id = strings.id
WHERE features.size = ?
  AND features.feature = ?;
"""

_FIND_MAX_FEATURES = u"""
SELECT DISTINCT MAX(size) FROM features;
"""

_FIND_MIN_FEATURES = u"""
SELECT DISTINCT MIN(size) FROM features;
"""

class SQLite3Database(BaseDatabase):
    def __init__(self, feature_extractor):
        self.feature_extractor = feature_extractor

    def use(self, connection_or_filename):
        if isinstance(connection_or_filename, sqlite3.Connection):
            self.connection = connection_or_filename
        else:
            self.connection = sqlite3.connect(connection_or_filename)

        cursor = self.connection.cursor()
        cursor.execute(_CREATE_STRINGS_SQL)
        cursor.execute(_CREATE_FEATURES_SQL)
        cursor.execute(_INDEX_FEATURES_SQL)
        self.connection.commit()
        cursor.close()
        return self

    def add(self, string):
        features = self.feature_extractor.features(string)
        size = len(features)
        cursor = self.connection.cursor()

        try:
            cursor.execute(_INSERT_STRING_SQL, (string,))
        except sqlite3.IntegrityError:
            return self

        string_id = cursor.lastrowid
        for feature in features:
            cursor.execute(_INSERT_FEATURE_SQL, (size, feature, string_id))
        self.connection.commit()
        cursor.close()
        return self

    def lookup_strings_by_feature_set_size_and_feature(self, size, feature):
        cursor = self.connection.cursor()
        cursor.execute(_FIND_STRINGS_SQL, (size, feature))
        rows = cursor.fetchall()
        cursor.close()
        return [row[0] for row in rows]

    def min_feature_size(self):
        cursor = self.connection.cursor()
        cursor.execute(_FIND_MIN_FEATURES)
        row = cursor.fetchone()
        cursor.close()
        return row[0]

    def max_feature_size(self):
        cursor = self.connection.cursor()
        cursor.execute(_FIND_MAX_FEATURES)
        row = cursor.fetchone()
        cursor.close()
        return row[0]

    def close(self):
        self.connection.close()
