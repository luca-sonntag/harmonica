"""
Unit tests for the Pipeline Job Manager and real-time stage tracking.
"""

from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harmonica_pipeline.jobs import JobManager, JobState, STAGE_DEFINITIONS


class TestJobManager(unittest.TestCase):
    def test_job_lifecycle_and_stage_transitions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            jobs_dir = Path(tmp_dir)
            manager = JobManager(jobs_dir)

            job, is_new = manager.get_or_create_job("test_job_123", "polka.wav", "Test Polka")
            self.assertTrue(is_new)
            self.assertEqual(job.status, "queued")
            self.assertEqual(len(job.stages), len(STAGE_DEFINITIONS))

            # Start job
            job.start()
            self.assertEqual(job.status, "running")
            self.assertGreaterEqual(job.progress_percent, 2)

            # Start stage ingest
            job.start_stage("ingest", "FFmpeg extrahiert Audio...")
            self.assertEqual(job.current_stage_id, "ingest")
            stage_01 = next(s for s in job.stages if s["id"] == "ingest")
            self.assertEqual(stage_01["status"], "running")

            time.sleep(0.05)
            job.complete_stage("ingest", "22.05 kHz Audio extrahiert")
            self.assertEqual(stage_01["status"], "completed")
            self.assertGreater(stage_01["duration_s"], 0)

            # Progress update & log
            job.set_progress(45)
            job.log("MuScriptor Noten erkannt: 42", "info")
            self.assertEqual(len(job.logs), 2)  # initial + new
            self.assertEqual(job.progress_percent, 45)

            # Complete job with dummy payload
            dummy_result = {"title": "Test Polka", "measures_count": 32}
            job.complete(dummy_result)
            self.assertEqual(job.status, "completed")
            self.assertEqual(job.progress_percent, 100)
            self.assertEqual(job.result, dummy_result)

            # Check that job_status.json was written to disk
            status_file = jobs_dir / "test_job_123" / "job_status.json"
            self.assertTrue(status_file.exists())

            # Verify reload from disk
            new_manager = JobManager(jobs_dir)
            reloaded = new_manager.get_job("test_job_123")
            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded.status, "completed")
            self.assertEqual(reloaded.result["title"], "Test Polka")

    def test_job_failure_state(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            jobs_dir = Path(tmp_dir)
            manager = JobManager(jobs_dir)

            job, _ = manager.get_or_create_job("failed_job", "bad.wav", "")
            job.start()
            job.start_stage("ingest", "Initialisiere...")
            job.fail("Datei ist beschädigt.")

            self.assertEqual(job.status, "failed")
            self.assertEqual(job.error, "Datei ist beschädigt.")
            stage_ingest = next(s for s in job.stages if s["id"] == "ingest")
            self.assertEqual(stage_ingest["status"], "failed")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestJobManager)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
