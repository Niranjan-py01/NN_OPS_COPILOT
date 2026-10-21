
from backend.main import (
    _answer_database_size,
    _needs_live_metrics,
)


def test_detects_database_size_question():
    assert _needs_live_metrics(
        "What is the current size of the NNOpsTest database?"
    )


def test_returns_live_database_size():
    metrics = {
        "metrics": {
            "database_sizes": {
                "rows": [
                    {
                        "database_name": "NNOpsTest",
                        "size_mb": 16.0,
                    }
                ],
                "count": 1,
            }
        }
    }

    answer = _answer_database_size(
        "What is the current size of the NNOpsTest database?",
        metrics,
    )

    assert answer is not None
    assert "NNOpsTest" in answer
    assert "16.0 MB" in answer or "16.00 MB" in answer


def test_does_not_invent_missing_database_size():
    metrics = {
        "metrics": {
            "database_sizes": {
                "rows": [],
                "count": 0,
            }
        }
    }

    answer = _answer_database_size(
        "What is the size of the MissingDB database?",
        metrics,
    )

    assert answer is not None
    assert "not found" in answer.lower()
    assert "16 MB" not in answer


def test_non_size_question_returns_none():
    metrics = {"metrics": {}}

    answer = _answer_database_size(
        "How do I investigate SQL Server blocking?",
        metrics,
    )

    assert answer is None
