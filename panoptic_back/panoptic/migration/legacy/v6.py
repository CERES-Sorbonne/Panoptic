v6_sql = """
CREATE INDEX idx_folder_id ON instances(folder_id);
CREATE INDEX idx_instance_values_instance_id ON instance_property_values(instance_id);
CREATE INDEX idx_vectors_sha1 ON vectors(sha1);
"""
