"""Task-local, atomic checkpoints; successful work survives a failed later stage."""
import hashlib
import json
import logging
from pathlib import Path
import threading
from uuid import uuid4

log = logging.getLogger(__name__)


class Checkpoints:
    def __init__(self, root: Path, context: dict):
        self.root, self.context = root, context
        self.hits: dict[str, int] = {}
        self._lock = threading.Lock()

    def run(self, stage, inputs, function, accept=lambda value: True):
        identity = {'version': 1, 'context': self.context, 'stage': stage, 'inputs': inputs}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False,
                                          separators=(',', ':')).encode()).hexdigest()
        path = self.root / f'{digest}.json'
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved.get('digest') == digest and accept(saved['value']):
                with self._lock:
                    name = stage.split(':')[0]
                    self.hits[name] = self.hits.get(name, 0) + 1
                log.info('Reused checkpoint %s', stage)
                return saved['value']
        except (OSError, ValueError, KeyError, TypeError):
            pass
        value = function()
        if accept(value):
            self.root.mkdir(parents=True, exist_ok=True)
            temporary = self.root / f'{digest}.{uuid4().hex}.tmp'
            try:
                temporary.write_text(json.dumps({'digest': digest, 'value': value}, ensure_ascii=False),
                                     encoding='utf-8')
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        return value
