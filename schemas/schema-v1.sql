-- WBKB structured index schema v1
-- Generated database (data/generated/index/wbkb.db) is rebuilt by the
-- indexer pipeline and never committed to Git.

PRAGMA journal_mode = DELETE;

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE sources (
  id           INTEGER PRIMARY KEY,
  source_id    TEXT NOT NULL UNIQUE,
  source_kind  TEXT NOT NULL,
  version      TEXT,
  content_hash TEXT,
  snapshot_id  TEXT
);

CREATE TABLE files (
  id            INTEGER PRIMARY KEY,
  source_id     INTEGER NOT NULL REFERENCES sources(id),
  relative_path TEXT NOT NULL,
  filename      TEXT NOT NULL,
  extension     TEXT NOT NULL,
  size          INTEGER NOT NULL,
  sha256        TEXT NOT NULL,
  line_count    INTEGER,
  parse_status  TEXT NOT NULL DEFAULT 'OK',
  parse_error   TEXT,
  UNIQUE (source_id, relative_path)
);

CREATE TABLE types (
  id                    INTEGER PRIMARY KEY,
  source_id             INTEGER NOT NULL REFERENCES sources(id),
  file_id               INTEGER NOT NULL REFERENCES files(id),
  namespace             TEXT,
  name                  TEXT NOT NULL,
  full_name             TEXT NOT NULL,
  kind                  TEXT NOT NULL,
  visibility            TEXT,
  is_abstract           INTEGER NOT NULL DEFAULT 0,
  is_static             INTEGER NOT NULL DEFAULT 0,
  is_sealed             INTEGER NOT NULL DEFAULT 0,
  is_compiler_generated INTEGER NOT NULL DEFAULT 0,
  parent_type_id        INTEGER REFERENCES types(id),
  start_line            INTEGER,
  end_line              INTEGER,
  UNIQUE (source_id, full_name)
);

CREATE TABLE methods (
  id           INTEGER PRIMARY KEY,
  source_id    INTEGER NOT NULL REFERENCES sources(id),
  type_id      INTEGER NOT NULL REFERENCES types(id),
  file_id      INTEGER NOT NULL REFERENCES files(id),
  name         TEXT NOT NULL,
  signature    TEXT NOT NULL,
  return_type  TEXT,
  visibility   TEXT,
  is_static    INTEGER NOT NULL DEFAULT 0,
  is_virtual   INTEGER NOT NULL DEFAULT 0,
  is_override  INTEGER NOT NULL DEFAULT 0,
  is_abstract  INTEGER NOT NULL DEFAULT 0,
  start_line   INTEGER,
  end_line    INTEGER
);

CREATE TABLE fields (
  id          INTEGER PRIMARY KEY,
  source_id   INTEGER NOT NULL REFERENCES sources(id),
  type_id     INTEGER NOT NULL REFERENCES types(id),
  file_id     INTEGER NOT NULL REFERENCES files(id),
  name        TEXT NOT NULL,
  field_type  TEXT,
  visibility  TEXT,
  is_static   INTEGER NOT NULL DEFAULT 0,
  is_readonly INTEGER NOT NULL DEFAULT 0,
  is_const    INTEGER NOT NULL DEFAULT 0,
  start_line  INTEGER
);

CREATE TABLE properties (
  id             INTEGER PRIMARY KEY,
  source_id      INTEGER NOT NULL REFERENCES sources(id),
  type_id        INTEGER NOT NULL REFERENCES types(id),
  file_id        INTEGER NOT NULL REFERENCES files(id),
  name           TEXT NOT NULL,
  property_type  TEXT,
  visibility     TEXT,
  has_getter     INTEGER NOT NULL DEFAULT 0,
  has_setter     INTEGER NOT NULL DEFAULT 0,
  is_static      INTEGER NOT NULL DEFAULT 0,
  start_line     INTEGER,
  end_line       INTEGER
);

CREATE TABLE inheritance (
  id             INTEGER PRIMARY KEY,
  source_id      INTEGER NOT NULL REFERENCES sources(id),
  type_id        INTEGER NOT NULL REFERENCES types(id),
  relation       TEXT NOT NULL,
  target_name    TEXT NOT NULL,
  target_type_id INTEGER REFERENCES types(id)
);

CREATE TABLE strings (
  id             INTEGER PRIMARY KEY,
  source_id      INTEGER NOT NULL REFERENCES sources(id),
  file_id        INTEGER NOT NULL REFERENCES files(id),
  type_id        INTEGER REFERENCES types(id),
  method_id      INTEGER REFERENCES methods(id),
  value          TEXT NOT NULL,
  classification TEXT NOT NULL DEFAULT 'other',
  start_line     INTEGER
);

CREATE INDEX idx_types_full_name ON types(full_name);
CREATE INDEX idx_types_name ON types(name);
CREATE INDEX idx_methods_name ON methods(name);
CREATE INDEX idx_methods_type ON methods(type_id);
CREATE INDEX idx_fields_name ON fields(name);
CREATE INDEX idx_properties_name ON properties(name);
CREATE INDEX idx_strings_value ON strings(value);
CREATE INDEX idx_files_path ON files(relative_path);
CREATE INDEX idx_inheritance_type ON inheritance(type_id);
CREATE INDEX idx_inheritance_target ON inheritance(target_name);
