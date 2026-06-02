"""Shared helpers for NDJSON streaming responses (agent /stream endpoints).

The agent emits frame dicts ({"type": "session"|"sources"|"token"|"metadata"|"done"|"error"}).
We serialize each as one JSON object per line (NDJSON), which the frontend reads via a
chunked fetch + ReadableStream. See docs for the full contract.
"""

import json
import logging
from typing import AsyncIterator, Dict, Any

logger = logging.getLogger(__name__)

# Headers that keep streaming working through proxies/load balancers (nginx, Cloud Run).
STREAM_HEADERS = {
    "X-Accel-Buffering": "no",   # disable nginx response buffering
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}


async def ndjson_stream(frame_gen: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[bytes]:
    """Turn an async generator of frame dicts into NDJSON bytes (one JSON per line).

    Errors that escape the generator are converted to a final in-band error frame so the
    client always gets a clean terminal message instead of a broken connection.
    """
    try:
        async for frame in frame_gen:
            yield (json.dumps(frame, default=str) + "\n").encode("utf-8")
    except Exception as e:
        logger.error(f"Streaming generator failed: {e}", exc_info=True)
        err = {"type": "error", "message": "I apologize, but I encountered an error. Please try again."}
        yield (json.dumps(err) + "\n").encode("utf-8")
