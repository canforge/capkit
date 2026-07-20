"""Tests for lazy merging of timestamp-ordered frame streams."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from capkit import Frame, merge_frames


def make_frame(
    timestamp: float,
    arbitration_id: int,
    *,
    channel: int | None = None,
) -> Frame:
    return Frame(timestamp=timestamp, arbitration_id=arbitration_id, data=b"", channel=channel)


def test_merges_multiple_buses_in_timestamp_order() -> None:
    first_bus = [
        make_frame(1.0, 0x101, channel=1),
        make_frame(4.0, 0x104, channel=1),
    ]
    second_bus = [
        make_frame(2.0, 0x202, channel=2),
        make_frame(5.0, 0x205, channel=2),
    ]
    third_bus = [
        make_frame(3.0, 0x303, channel=3),
        make_frame(6.0, 0x306, channel=3),
    ]

    merged = merge_frames(first_bus, second_bus, third_bus)

    assert isinstance(merged, Iterator)
    assert list(merged) == [
        first_bus[0],
        second_bus[0],
        third_bus[0],
        first_bus[1],
        second_bus[1],
        third_bus[1],
    ]


def test_equal_timestamps_prefer_lower_source_index_and_preserve_source_order() -> None:
    first_source = [make_frame(1.0, 0x101), make_frame(1.0, 0x102)]
    second_source = [make_frame(1.0, 0x201), make_frame(1.0, 0x202)]
    third_source = [make_frame(1.0, 0x301)]

    assert list(merge_frames(first_source, second_source, third_source)) == [
        first_source[0],
        first_source[1],
        second_source[0],
        second_source[1],
        third_source[0],
    ]


def test_handles_no_inputs_empty_streams_and_uneven_exhaustion() -> None:
    frames = [make_frame(1.0, 0x100), make_frame(2.0, 0x200)]

    assert list(merge_frames()) == []
    assert list(merge_frames([], [])) == []
    assert list(merge_frames([], frames, [])) == frames


def test_generator_inputs_are_untouched_until_iteration_starts() -> None:
    consumed: list[tuple[int, float]] = []

    def source(source_index: int, timestamps: tuple[float, ...]) -> Iterator[Frame]:
        for timestamp in timestamps:
            consumed.append((source_index, timestamp))
            yield make_frame(timestamp, source_index)

    merged = merge_frames(source(0, (1.0, 3.0)), source(1, (2.0, 4.0)))

    assert consumed == []
    assert next(merged).timestamp == 1.0
    assert consumed == [(0, 1.0), (1, 2.0)]
    assert next(merged).timestamp == 2.0
    assert consumed == [(0, 1.0), (1, 2.0), (0, 3.0)]
    assert next(merged).timestamp == 3.0
    assert consumed == [(0, 1.0), (1, 2.0), (0, 3.0), (1, 4.0)]
    assert next(merged).timestamp == 4.0
    assert consumed == [(0, 1.0), (1, 2.0), (0, 3.0), (1, 4.0)]
    with pytest.raises(StopIteration):
        next(merged)


def test_preserves_frame_identity_and_every_field() -> None:
    frame = Frame(
        timestamp=1.25,
        arbitration_id=0x1ABCDE,
        data=b"\x01\x02",
        channel=4,
        is_extended_frame=True,
        is_fd=True,
        is_remote_frame=False,
        is_error_frame=True,
        is_rx=False,
        dlc=8,
        bitrate_switch=True,
        error_state_indicator=True,
    )

    result = next(merge_frames([frame]))

    assert result is frame


def test_out_of_order_source_raises_when_violation_is_reached() -> None:
    first = make_frame(1.0, 0x100)
    second = make_frame(3.0, 0x300)
    backwards = make_frame(2.0, 0x200)
    merged = merge_frames([first, second, backwards], [make_frame(10.0, 0xA00)])

    assert next(merged) is first
    assert next(merged) is second
    with pytest.raises(
        ValueError,
        match=r"input stream 0 is not time-ordered: timestamp 2\.0 follows 3\.0",
    ):
        next(merged)


def test_out_of_order_error_identifies_the_source_index() -> None:
    valid = [make_frame(0.0, 0x100)]
    invalid = [make_frame(1.0, 0x200), make_frame(0.5, 0x201)]
    merged = merge_frames(valid, invalid)

    assert next(merged) is valid[0]
    assert next(merged) is invalid[0]
    with pytest.raises(ValueError, match=r"input stream 1 is not time-ordered"):
        next(merged)
