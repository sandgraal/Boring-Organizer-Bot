"""Tests for hybrid scoring module."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from bob.retrieval.scoring import (
    HybridScorer,
    ScoredResult,
    ScoringConfig,
    compute_bm25_score,
    compute_idf,
    compute_recency_score,
    normalize_scores,
    tokenize,
)


class TestTokenize:
    """Tests for tokenization."""

    def test_basic_tokenization(self):
        """Simple text is tokenized correctly."""
        tokens = tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_removes_short_tokens(self):
        """Single-character tokens are removed."""
        tokens = tokenize("I am a test")
        assert "i" not in tokens
        assert "a" not in tokens
        assert "am" in tokens
        assert "test" in tokens

    def test_handles_punctuation(self):
        """Punctuation is handled correctly."""
        tokens = tokenize("Hello, world! How's it going?")
        assert "hello" in tokens
        assert "world" in tokens
        assert "how" in tokens

    def test_handles_numbers(self):
        """Numbers are included as tokens."""
        tokens = tokenize("version 3.14 release 42")
        assert "version" in tokens
        assert "14" in tokens
        assert "release" in tokens
        assert "42" in tokens

    def test_empty_string(self):
        """Empty string returns empty list."""
        tokens = tokenize("")
        assert tokens == []


class TestComputeIDF:
    """Tests for IDF computation."""

    def test_single_document(self):
        """IDF with single document."""
        idf = compute_idf(["hello world"])
        assert "hello" in idf
        assert "world" in idf
        # With one doc containing the term, IDF is low
        assert idf["hello"] > 0

    def test_rare_term_higher_idf(self):
        """Rare terms have higher IDF than common terms."""
        documents = [
            "the cat sat on the mat",
            "the dog ran in the park",
            "the bird flew over the tree",
            "python programming language",
        ]
        idf = compute_idf(documents)

        # "the" appears in all docs, "python" in only one
        assert idf["python"] > idf["the"]

    def test_empty_documents(self):
        """Empty document list returns empty IDF."""
        idf = compute_idf([])
        assert idf == {}


class TestComputeBM25Score:
    """Tests for BM25 scoring."""

    def test_matching_query_scores_positive(self):
        """Query with matching terms scores positive."""
        query_tokens = ["hello", "world"]
        doc_tokens = ["hello", "world", "test"]
        idf = {"hello": 1.0, "world": 1.0, "test": 0.5}

        score = compute_bm25_score(query_tokens, doc_tokens, idf, avg_doc_len=3)
        assert score > 0

    def test_no_matching_terms_scores_zero(self):
        """Query with no matching terms scores zero."""
        query_tokens = ["foo", "bar"]
        doc_tokens = ["hello", "world"]
        idf = {"foo": 1.0, "bar": 1.0}

        score = compute_bm25_score(query_tokens, doc_tokens, idf, avg_doc_len=2)
        assert score == 0

    def test_more_matches_higher_score(self):
        """Document with more query matches scores higher."""
        query_tokens = ["python", "programming"]
        idf = {"python": 1.0, "programming": 1.0}

        doc1_tokens = ["python"]  # One match
        doc2_tokens = ["python", "programming"]  # Two matches

        score1 = compute_bm25_score(query_tokens, doc1_tokens, idf, avg_doc_len=2)
        score2 = compute_bm25_score(query_tokens, doc2_tokens, idf, avg_doc_len=2)

        assert score2 > score1

    def test_empty_query_scores_zero(self):
        """Empty query returns zero score."""
        score = compute_bm25_score([], ["hello", "world"], {"hello": 1.0}, avg_doc_len=2)
        assert score == 0

    def test_empty_document_scores_zero(self):
        """Empty document returns zero score."""
        score = compute_bm25_score(["hello"], [], {"hello": 1.0}, avg_doc_len=2)
        assert score == 0


class TestNormalizeScores:
    """Tests for score normalization."""

    def test_normalizes_to_zero_one(self):
        """Scores are normalized to [0, 1] range."""
        scores = [10, 20, 30, 40, 50]
        normalized = normalize_scores(scores)

        assert normalized[0] == 0.0  # Min
        assert normalized[-1] == 1.0  # Max
        for n in normalized:
            assert 0.0 <= n <= 1.0

    def test_empty_list(self):
        """Empty list returns empty list."""
        assert normalize_scores([]) == []

    def test_all_equal_scores(self):
        """All equal scores return all 1.0."""
        scores = [5, 5, 5, 5]
        normalized = normalize_scores(scores)
        assert all(n == 1.0 for n in normalized)

    def test_preserves_order(self):
        """Normalization preserves relative order."""
        scores = [10, 50, 30, 20]
        normalized = normalize_scores(scores)

        # Original order: 10 < 20 < 30 < 50
        assert normalized[0] < normalized[3]  # 10 < 20
        assert normalized[3] < normalized[2]  # 20 < 30
        assert normalized[2] < normalized[1]  # 30 < 50


class TestHybridScorer:
    """Tests for HybridScorer."""

    @pytest.fixture
    def default_scorer(self):
        """Create scorer with default config."""
        return HybridScorer()

    @pytest.fixture
    def sample_results(self):
        """Sample results for testing."""
        return [
            {"id": 1, "content": "Python is a programming language"},
            {"id": 2, "content": "Java is also a programming language"},
            {"id": 3, "content": "The cat sat on the mat"},
        ]

    @pytest.fixture
    def sample_vector_scores(self):
        """Sample vector scores (0-1)."""
        return [0.8, 0.6, 0.3]

    def test_returns_scored_results(self, default_scorer, sample_results, sample_vector_scores):
        """Scorer returns ScoredResult objects."""
        query = "python programming"
        results = default_scorer.score_results(query, sample_results, sample_vector_scores)

        assert len(results) == 3
        assert all(isinstance(r, ScoredResult) for r in results)

    def test_results_have_scores(self, default_scorer, sample_results, sample_vector_scores):
        """Results have all score components."""
        query = "python programming"
        results = default_scorer.score_results(query, sample_results, sample_vector_scores)

        for r in results:
            assert 0.0 <= r.vector_score <= 1.0
            assert 0.0 <= r.keyword_score <= 1.0
            assert 0.0 <= r.final_score <= 1.0

    def test_results_sorted_by_final_score(
        self, default_scorer, sample_results, sample_vector_scores
    ):
        """Results are sorted by final_score descending."""
        query = "python programming"
        results = default_scorer.score_results(query, sample_results, sample_vector_scores)

        scores = [r.final_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_keyword_match_affects_ranking(self):
        """Keyword matches can re-rank results."""
        # Config with strong keyword weight
        config = ScoringConfig(vector_weight=0.3, keyword_weight=0.7)
        scorer = HybridScorer(config)

        results = [
            {"id": 1, "content": "The cat sat on the mat"},  # No match
            {"id": 2, "content": "Python programming guide"},  # Exact match
        ]
        # Vector scores favor first result
        vector_scores = [0.9, 0.5]

        query = "python programming"
        scored = scorer.score_results(query, results, vector_scores)

        # Despite lower vector score, keyword match should push it up
        assert scored[0].chunk_id == 2

    def test_empty_results(self, default_scorer):
        """Empty results returns empty list."""
        results = default_scorer.score_results("test", [], [])
        assert results == []

    def test_preserves_metadata(self, default_scorer, sample_results, sample_vector_scores):
        """Original metadata is preserved in results."""
        query = "python"
        results = default_scorer.score_results(query, sample_results, sample_vector_scores)

        for r in results:
            assert "content" in r.metadata
            assert r.metadata["id"] == r.chunk_id

    def test_custom_bm25_parameters(self):
        """Custom BM25 parameters are used."""
        config = ScoringConfig(bm25_k1=2.0, bm25_b=0.5)
        scorer = HybridScorer(config)

        results = [{"id": 1, "content": "test content here"}]
        vector_scores = [0.5]

        # Should not error with custom params
        scored = scorer.score_results("test", results, vector_scores)
        assert len(scored) == 1


class TestScoringConfig:
    """Tests for ScoringConfig."""

    def test_default_weights_sum_to_one(self):
        """Default vector + keyword weights sum to 1.0."""
        config = ScoringConfig()
        assert config.vector_weight + config.keyword_weight == pytest.approx(1.0)

    def test_custom_weights(self):
        """Custom weights can be specified."""
        config = ScoringConfig(vector_weight=0.5, keyword_weight=0.5)
        assert config.vector_weight == 0.5
        assert config.keyword_weight == 0.5

    def test_recency_boost_default_disabled(self):
        """Recency boost is disabled by default."""
        config = ScoringConfig()
        assert config.recency_boost_enabled is False


class TestComputeRecencyScore:
    """Tests for recency score computation."""

    def test_current_date_full_score(self):
        """Document dated today gets full score."""
        now = datetime.now()
        score = compute_recency_score(now, half_life_days=180, reference_date=now)
        assert score == 1.0

    def test_half_life_gives_half_score(self):
        """Document at half_life age gets 0.5 score."""
        now = datetime.now()
        old_date = now - timedelta(days=180)
        score = compute_recency_score(old_date, half_life_days=180, reference_date=now)
        assert score == pytest.approx(0.5, rel=0.01)

    def test_double_half_life_gives_quarter_score(self):
        """Document at 2x half_life gets 0.25 score."""
        now = datetime.now()
        old_date = now - timedelta(days=360)
        score = compute_recency_score(old_date, half_life_days=180, reference_date=now)
        assert score == pytest.approx(0.25, rel=0.01)

    def test_minimum_score_floor(self):
        """Very old documents still get minimum score."""
        now = datetime.now()
        very_old = now - timedelta(days=3650)  # 10 years
        score = compute_recency_score(very_old, half_life_days=180, reference_date=now)
        assert score >= 0.1  # Minimum floor

    def test_none_date_full_score(self):
        """None date returns full score."""
        score = compute_recency_score(None)
        assert score == 1.0

    def test_string_date_parsed(self):
        """ISO string dates are parsed correctly."""
        now = datetime.now()
        date_str = (now - timedelta(days=90)).isoformat()
        score = compute_recency_score(date_str, half_life_days=180, reference_date=now)
        # At 90 days (half of half_life), should be ~0.707
        assert 0.6 < score < 0.8

    def test_invalid_string_full_score(self):
        """Invalid date strings return full score."""
        score = compute_recency_score("not-a-date")
        assert score == 1.0

    def test_future_date_full_score(self):
        """Future dates get full score."""
        now = datetime.now()
        future = now + timedelta(days=30)
        score = compute_recency_score(future, reference_date=now)
        assert score == 1.0


class TestRecencyBoostIntegration:
    """Tests for recency boost in HybridScorer."""

    def test_recency_boost_disabled_no_effect(self):
        """With recency disabled, all recency scores are 1.0."""
        config = ScoringConfig(recency_boost_enabled=False)
        scorer = HybridScorer(config)

        now = datetime.now()
        results = [
            {"id": 1, "content": "test content", "source_date": now.isoformat()},
            {
                "id": 2,
                "content": "test content",
                "source_date": (now - timedelta(days=365)).isoformat(),
            },
        ]
        vector_scores = [0.8, 0.8]

        scored = scorer.score_results("test", results, vector_scores)
        assert all(r.recency_score == 1.0 for r in scored)

    def test_recency_boost_enabled_affects_ranking(self):
        """With recency enabled, newer docs rank higher with equal relevance."""
        config = ScoringConfig(
            recency_boost_enabled=True,
            recency_half_life_days=180,
            vector_weight=1.0,
            keyword_weight=0.0,
        )
        scorer = HybridScorer(config)

        now = datetime.now()
        results = [
            {
                "id": 1,
                "content": "test content",
                "source_date": (now - timedelta(days=365)).isoformat(),
            },
            {"id": 2, "content": "test content", "source_date": now.isoformat()},
        ]
        # Equal vector scores
        vector_scores = [0.8, 0.8]

        scored = scorer.score_results("test", results, vector_scores)

        # Newer doc (id=2) should rank first
        assert scored[0].chunk_id == 2
        assert scored[0].recency_score > scored[1].recency_score

    def test_relevance_can_overcome_recency(self):
        """A more relevant old doc can still rank above less relevant new doc."""
        config = ScoringConfig(
            recency_boost_enabled=True,
            recency_half_life_days=180,
            vector_weight=1.0,
            keyword_weight=0.0,
        )
        scorer = HybridScorer(config)

        now = datetime.now()
        results = [
            {
                "id": 1,
                "content": "very relevant test content",
                "source_date": (now - timedelta(days=90)).isoformat(),
            },
            {"id": 2, "content": "barely relevant", "source_date": now.isoformat()},
        ]
        # Old doc has much higher vector score
        vector_scores = [0.95, 0.3]

        scored = scorer.score_results("test", results, vector_scores)

        # More relevant old doc should still win
        assert scored[0].chunk_id == 1
