import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zet.services.process_service import ProcessInfo, ProcessService


class ProcessServiceTests(unittest.TestCase):
    def test_restart_zet_stops_harvester_before_restarting_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ProcessService(Path(temp_dir))
            calls = []

            with (
                patch.object(service, "stop", side_effect=lambda process_id: calls.append(("stop", process_id)) or 1),
                patch.object(service, "restart", side_effect=lambda process_id: calls.append(("restart", process_id)) or 2),
            ):
                result = service.restart_zet()

            self.assertEqual((1, 2), result)
            self.assertEqual([("stop", "auto_harvest"), ("restart", "zet_web")], calls)

    def test_zet_self_restart_uses_detached_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ProcessService(Path(temp_dir))
            process = ProcessInfo(os.getpid(), "python.exe", "python -m zet.web.app")

            with (
                patch.object(service, "list_processes", return_value=[process]),
                patch("zet.services.process_service.subprocess.Popen") as popen,
            ):
                stopped = service.restart("zet_web")

            self.assertEqual(stopped, 1)
            command = popen.call_args_list[0].args[0]
            self.assertIn("zet.scripts.restart_managed_process", command)
            self.assertIn(str(os.getpid()), command)
            self.assertIn("run_auto_harvest.bat", popen.call_args_list[1].args[0])

    def test_starting_dashboard_starts_missing_auto_harvester(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ProcessService(Path(temp_dir))
            with (
                patch.object(service, "list_processes", return_value=[]),
                patch("zet.services.process_service.subprocess.Popen") as popen,
            ):
                service.start("zet_web")

            self.assertEqual(2, popen.call_count)
            self.assertIn("run_zet_web.bat", popen.call_args_list[0].args[0])
            self.assertIn("run_auto_harvest.bat", popen.call_args_list[1].args[0])



if __name__ == "__main__":
    unittest.main()
