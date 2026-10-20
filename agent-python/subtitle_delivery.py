"""Publish grouped text to Java without waiting for the subtitle worker."""

from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID


_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='subtitle-source')
_pending = threading.BoundedSemaphore(8)
_logger = logging.getLogger(__name__)


def _deliver_source(url: str, token: str, encoded: bytes) -> bool:
    for attempt in range(3):
        request = Request(url, data=encoded, method='POST', headers={
            'Content-Type': 'application/json', 'X-Subtitle-Token': token,
        })
        runtime_token=os.environ.get('FRAMEWISE_RUNTIME_TOKEN','')
        if runtime_token:request.add_header('X-Framewise-Runtime',runtime_token)
        try:
            with urlopen(request, timeout=5) as response:
                response.read()
            return True
        except HTTPError as error:
            if 400 <= error.code < 500 and error.code not in (408, 429):
                return False
        except (OSError, TimeoutError):
            pass
        if attempt < 2:
            time.sleep(0.5 * (attempt + 1))
    # Do not log the token, request body, or provider message.
    _logger.warning('Subtitle source delivery failed; completed analysis can supply the fallback')
    return False


def publish_subtitle_source(file_id: str, callback_token: str | None, language: str,
                            segments: list[dict], page_groups: list[dict]):
    file_id = str(UUID(file_id))
    if not callback_token or not _pending.acquire(blocking=False):
        return None
    try:
        # Freeze the source after page understanding has completed.
        # This contains OCR text and timestamps, never image bytes or media paths.
        encoded = json.dumps({'language': language, 'segments': segments,
                              'pageGroups': page_groups}, ensure_ascii=False).encode('utf-8')
        base = os.environ.get('JAVA_INTERNAL_BASE_URL', 'http://java-api:18080').rstrip('/')
        future = _executor.submit(_deliver_source,
            f'{base}/api/internal/transcriptions/{file_id}/subtitle-source', callback_token, encoded)
        future.add_done_callback(lambda _: _pending.release())
        return future
    except Exception:
        _pending.release()
        raise

