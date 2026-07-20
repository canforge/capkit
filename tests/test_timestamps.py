"""Tests for lazy frame-stream timestamp rebasing."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from capkit import Frame, rebase_timestamps


def make_frame(timestamp: float, arbitration_id: int = 0x100) -> Frame:
    return Frame(timestamp=timestamp, arbitration_id=arbitration_id, data=b"")


def test_empty_input_returns_an_empty_iterator() -> None:
    rebased = rebase_timestamps([])

    assert isinstance(rebased, Iterator)
    assert list(rebased) == []


@pytest.mark.parametrize(
    ("timestamps", "expected"),
    [
        ((10.0, 10.25, 11.0), (0.0, 0.25, 1.0)),
        ((-10.0, -9.75, -9.0), (0.0, 0.25, 1.0)),
        (
            (1_752_624_000.000139, 1_752_624_000.250139, 1_752_624_001.000139),
            (0.0, 0.25, 1.0),
        ),
    ],
)
def test_default_rebases_first_frame_to_zero(
    timestamps: tuple[float, ...],
    expected: tuple[float, ...],
) -> None:
    frames = [make_frame(timestamp) for timestamp in timestamps]

    result = list(rebase_timestamps(frames))

    assert [frame.timestamp for frame in result] == pytest.approx(expected)


def test_offset_maps_inferred_first_timestamp_to_requested_value() -> None:
    frames = [make_frame(10.0), make_frame(12.5)]

    result = list(rebase_timestamps(frames, offset=3.0))

    assert [frame.timestamp for frame in result] == pytest.approx([3.0, 5.5])


def test_explicit_origin_and_offset_define_the_mapping() -> None:
    frames = [make_frame(105.0), make_frame(110.0)]

    origin_only = list(rebase_timestamps(frames, origin=100.0))
    translated = list(rebase_timestamps(frames, origin=100.0, offset=-2.0))

    assert [frame.timestamp for frame in origin_only] == pytest.approx([5.0, 10.0])
    assert [frame.timestamp for frame in translated] == pytest.approx([3.0, 8.0])


def test_preserves_timestamp_deltas_and_source_order() -> None:
    frames = [
        make_frame(10.5, 0x100),
        make_frame(9.0, 0x200),
        make_frame(12.25, 0x300),
    ]

    result = list(rebase_timestamps(frames, origin=8.0, offset=2.0))

    assert [frame.arbitration_id for frame in result] == [0x100, 0x200, 0x300]
    result_deltas = [result[index + 1].timestamp - result[index].timestamp for index in range(2)]
    source_deltas = [frames[index + 1].timestamp - frames[index].timestamp for index in range(2)]
    assert result_deltas == pytest.approx(source_deltas)


def test_copies_only_the_timestamp_and_leaves_frozen_input_unchanged() -> None:
    original = Frame(
        timestamp=1_000.25,
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

    result = next(rebase_timestamps([original]))

    assert result is not original
    assert result.timestamp == 0.0
    assert result.arbitration_id == original.arbitration_id
    assert result.data is original.data
    assert result.channel == original.channel
    assert result.is_extended_frame == original.is_extended_frame
    assert result.is_fd == original.is_fd
    assert result.is_remote_frame == original.is_remote_frame
    assert result.is_error_frame == original.is_error_frame
    assert result.is_rx == original.is_rx
    assert result.dlc == original.dlc
    assert result.bitrate_switch == original.bitrate_switch
    assert result.error_state_indicator == original.error_state_indicator
    assert original.timestamp == 1_000.25


def test_generator_is_untouched_until_iteration_and_never_read_ahead() -> None:
    frames = [make_frame(10.0), make_frame(11.0), make_frame(12.0)]
    consumed: list[Frame] = []

    def source() -> Iterator[Frame]:
        for frame in frames:
            consumed.append(frame)
            yield frame

    rebased = rebase_timestamps(source())

    assert consumed == []
    assert next(rebased).timestamp == 0.0
    assert consumed == frames[:1]
    assert next(rebased).timestamp == 1.0
    assert consumed == frames[:2]
    assert next(rebased).timestamp == 2.0
    assert consumed == frames
    with pytest.raises(StopIteration):
        next(rebased)
