"""Lazy filters for frame iterables."""
from __future__ import annotations

from collections.abc import Iterable, Iterator

from capkit.model import Frame


def filter_frames(
    frames: Iterable[Frame],
    *,
    arbitration_ids: Iterable[int] | None = None,
    channels: Iterable[int | None] | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
) -> Iterator[Frame]:
    """Yield frames matching every supplied criterion.

    Time bounds are inclusive. The input frame iterable is not touched until
    the returned iterator is advanced, and matching frames are yielded without
    copying or reordering them.
    """
    if start_time is not None and end_time is not None and start_time > end_time:
        raise ValueError("start_time must be less than or equal to end_time")

    wanted_ids = None if arbitration_ids is None else frozenset(arbitration_ids)
    wanted_channels = None if channels is None else frozenset(channels)

    def iter_matches() -> Iterator[Frame]:
        if (wanted_ids is not None and not wanted_ids) or (
            wanted_channels is not None and not wanted_channels
        ):
            return

        for frame in frames:
            if wanted_ids is not None and frame.arbitration_id not in wanted_ids:
                continue
            if wanted_channels is not None and frame.channel not in wanted_channels:
                continue
            if start_time is not None and frame.timestamp < start_time:
                continue
            if end_time is not None and frame.timestamp > end_time:
                continue
            yield frame

    return iter_matches()
