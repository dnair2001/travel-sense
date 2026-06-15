import math

from app.services.hash_embeddings import HashEmbeddings


def test_embed_empty_text_returns_zero_vector():
    embedder = HashEmbeddings(dimensions=64)
    vector = embedder.embed_query("")
    assert len(vector) == 64
    assert all(v == 0.0 for v in vector)


def test_embed_non_alphanumeric_text_returns_zero_vector():
    embedder = HashEmbeddings(dimensions=64)
    vector = embedder.embed_query("!!! ??? ...")
    assert all(v == 0.0 for v in vector)


def test_embed_query_returns_unit_vector():
    embedder = HashEmbeddings(dimensions=128)
    vector = embedder.embed_query("hello world travel")
    norm = math.sqrt(sum(v * v for v in vector))
    assert abs(norm - 1.0) < 1e-9


def test_embed_documents_returns_one_vector_per_document():
    embedder = HashEmbeddings(dimensions=32)
    vectors = embedder.embed_documents(["paris", "tokyo", "nyc"])
    assert len(vectors) == 3
    assert all(len(v) == 32 for v in vectors)


def test_same_text_produces_identical_vectors():
    embedder = HashEmbeddings(dimensions=64)
    a = embedder.embed_query("travel paris food")
    b = embedder.embed_query("travel paris food")
    assert a == b


def test_different_text_produces_different_vectors():
    embedder = HashEmbeddings(dimensions=256)
    a = embedder.embed_query("paris museums art galleries")
    b = embedder.embed_query("tokyo ramen street food")
    assert a != b
