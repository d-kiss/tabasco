#!/usr/bin/env python3
"""tabasco - Time Based Source Control.

Usage:
    tabasco start [--frequency=<seconds>]
    tabasco stop
    tabasco monitor <directory>
    tabasco unmonitor <directory>
    tabasco log
    tabasco apply <commit>
    tabasco rm <commit>
    tabasco -h | --help
    tabasco --version

Options:
    -h, --help                  Show this help message.
    --version                   Show version.
    --frequency=<seconds>       how frequently to monitored
                                directories. [default: 5]

"""
import glob
from collections import namedtuple
from io import StringIO
from checksumdir import dirhash
import datetime
import time
from docopt import docopt
import shutil
from filecmp import dircmp
import os
from pathlib import Path
import shelve
from email.utils import formatdate

from termcolor import colored
from contextlib import redirect_stdout

__version__ = "1.0.0"

Version = namedtuple('Version', ['checksum', 'time', 'name'])


class Daemon(object):
    """I am a daemon that calls all of the monitors and try to load new ones
    from the configuration set in the database.

    Note:
        the debug attribute will make the daemon loop run only once.
        this is for easier unit-testing (go test a daemon, huh? :P),
        don't set this flag
    """

    def __init__(self, tabasco_folder: Path, polling_frequency: int=10,
                 debug: bool=False):
        if type(tabasco_folder) is str:
            tabasco_folder = Path(tabasco_folder)

        if not tabasco_folder.exists():
            tabasco_folder.mkdir()

        self.manager = Manager(tabasco_folder)
        self.polling_frequency = polling_frequency
        self.stop_file = tabasco_folder.joinpath("stop")
        self.is_debug = debug

    def start(self, remove_stopfile_first=True):
        """Start the tabasco daemon.

        This deletes the stop-file if one exists. (but not in debug mode) """
        if remove_stopfile_first and self.stop_file.exists():
            os.remove(str(self.stop_file))

        while not self._should_stop():
            for folder, _ in self.manager:
                Monitor(directory=Path(folder),
                        frequency=self.polling_frequency).run()

            if self.is_debug:
                break

            time.sleep(self.polling_frequency)

    def stop(self):
        """Stop the tabasco daemon.

        This writes a stop-file with the current date."""
        self.stop_file.touch()

    def _should_stop(self):
        """Determine whether or not we should stop."""
        return self.stop_file.exists()


class Manager(object):
    """I know how to add new directories to being monitored and remove them
    afterwards as well."""
    DB_PATH = "monitored_folders.pickle.rick"

    def __init__(self, tabasco_folder: Path):
        if type(tabasco_folder) is str:
            tabasco_folder = Path(tabasco_folder)

        if not tabasco_folder.exists():
            tabasco_folder.mkdir()

        self.db_path = tabasco_folder.joinpath(self.DB_PATH)

    def monitor(self, directory: Path, date: datetime.datetime=None):
        """Add a directory to the monitored directories."""
        if type(directory) is str:
            directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError("Can't monitor an unexisting directory.")

        if not directory.is_dir():
            raise NotADirectoryError("Can't monitor a file.")

        with shelve.open(str(self.db_path)) as db:
            if str(directory) in db:
                raise FileExistsError("Directory already monitored.")

            db[str(directory)] = {'time': date or datetime.datetime.now()}

    def unmonitor(self, directory: Path):
        """Remove a directory from the monitored directories."""
        if type(directory) is str:
            directory = Path(directory)

        with shelve.open(str(self.db_path)) as db:
            del db[str(directory)]

    def __iter__(self):
        with shelve.open(str(self.db_path)) as db:
            for key, value in db.items():
                yield key, value


class Monitor(object):
    """I know how to monitor a single directory and save copies of its
    contents according to a checksum.

    Monitor class saves the information in the following way:
    1. first it manages a LASTFILE, this file manages the information of the
        last backup, so we don't backup every second and without a change.
    2. it manages a versions file, containing information about all versions
    saved.
    """

    def __init__(self, directory: Path, frequency: int = 300):
        self.frequency = frequency

        if type(directory) is str:
            directory = Path(directory)

        self.directory = directory
        self.tabasco_directory = directory.joinpath(".tbsc")
        self.versions_file = self.tabasco_directory.joinpath("versions")
        self.last_file = self.tabasco_directory.joinpath("last")

    def run(self, date: datetime.datetime=None, _checksum: str=None):
        """Back up the directory if found necessary"""
        if not self.tabasco_directory.exists():
            self.tabasco_directory.mkdir()

        now = date or datetime.datetime.now()
        checksum = _checksum or self._checksum()

        if self._should_backup(now, checksum):
            self._update_time_and_hash(now, checksum)
            try:
                self._backup(now, checksum)

            except FileExistsError:
                raise RuntimeError("Commit failed - a commit with the same "
                                   "name already exists.")

    def _checksum(self):
        return dirhash(str(self.directory), ignore_hidden=True)

    def _backup(self, now, checksum):
        """Back up the directory. and save the version in versions file."""
        with shelve.open(str(self.versions_file)) as versions:
            version_name = now.strftime("%Y.%m.%d - %H.%M.%S")
            versions[version_name] = {'time': now,
                                      'checksum': checksum,
                                      'name': version_name}

        version_directory = self.tabasco_directory.joinpath(version_name)
        self._commit(version_directory)

    def _commit(self, version_directory: Path):
        """Copy everything to a destination path except for tabasco files"""
        if not version_directory.exists():
            version_directory.mkdir(parents=True)

        for filename in os.listdir(str(self.directory)):
            if ".tbsc" in filename:
                continue

            path = self.directory.joinpath(filename)

            if path.is_file():
                shutil.copy2(str(path),
                             str(version_directory))

            elif path.is_dir():
                shutil.copytree(str(path),
                                str(version_directory.joinpath(filename)))

    def _should_backup(self, now, checksum):
        """Determine whether or not we should run a backup by reading the
        last-file."""
        with shelve.open(str(self.last_file)) as last:
            last_checksum = last["checksum"] if "checksum" in last else None
            last_access_time = last["time"] if "time" in last else None
            if last_checksum is None and last_access_time is None:
                return True

            is_old = (now - last_access_time).total_seconds() >= self.frequency
            is_outdated = checksum != last_checksum
            return is_old and is_outdated

    def _update_time_and_hash(self, now, checksum):
        """Update the last-file with given time and hash."""
        version_name = now.strftime("%Y.%m.%d - %H.%M.%S")

        with shelve.open(str(self.last_file)) as last:
            last["checksum"] = checksum
            last["time"] = now
            last["name"] = version_name


class SC(object):
    """Source Control

    I expect a tabasco_folder to be a folder with a .tbsc folder where a
    monitor logs action. I can display the actions over time, I can remove a
    snapshot and i can apply a snapshot and revert back to the state of the
    snapshot."""

    def __init__(self, folder: Path):
        if type(folder) is str:
            folder = Path(folder)

        self.directory = folder
        self.tabasco_directory = self.directory.joinpath(".tbsc")
        self.versions_file = self.tabasco_directory.joinpath("versions")
        self.last_file = self.tabasco_directory.joinpath("last")

        if not self.tabasco_directory.exists():
            self.tabasco_directory.mkdir()

    @property
    def versions(self) -> list:
        """list all versions from db."""
        with shelve.open(str(self.versions_file)) as db:
            for key in db:
                yield Version(checksum=db[key]["checksum"],
                              time=db[key]["time"],
                              name=db[key]["name"])

    def print_log(self):
        for version in sorted(self.versions,
                              key=lambda version: version.time):
            print(colored("commit {checksum}"
                            .format(checksum=version.checksum),
                          "yellow"))

            print("Date: {date}".format(date=self._date(version)))
            print(self._diff(version))
            print()

    def apply(self, commit: str):
        version = self._version_by_commit_checksum(commit)
        version_path = self.tabasco_directory.joinpath(version.name)
        self._clear_working_directory()
        self._copy_to_working_directory(version_path)

    def remove(self, commit: str):
        """Delete a version."""
        version = self._version_by_commit_checksum(commit)
        with shelve.open(str(self.versions_file)) as db:
            for key in db:
                if db[key]["checksum"] == version.checksum:
                    del db[key]

    def _clear_working_directory(self):
        for path in glob.glob(os.path.join(str(self.directory), '*')):
            if os.path.isdir(path):
                shutil.rmtree(path)

            if os.path.isfile(path):
                os.remove(path)

    def _copy_to_working_directory(self, version_path: Path):
        for name in os.listdir(str(version_path)):
            path = version_path.joinpath(name)

            if path.is_file():
                shutil.copy2(str(path),
                             str(self.directory))

            elif path.is_dir():
                shutil.copytree(str(path),
                                str(self.directory.joinpath(name)))

    @staticmethod
    def _date(version, localtime=True) -> str:
        """Prettify a version's date."""
        return formatdate(time.mktime(version.time.timetuple()),
                          localtime=localtime)

    def _diff(self, version: Version) -> str:
        """display the difference between a version and working directory."""
        temp_stdout = StringIO()

        with redirect_stdout(temp_stdout):
            dircmp(str(self.directory),
                   str(self.tabasco_directory.joinpath(version.name)),
                   ignore=[".", "..", ".tbsc"]).report()

        # Tab the results and ignore the first line (header)
        diff = temp_stdout.getvalue()
        return "\n".join(["\t" + line for line in diff.splitlines()][1:])

    def _version_by_commit_checksum(self, commit: str) -> Version:
        """Find the closest version by a given checksum.

        Basically sorts the checksums with the requested one and returns the
        next match.
        """
        checksums = [version.checksum for version in self.versions]
        checksums.append(commit)
        checksums = sorted(checksums)
        candidate_checksum = checksums[checksums.index(commit) + 1]

        if not candidate_checksum.startswith(commit):
            raise IndexError("No such commit.")

        for version in self.versions:
            if version.checksum == candidate_checksum:
                return version


def main():
    args = docopt(__doc__)
    tabasco_path = Path.home().joinpath(".tabasco")

    if args["start"]:
        Daemon(tabasco_path,
               polling_frequency=int(args["--frequency"])).start()

    elif args["stop"]:
        Daemon(tabasco_path).stop()

    elif args["monitor"]:
        Manager(tabasco_path).monitor(Path(args["<directory>"]).absolute())

    elif args["unmonitor"]:
        Manager(tabasco_path).unmonitor(Path(args["<directory>"]).absolute())

    elif args["log"]:
        SC(Path.cwd()).print_log()

    elif args["apply"]:
        SC(Path.cwd()).apply(args["<commit>"])

    elif args["rm"]:
        SC(Path.cwd()).remove(args["<commit>"])

    elif args["--version"]:
        print(__version__)


if __name__ == '__main__':
    try:
        main()

    except Exception as error:
        print ("%s" % error)
