from scripts.scope14_policy import (
    deterministic_prefix_target_assignment,
    holdout_conflict,
    overlap_by_key,
    strict_original_split_assignment,
)


def test_two_videos_same_prefix_are_one_candidate_group():
    groups = [{"prefix": "p", "sample_count": 10}]
    assert deterministic_prefix_target_assignment(groups, seed=42) == {"p": "train"}


def test_different_prefixes_are_not_declared_session_independent():
    assert strict_original_split_assignment("train") == "train"
    assert holdout_conflict("train", "test") is True


def test_original_test_holdout_cannot_enter_train():
    assert holdout_conflict("test", "train") is True
    assert holdout_conflict("test", "test") is False


def test_candidate_group_holdout_conflict_is_detected():
    assert holdout_conflict("val", "train") is True


def test_seed_reproducibility():
    groups = [{"prefix": "a", "sample_count": 5}, {"prefix": "b", "sample_count": 4}, {"prefix": "c", "sample_count": 3}]
    assert deterministic_prefix_target_assignment(groups, 42) == deterministic_prefix_target_assignment(groups, 42)


def test_quarantine_is_not_reintroduced_by_overlap_audit():
    rows = [{"prefix": "a", "split": "train"}, {"prefix": "b", "split": "val"}]
    assert overlap_by_key(rows, "prefix") == []


def test_baseline_like_rows_have_no_candidate_overlap():
    rows = [{"prefix": "p", "split": "train"}, {"prefix": "q", "split": "val"}]
    assert overlap_by_key(rows, "prefix") == []
