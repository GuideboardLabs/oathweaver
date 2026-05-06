from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tests.common import ensure_runtime  # noqa: F401  # ensure SourceCode on sys.path
from shared_tools.premium_model_lock import PremiumModelLock


class _FakeClient:
    def __init__(self) -> None:
        self.released: list[str] = []

    def release_model(self, model: str) -> None:
        self.released.append(str(model))


class PremiumModelLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="oathweaver_premium_lock_")
        self.repo_root = Path(self.tmpdir.name)
        ensure_runtime(self.repo_root)
        self.client = _FakeClient()
        self.models = ["qwen3:14b", "deepseek-r1:14b", "qwen2.5-coder:14b", "qwen2.5:32b"]

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_acquire_release_roundtrip(self) -> None:
        lock = PremiumModelLock(self.repo_root, client=self.client, premium_models=self.models)
        lease = lock.acquire("qwen3:14b", timeout_sec=2.0)
        self.assertEqual(lease.model, "qwen3:14b")
        lock.release(lease, force_unload=True)
        self.assertIn("qwen3:14b", self.client.released)

    def test_concurrent_acquisition_serializes(self) -> None:
        lock1 = PremiumModelLock(self.repo_root, client=self.client, premium_models=self.models)
        lock2 = PremiumModelLock(self.repo_root, client=self.client, premium_models=self.models)
        waits: dict[str, float] = {}

        def t1() -> None:
            lease = lock1.acquire("qwen3:14b", timeout_sec=2.0)
            waits["a"] = lease.wait_ms
            time.sleep(0.35)
            lock1.release(lease, force_unload=True)

        def t2() -> None:
            time.sleep(0.05)
            lease = lock2.acquire("deepseek-r1:14b", timeout_sec=3.0)
            waits["b"] = lease.wait_ms
            lock2.release(lease, force_unload=True)

        th1 = threading.Thread(target=t1)
        th2 = threading.Thread(target=t2)
        th1.start()
        th2.start()
        th1.join()
        th2.join()

        self.assertIn("a", waits)
        self.assertIn("b", waits)
        self.assertGreater(waits["b"], 100.0)

    def test_swap_unloads_previous_model(self) -> None:
        lock = PremiumModelLock(self.repo_root, client=self.client, premium_models=self.models)
        lease_a = lock.acquire("qwen3:14b", timeout_sec=2.0)
        lease_b = lock.acquire("deepseek-r1:14b", timeout_sec=2.0)
        self.assertEqual(lease_b.swapped_from, "qwen3:14b")
        self.assertIn("qwen3:14b", self.client.released)
        lock.release(lease_a, force_unload=True)  # no-op clear (stale lease)
        lock.release(lease_b, force_unload=True)

    def test_timeout_when_lock_held_by_other_owner(self) -> None:
        lock1 = PremiumModelLock(self.repo_root, client=self.client, premium_models=self.models)
        lock2 = PremiumModelLock(self.repo_root, client=self.client, premium_models=self.models)
        lease = lock1.acquire("qwen3:14b", timeout_sec=2.0)
        try:
            with self.assertRaises(TimeoutError):
                lock2.acquire("deepseek-r1:14b", timeout_sec=0.2)
        finally:
            lock1.release(lease, force_unload=True)

    def test_filesystem_sentinel_roundtrip_and_stale_reclaim(self) -> None:
        lock = PremiumModelLock(self.repo_root, client=self.client, premium_models=self.models)
        lease = lock.acquire("qwen3:14b", timeout_sec=2.0)
        state_path = self.repo_root / "var" / "state" / "premium_lock.json"
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("model"), "qwen3:14b")
        lock.release(lease, force_unload=True)

        stale_payload = {
            "model": "qwen3:14b",
            "owner_pid": 999999,
            "owner_token": "stale-owner",
            "updated_ts": time.time() - 9999.0,
            "updated_at": "2000-01-01T00:00:00+00:00",
        }
        state_path.write_text(json.dumps(stale_payload, indent=2), encoding="utf-8")
        lease2 = lock.acquire("deepseek-r1:14b", timeout_sec=2.0)
        payload2 = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload2.get("model"), "deepseek-r1:14b")
        lock.release(lease2, force_unload=True)


if __name__ == "__main__":
    unittest.main()
