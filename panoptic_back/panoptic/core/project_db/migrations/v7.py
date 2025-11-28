v7_sql = """
DROP TABLE IF EXISTS vectors;

CREATE TABLE vectors (
    type_id INTEGER,
    sha1 TEXT,
    data ARRAY,
    
    PRIMARY KEY (type_id, sha1),
    FOREIGN KEY (type_id) REFERENCES vector_type(id) ON DELETE CASCADE
);

CREATE INDEX idx_vectors_sha1 ON vectors(sha1);
"""
