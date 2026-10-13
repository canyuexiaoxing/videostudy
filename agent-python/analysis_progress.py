"""Best-effort atomic task progress, independent of reusable checkpoint identity."""
import json
import logging
from pathlib import Path
import threading
from uuid import uuid4

class AnalysisProgress:
    def __init__(self, root: Path):
        self.root = root
        self.lock = threading.Lock()
        self.units = set()
        self.value = {}

    def enter(self, stage, completed_stages, total_units=0):
        with self.lock:
            self.units.clear()
            self.value = dict(stage=stage, completedStages=completed_stages, totalStages=5,
                              completedUnits=0, totalUnits=total_units)
            self._publish()

    def unit_done(self, key, stage):
        with self.lock:
            if self.value.get('stage') != stage or key in self.units:
                return
            self.units.add(key)
            self.value['completedUnits'] = min(len(self.units), self.value['totalUnits'])
            self._publish()

    def update_groups(self, ready, completed, total, phase):
        """Publish overlapping group work without replacing the active media stage."""
        with self.lock:
            self.value.update(readyGroups=max(0, int(ready)), completedGroups=max(0, int(completed)),
                              totalGroups=max(0, int(total)), groupPhase=str(phase))
            self._publish()

    def _publish(self):
        temporary = self.root / f'progress.{uuid4().hex}.tmp'
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(self.value), encoding='utf-8')
            temporary.replace(self.root / 'progress.json')
        except OSError:
            logging.getLogger(__name__).warning('Unable to publish analysis progress')
        finally:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass
