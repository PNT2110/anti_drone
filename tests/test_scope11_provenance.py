from scripts.scope11_provenance import classify_match, group_aliases, promote_possible


def test_one_to_many_tracking_match_stays_possible():
    status = classify_match(exact_archive_member=True, exact_tracking_members=["video01/00001.jpg", "video02/00001.jpg"])
    assert status == "POSSIBLE_MATCH"


def test_single_exact_tracking_member_is_source_sequence():
    status = classify_match(exact_archive_member=True, exact_tracking_members=["video01/00001.jpg"])
    assert status == "CONFIRMED_SOURCE_SEQUENCE"


def test_missing_metadata_is_unresolved():
    assert classify_match(exact_archive_member=False, exact_tracking_members=[]) == "UNRESOLVED"
    assert classify_match(exact_archive_member=True, exact_tracking_members=[]) == "UNRESOLVED"


def test_group_alias_is_reported_without_merging():
    records = [
        {"source_sequence_key": "DUT:video01", "v2_group": "base:DUT_00001", "provenance_status": "CONFIRMED_SOURCE_SEQUENCE"},
        {"source_sequence_key": "DUT:video01", "v2_group": "base:DUT_00002", "provenance_status": "CONFIRMED_SOURCE_SEQUENCE"},
    ]
    aliases = group_aliases(records)
    assert aliases[0]["collision_type"] == "SOURCE_GROUP_ALIAS"
    assert len(aliases[0]["v2_groups"]) == 2


def test_possible_match_is_not_promoted():
    assert promote_possible("POSSIBLE_MATCH") == "POSSIBLE_MATCH"
