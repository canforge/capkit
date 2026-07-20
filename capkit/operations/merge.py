"""Lazy merging for timestamp-ordered frame iterables."""
from __future__ import annotations

import heapq
from collections.abc import Iterable, Iterator

from capkit.model import Frame


def merge_frames(*streams: Iterable[Frame]) -> Iterator[Frame]:
    """Merge timestamp-ordered frame streams without copying their frames.

    Inputs must be ordered by nondecreasing timestamp. Equal timestamps are
    yielded from lower-indexed streams first. Sources are validated as they are
    consumed, and a backwards timestamp raises ``ValueError``.
    """

    def iter_merged() -> Iterator[Frame]:
        iterators = [iter(stream) for stream in streams]
        heads: list[tuple[float, int, Frame]] = []
        previous_timestamps: dict[int, float] = {}

        for source_index, frames in enumerate(iterators):
            try:
                frame = next(frames)
            except StopIteration:
                continue
            previous_timestamps[source_index] = frame.timestamp
            heapq.heappush(heads, (frame.timestamp, source_index, frame))

        while heads:
            _, source_index, frame = heapq.heappop(heads)
            yield frame

            try:
                next_frame = next(iterators[source_index])
            except StopIteration:
                continue

            previous_timestamp = previous_timestamps[source_index]
            if next_frame.timestamp < previous_timestamp:
                raise ValueError(
                    f"input stream {source_index} is not time-ordered: "
                    f"timestamp {next_frame.timestamp!r} follows {previous_timestamp!r}"
                )

            previous_timestamps[source_index] = next_frame.timestamp
            heapq.heappush(heads, (next_frame.timestamp, source_index, next_frame))

    return iter_merged()
