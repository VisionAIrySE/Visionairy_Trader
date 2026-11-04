-- Cover the complete composite embedding-profile foreign key.
create index embeddings_profile_dimensions on trader.chunk_embeddings(profile_id,dimensions);
