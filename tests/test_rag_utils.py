from backend.rag import chunk_text

def test_empty_text():
    assert chunk_text("   ") == []

def test_splits_long_text():
    chunks = chunk_text("a" * 2000, size=500, overlap=50)
    assert len(chunks) > 1
    assert all(chunks)
