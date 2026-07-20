"""Lazy timestamp transforms for frame iterables."""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import replace

from capkit.model import Frame


def rebase_timestamps(
    frames: Iterable[Frame],
    *,
    origin: float | None = None,
    offset: float = 0.0,
) -> Iterator[Frame]:
    """Yield frames translated onto a new timestamp origin.

    ``origin`` names a timestamp in the input time base and ``offset`` names
    the timestamp it should map to. When ``origin`` is omitted, the first
    frame's timestamp is used, so the default rebases the first frame to zero.

    The input is consumed lazily and each frozen frame is copied with only its
    timestamp changed. Input order, timestamp deltas, and every other field are
    preserved.
    """

    def iter_rebased() -> Iterator[Frame]:
        iterator = iter(frames)
        source_origin = origin

        if source_origin is None:
            try:
                first_frame = next(iterator)
            except StopIteration:
                return

            source_origin = first_frame.timestamp
            rebased_first = replace(
                first_frame,
                timestamp=first_frame.timestamp - source_origin + offset,
            )
            del first_frame
            yield rebased_first
            del rebased_first

        for frame in iterator:
            yield replace(frame, timestamp=frame.timestamp - source_origin + offset)

    return iter_rebased()
