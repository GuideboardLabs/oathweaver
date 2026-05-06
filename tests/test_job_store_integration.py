from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.common import ensure_runtime
from infra.background.job_store import JobStore


class JobStoreIntegrationTests(unittest.TestCase):
    def test_job_lifecycle_persists_events(self) -> None:
        with tempfile.TemporaryDirectory(prefix='oathweaver_jobs_') as tmpdir:
            repo_root = Path(tmpdir)
            ensure_runtime(repo_root)
            store = JobStore(repo_root)
            start = store.start_job(
                profile_id='p1',
                request_id='r1',
                conversation_id='c1',
                mode='chat',
                user_text_preview='hello world',
            )
            self.assertEqual(start['status'], 'running')
            store.attach_context(profile_id='p1', request_id='r1', project='general', lane='research')
            store.update_job(profile_id='p1', request_id='r1', stage='research_pool_started', detail='workers ready')
            self.assertTrue(store.request_cancel(profile_id='p1', request_id='r1'))
            end = store.finish_job(profile_id='p1', request_id='r1', status='cancelled', detail='user cancelled')
            self.assertEqual(end['status'], 'cancelled')
            events = store.list_events(profile_id='p1', request_id='r1', limit=10)
            stages = [row['stage'] for row in events]
            self.assertIn('research_pool_started', stages)
            self.assertIn('cancel_requested', stages)
            self.assertIn('cancelled', stages)


if __name__ == '__main__':
    unittest.main()
