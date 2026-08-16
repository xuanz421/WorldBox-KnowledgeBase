-- WBKB structured index schema v2
-- Adds the reference layer (symbol_references / method_calls / type_references)
-- on top of the v1 declaration layer. Generated database is rebuilt by the
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
  id               INTEGER PRIMARY KEY,
  source_id        INTEGER NOT NULL REFERENCES sources(id),
  relative_path    TEXT NOT NULL,
  filename         TEXT NOT NULL,
  extension        TEXT NOT NULL,
  size             INTEGER NOT NULL,
  sha256           TEXT NOT NULL,
  line_count       INTEGER,
  parse_status     TEXT NOT NULL DEFAULT 'OK',
  parse_error      TEXT,
  reference_status TEXT NOT NULL DEFAULT 'OK',
  reference_error  TEXT,
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
  end_line     INTEGER
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

-- Reference layer (schema v2)

CREATE TABLE symbol_references (
  id                    INTEGER PRIMARY KEY,
  source_id             INTEGER NOT NULL REFERENCES sources(id),
  from_file_id          INTEGER NOT NULL REFERENCES files(id),
  from_type_id          INTEGER REFERENCES types(id),
  from_method_id        INTEGER REFERENCES methods(id),
  target_kind           TEXT NOT NULL,   -- field / property / method / type / constructor / unknown
  target_name           TEXT NOT NULL,   -- display hint, e.g. Actor.data
  target_logical_key    TEXT NOT NULL,   -- stable identity, e.g. field:Actor.data
  target_id             INTEGER,         -- resolved declaration id, NULL unless resolved
  reference_kind        TEXT NOT NULL,   -- read / write / read_write / type_use / ...
  start_line            INTEGER,
  start_column          INTEGER,
  end_line              INTEGER,
  end_column            INTEGER,
  resolution_status     TEXT NOT NULL,   -- resolved / ambiguous / unresolved / external
  resolution_confidence REAL NOT NULL DEFAULT 0
);

CREATE TABLE method_calls (
  id                    INTEGER PRIMARY KEY,
  source_id             INTEGER NOT NULL REFERENCES sources(id),
  caller_method_id      INTEGER REFERENCES methods(id),
  callee_method_id      INTEGER REFERENCES methods(id),
  callee_name           TEXT NOT NULL,
  callee_signature_hint TEXT,            -- e.g. (int,string)
  declaring_type_hint   TEXT,            -- e.g. Actor / Mathf
  file_id               INTEGER NOT NULL REFERENCES files(id),
  line                  INTEGER,
  column                INTEGER,
  resolution_status     TEXT NOT NULL    -- resolved / ambiguous / unresolved / external
);

CREATE TABLE type_references (
  id                INTEGER PRIMARY KEY,
  source_id         INTEGER NOT NULL REFERENCES sources(id),
  from_file_id      INTEGER NOT NULL REFERENCES files(id),
  from_type_id      INTEGER REFERENCES types(id),
  from_method_id    INTEGER REFERENCES methods(id),
  target_type_id    INTEGER REFERENCES types(id),
  target_name       TEXT NOT NULL,
  reference_kind    TEXT NOT NULL,       -- instantiate / parameter_type / return_type / field_type /
                                         -- property_type / typeof / cast / as / generic_argument /
                                         -- inherit / interface / attribute / type_use
  line              INTEGER,
  resolution_status TEXT NOT NULL
);

CREATE INDEX idx_types_full_name ON types(full_name);
CREATE INDEX idx_types_name ON types(name);
CREATE INDEX idx_methods_name ON methods(name);
CREATE INDEX idx_methods_type ON methods(type_id);
CREATE INDEX idx_methods_signature ON methods(signature);
CREATE INDEX idx_fields_name ON fields(name);
CREATE INDEX idx_properties_name ON properties(name);
CREATE INDEX idx_strings_value ON strings(value);
CREATE INDEX idx_files_path ON files(relative_path);
CREATE INDEX idx_inheritance_type ON inheritance(type_id);
CREATE INDEX idx_inheritance_target ON inheritance(target_name);

CREATE INDEX idx_symbol_references_target_id ON symbol_references(target_id);
CREATE INDEX idx_symbol_references_target_key ON symbol_references(target_logical_key);
CREATE INDEX idx_symbol_references_from_method ON symbol_references(from_method_id);
CREATE INDEX idx_method_calls_callee ON method_calls(callee_method_id);
CREATE INDEX idx_method_calls_caller ON method_calls(caller_method_id);
CREATE INDEX idx_type_references_target ON type_references(target_type_id);
