CREATE TABLE documents (
  id TEXT PRIMARY KEY, election TEXT NOT NULL, kind TEXT NOT NULL, urn TEXT NOT NULL,
  revision INTEGER NOT NULL, digest TEXT NOT NULL, hash TEXT NOT NULL,
  document TEXT NOT NULL, manifest TEXT NOT NULL, fingerprint TEXT NOT NULL,
  receipt TEXT NOT NULL, received TEXT NOT NULL,
  UNIQUE(election,kind,urn,revision)
);
CREATE INDEX election_docs ON documents(election,kind,urn,revision);
CREATE TABLE package_chunks (
  document_id TEXT NOT NULL REFERENCES documents(id),
  sequence INTEGER NOT NULL, content BLOB NOT NULL,
  PRIMARY KEY(document_id,sequence)
);
