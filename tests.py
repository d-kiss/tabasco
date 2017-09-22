import os
from pathlib import Path
import datetime
from unittest import TestCase
import shutil

from tabasco import Monitor, Manager, SC, Daemon


class MonitorCase(TestCase):
    def setUp(self):
        os.makedirs("temp")

    def test_that_checksum_stays_the_same(self):
        monitor = Monitor("temp")
        self.assertEqual(monitor._checksum(), monitor._checksum())

    def test_that_checksum_is_different(self):
        monitor = Monitor("temp")
        checksum = monitor._checksum()
        with open("temp/file", "w"):
            self.assertNotEqual(monitor._checksum(), checksum)

    def test_commit_when_source_controlled_directory_is_empty(self):
        monitor = Monitor("temp")
        monitor._commit(Path("temp/.tbsc/commit"))

        self.assertEqual(os.listdir("temp/.tbsc/commit"), [])

    def test_commit_when_source_controlled_directory_has_a_file_inside(self):
        monitor = Monitor("temp")
        with open("temp/file", "w"):
            monitor._commit(Path("temp/.tbsc/commit"))
            self.assertEqual(os.listdir("temp/.tbsc/commit"), ["file"])


    def test_commit_when_source_controlled_directory_has_a_folder_inside(self):
        monitor = Monitor("temp")
        os.mkdir("temp/folder")
        monitor._commit(Path("temp/.tbsc/commit"))
        self.assertEqual(os.listdir("temp/.tbsc/commit"),
                         ["folder"])

    def test_should_backup_in_the_first_run(self):
        monitor = Monitor("temp")
        monitor.run()

        versions = [f for f in os.listdir("temp/.tbsc")
                    if os.path.isdir(os.path.join("temp/.tbsc", f))]

        self.assertEqual(len(versions), 1)


    def test_shouldnt_backup_immidiately_without_change(self):
        monitor = Monitor("temp", frequency=1)
        monitor.run()
        monitor.run(date=datetime.datetime.now() +
                         datetime.timedelta(seconds=300))

        versions = [f for f in os.listdir("temp/.tbsc")
                    if os.path.isdir(os.path.join("temp/.tbsc", f))]

        self.assertEqual(len(versions), 1)

    def test_shouldnt_backup_immidiately_after_change(self):
        monitor = Monitor("temp")
        monitor.run()
        monitor.run(date=datetime.datetime.now() +
                         datetime.timedelta(seconds=2),
                    _checksum="what")
        versions = [f for f in os.listdir("temp/.tbsc")
                    if os.path.isdir(os.path.join("temp/.tbsc", f))]

        self.assertEqual(len(versions), 1)

    def test_shouldnt_backup_after_time_without_change(self):
        monitor = Monitor("temp", frequency=300)
        monitor.run()
        monitor.run(date=datetime.datetime.now() +
                         datetime.timedelta(seconds=301))
        versions = [f for f in os.listdir("temp/.tbsc")
                    if os.path.isdir(os.path.join("temp/.tbsc", f))]

        self.assertEqual(len(versions), 1)

    def test_should_backup_after_some_time_and_change(self):
        monitor = Monitor("temp", frequency=300)
        monitor.run()
        monitor.run(date=datetime.datetime.now() +
                         datetime.timedelta(seconds=301),
                    _checksum="what")
        versions = [f for f in os.listdir("temp/.tbsc")
                    if os.path.isdir(os.path.join("temp/.tbsc", f))]

        self.assertEqual(len(versions), 2)


    def tearDown(self):
        shutil.rmtree("temp")


class ManagerCase(TestCase):
    def setUp(self):
        os.makedirs(".tbsc.temp")
        os.makedirs("temp")

    def test_monitor(self):
        manager = Manager(".tbsc.temp")
        manager.monitor("temp")
        for directory, data in manager:
            self.assertEqual(str(directory), "temp")

    def test_unmonitor(self):
        manager = Manager(".tbsc.temp")
        manager.monitor("temp")
        manager.unmonitor("temp")

        self.assertEqual(len(list(manager)), 0)

    def tearDown(self):
        shutil.rmtree(".tbsc.temp")
        shutil.rmtree("temp")


class SCCase(TestCase):
    def setUp(self):
        os.makedirs("temp/.tbsc")

    def test_versions_empty(self):
        sc = SC("temp")
        self.assertEqual(len(list(sc.versions)), 0)

    def test_sc_can_read_one_version(self):
        monitor = Monitor("temp")
        monitor.run()
        sc = SC("temp")
        self.assertEqual(len(list(sc.versions)), 1)

    def test_sc_can_read_multiple_versions(self):
        monitor = Monitor("temp", frequency=1)
        monitor.run()
        open("temp/hello", "w").close()
        monitor.run(date=datetime.datetime.now() +
                         datetime.timedelta(seconds=4))

        sc = SC("temp")
        self.assertEqual(len(list(sc.versions)), 2)

    def test_sc_remove_version(self):
        monitor = Monitor("temp", frequency=1)
        monitor.run(_checksum="Hello")

        sc = SC("temp")
        self.assertEqual(len(list(sc.versions)), 1)

        sc.remove("H")
        self.assertEqual(len(list(sc.versions)), 0)

    def test_clear_working_directory(self):
        sc = SC("temp")
        os.makedirs("temp/folder")
        open("temp/file", "w").close()

        sc._clear_working_directory()
        self.assertEqual(os.listdir("temp"), [".tbsc"])

    def test_apply(self):
        monitor = Monitor("temp", frequency=1)
        open("temp/FILE", "w").close()
        monitor.run(_checksum="Hello")

        sc = SC("temp")
        self.assertEqual(sorted(os.listdir("temp")),
                         sorted([".tbsc", "FILE"]))

        os.remove("temp/FILE")
        self.assertEqual(os.listdir("temp"), [".tbsc"])

        open("temp/BADFILE", "w").close()
        sc.apply("H")
        self.assertEqual(sorted(os.listdir("temp")),
                         sorted([".tbsc", "FILE"]))

        os.remove("temp/FILE")

        os.mkdir("temp/FOLDER")
        monitor.run(date=datetime.datetime.now() +
                         datetime.timedelta(seconds=2),
                    _checksum="WORLD")
        self.assertEqual(sorted(os.listdir("temp")),
                         sorted([".tbsc", "FOLDER"]))

        os.rmdir("temp/FOLDER")
        os.mkdir("temp/BAD_FOLDER")

        self.assertEqual(sorted(os.listdir("temp")),
                         sorted([".tbsc", "BAD_FOLDER"]))
        sc.apply("W")
        self.assertEqual(sorted(os.listdir("temp")),
                         sorted([".tbsc", "FOLDER"]))





    def test_print_log(self):
        monitor = Monitor("temp", frequency=1)
        open("temp/FILE", "w").close()
        open("temp/FIL"
             "E", "w").close()
        monitor.run(_checksum="Hello")

        sc = SC("temp")
        sc.print_log()


    def test_version_by_commit_checksum(self):
        monitor = Monitor("temp", frequency=1)
        monitor.run(_checksum="Hello")
        monitor.run(_checksum="Hello2", date=datetime.datetime.now() +
                                             datetime.timedelta(seconds=4))

        sc = SC("temp")
        self.assertEqual(sc._version_by_commit_checksum("H").checksum, "Hello")
        self.assertEqual(sc._version_by_commit_checksum("Hello2").checksum,
                         "Hello2")
        self.assertEqual(sc._version_by_commit_checksum("Hello").checksum,
                         "Hello")

        with self.assertRaises(IndexError):
            sc._version_by_commit_checksum("A")

    def test_date(self):
        monitor = Monitor("temp", frequency=1)
        monitor.run(_checksum="Hello2", date=datetime.datetime(1997, 10, 2, 12))
        sc = SC("temp")
        self.assertIn("Thu, 02 Oct 1997", sc._date(list(sc.versions)[0],
                                                  localtime=True))

    def tearDown(self):
        shutil.rmtree("temp")


class DaemonCase(TestCase):
    def setUp(self):
        os.makedirs(".tbsc.temp")
        os.makedirs("temp")

    def test_start_first_time(self):
        # Monitor a directory
        Manager(".tbsc.temp").monitor("temp")
        daemon = Daemon(".tbsc.temp", polling_frequency=1, debug=True)
        daemon.start()

        self.assertEqual(sorted(os.listdir("temp")),
                         sorted([".tbsc"]))

    def test_doesnt_run_if_stopped(self):
        Manager(".tbsc.temp").monitor("temp")
        daemon = Daemon(".tbsc.temp", polling_frequency=1, debug=True)
        daemon.stop()
        daemon.start(remove_stopfile_first=False)
        self.assertEqual(sorted(os.listdir("temp")),
                         sorted([]))

    def test_runs_if_started_again_after_being_stopped(self):
        Manager(".tbsc.temp").monitor("temp")
        daemon = Daemon(".tbsc.temp", polling_frequency=1, debug=True)
        daemon.stop()
        daemon.start()
        self.assertEqual(sorted(os.listdir("temp")),
                         sorted([".tbsc"]))

    def tearDown(self):
        shutil.rmtree(".tbsc.temp")
        shutil.rmtree("temp")
