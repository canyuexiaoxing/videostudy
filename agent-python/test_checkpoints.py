import tempfile
import threading
import unittest
from pathlib import Path

from checkpoints import Checkpoints


class CheckpointTest(unittest.TestCase):
    def test_restart_reuses_success_but_invalidated_inputs_recompute(self):
        with tempfile.TemporaryDirectory() as d:
            first = Checkpoints(Path(d), {'model': 'v1'})
            self.assertEqual(first.run('speech', {'size': 4}, lambda: {'text': 'hello'}), {'text': 'hello'})
            second = Checkpoints(Path(d), {'model': 'v1'})
            self.assertEqual(second.run('speech', {'size': 4}, lambda: self.fail('recomputed')), {'text': 'hello'})
            self.assertEqual(second.hits, {'speech': 1})
            third = Checkpoints(Path(d), {'model': 'v2'})
            self.assertEqual(third.run('speech', {'size': 4}, lambda: {'text': 'new'}), {'text': 'new'})

    def test_failed_results_and_exceptions_are_not_reused(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Checkpoints(Path(d), {})
            cache.run('page', {}, lambda: {'status': 'failed'}, accept=lambda v: v['status'] != 'failed')
            self.assertEqual(cache.run('page', {}, lambda: {'status': 'completed'}), {'status': 'completed'})
            with self.assertRaises(RuntimeError):
                cache.run('bad', {}, lambda: (_ for _ in ()).throw(RuntimeError('failure')))
            self.assertEqual(cache.run('bad', {}, lambda: 5), 5)

    def test_parallel_writes_are_independent_and_corruption_recomputes(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Checkpoints(Path(d), {})
            threads = [threading.Thread(target=lambda i=i: cache.run(f'page:{i}', {}, lambda: i)) for i in range(8)]
            for t in threads: t.start()
            for t in threads: t.join()
            self.assertEqual(len(list(Path(d).glob('*.json'))), 8)
            for p in Path(d).glob('*.json'): p.write_text('{broken')
            self.assertEqual(cache.run('page:0', {}, lambda: 99), 99)


if __name__ == '__main__': unittest.main()
