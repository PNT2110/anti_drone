from scripts.scope13_provenance import (
    classify_prefix,
    confirmed_cross_split_collisions,
    parse_rgbt_basename,
)


def test_one_frame_maps_to_two_modalities_same_archive_sequence():
    visible = parse_rgbt_basename("RGBT_test_20200101_120000_1_1_visible_10.jpg")
    infrared = parse_rgbt_basename("RGBT_test_20200101_120000_1_1_infrared_10.jpg")
    assert visible["archive_sequence_id"] == infrared["archive_sequence_id"]
    assert visible["modality"] != infrared["modality"]
    assert visible["source_frame_index"] == infrared["source_frame_index"] == 10


def test_same_timestamp_different_sequence_is_not_shared_session():
    a = parse_rgbt_basename("RGBT_test_20200101_120000_1_1_visible_10.jpg")
    b = parse_rgbt_basename("RGBT_test_20200101_120000_1_2_visible_10.jpg")
    assert a["session_prefix"] == b["session_prefix"]
    assert a["archive_sequence_id"] != b["archive_sequence_id"]
    assert classify_prefix(archive_sequence_ids={a["archive_sequence_id"], b["archive_sequence_id"]}) == (
        "CONFIRMED_DISTINCT_SOURCES", "UNRESOLVED"
    )


def test_ambiguous_member_is_unresolved():
    assert classify_prefix(archive_sequence_ids=set()) == ("UNRESOLVED", "UNRESOLVED")


def test_explicit_same_session_is_confirmed_shared():
    assert classify_prefix(archive_sequence_ids={"a", "b"}, explicit_session_ids={"session-1"}) == (
        "CONFIRMED_SHARED_SESSION", "CONFIRMED_SHARED_SESSION"
    )


def test_confirmed_sequence_collision_is_detected():
    records = [
        {"mapping_status": "CONFIRMED", "source_key": "seq-a", "split": "train", "group": "g1"},
        {"mapping_status": "CONFIRMED", "source_key": "seq-a", "split": "test", "group": "g1"},
        {"mapping_status": "UNRESOLVED", "source_key": "seq-b", "split": "train", "group": "g2"},
    ]
    assert confirmed_cross_split_collisions(records, "source_key")[0]["source_key"] == "seq-a"


def test_invalid_prefix_does_not_become_confirmed():
    assert parse_rgbt_basename("not-an-rgbt-file.jpg") is None
