"""Tests for lazy frame-stream filtering."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from capkit import Frame, filter_frames


def make_frame(
    timestamp: float,
    arbitration_id: int,
    *,
    channel: int | None = None,
) -> Frame:
    return Frame(timestamp=timestamp, arbitration_id=arbitration_id, data=b"", channel=channel)


def test_empty_input_and_omitted_criteria() -> None:
    assert list(filter_frames([])) == []

    frames = [make_frame(1.0, 0x100, channel=1), make_frame(2.0, 0x200, channel=2)]
    filtered = filter_frames(frames)

    assert isinstance(filtered, Iterator)
    assert list(filtered) == frames


def test_filters_by_multiple_arbitration_ids() -> None:
    frames = [
        make_frame(1.0, 0x100),
        make_frame(2.0, 0x200),
        make_frame(3.0, 0x300),
        make_frame(4.0, 0x100),
    ]

    assert list(filter_frames(frames, arbitration_ids={0x100, 0x300})) == [frames[0], frames[2], frames[3]]


def test_filters_by_multiple_channels_including_none() -> None:
    frames = [
        make_frame(1.0, 0x100, channel=None),
        make_frame(2.0, 0x100, channel=1),
        make_frame(3.0, 0x100, channel=2),
        make_frame(4.0, 0x100, channel=3),
    ]

    assert list(filter_frames(frames, channels={None, 2})) == [frames[0], frames[2]]


def test_time_bounds_are_inclusive_and_may_be_one_sided() -> None:
    frames = [make_frame(timestamp, 0x100) for timestamp in (1.0, 2.0, 3.0, 4.0)]

    assert list(filter_frames(frames, start_time=2.0, end_time=3.0)) == frames[1:3]
    assert list(filter_frames(frames, start_time=3.0)) == frames[2:]
    assert list(filter_frames(frames, end_time=2.0)) == frames[:2]


def test_combines_all_criteria_with_and_semantics() -> None:
    frames = [
        make_frame(1.0, 0x100, channel=1),
        make_frame(2.0, 0x200, channel=1),
        make_frame(3.0, 0x200, channel=2),
        make_frame(4.0, 0x200, channel=1),
    ]

    assert list(
        filter_frames(
            frames,
            arbitration_ids={0x200, 0x300},
            channels={1, 3},
            start_time=2.0,
            end_time=3.0,
        )
    ) == [frames[1]]


def test_rejects_reversed_window_without_iterating_source() -> None:
    iterated = False

    def frames() -> Iterator[Frame]:
        nonlocal iterated
        iterated = True
        yield make_frame(1.0, 0x100)

    with pytest.raises(ValueError, match="start_time must be less than or equal to end_time"):
        filter_frames(frames(), start_time=2.0, end_time=1.0)

    assert iterated is False


@pytest.mark.parametrize(
    "criteria",
    [
        {"arbitration_ids": []},
        {"channels": []},
    ],
)
def test_empty_criterion_matches_nothing_without_consuming_source(
    criteria: dict[str, list[int]],
) -> None:
    consumed: list[Frame] = []
    frame = make_frame(1.0, 0x100, channel=1)

    def frames() -> Iterator[Frame]:
        consumed.append(frame)
        yield frame

    assert list(filter_frames(frames(), **criteria)) == []  # type: ignore[arg-type]
    assert consumed == []


def test_generator_input_is_lazy_and_does_not_read_ahead() -> None:
    frames = [
        make_frame(1.0, 0x100),
        make_frame(2.0, 0x200),
        make_frame(3.0, 0x200),
    ]
    consumed: list[Frame] = []

    def source() -> Iterator[Frame]:
        for frame in frames:
            consumed.append(frame)
            yield frame

    filtered = filter_frames(source(), arbitration_ids={0x200})

    assert consumed == []
    assert next(filtered) is frames[1]
    assert consumed == frames[:2]
    assert next(filtered) is frames[2]
    assert consumed == frames
    with pytest.raises(StopIteration):
        next(filtered)


def test_preserves_input_order_and_frame_identity() -> None:
    first = make_frame(3.0, 0x100, channel=1)
    second = make_frame(1.0, 0x100, channel=1)

    result = list(filter_frames([first, second], arbitration_ids={0x100}, channels={1}))

    assert result[0] is first
    assert result[1] is second
