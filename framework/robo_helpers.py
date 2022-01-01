from pathlib import Path
import subprocess
import shutil
import tempfile
import os
import base64

def collect_all(root_dir, subdir_name, glob, dest_folder):
    """collects files in all directories by glob pattern being in a directory with subdir name and copies
    the files to dest_folder

    Args:
        root_dir (string): name of the directory, where to start searching
        subdir_name (string): basename of the subdir
        glob (string): glob pattern like *.py, *.robot
        dest_folder (string/path): Destination path
    """

    for dir in root_dir.glob(f"**/{subdir_name}"):
        if not dir.is_dir():
            continue
        files = list(dir.glob(glob))
        for file in files:
            dest_path = dest_folder / subdir_name / file.name
            if dest_path.exists():
                raise Exception(f"Destination path '{dest_path}' already exists.")
            dest_path.parent.mkdir(exist_ok=True)
            shutil.copy(file, dest_path)

def _make_archive(test_files, root_dir):
    """Makes archive of robot test containing all aggregated keywords.

    Args:
        test_files (list of paths): The robot test files to be packed

    Returns:
        bytes: the archive in bytes format
    """
    working_space = Path(tempfile.mkdtemp())
    test_folder = working_space / 'tests'
    test_folder.mkdir()
    test_files = [x.absolute() for x in test_files]
    pwd = os.getcwd()

    try:
        for file in test_files:
            shutil.copy(file, test_folder / file.name)

            # refactor after code review to remove consts
            for subdir in file.parent.glob("*"):
                if subdir.is_dir():
                    if subdir.name in ['data']:
                        (test_folder / subdir.name).mkdir(exist_ok=True)
                        subprocess.call(["rsync", 
                            str(subdir) + "/",
                            str(test_folder / subdir.name) + "/",
                            '-ar',
                        ])

        collect_all(root_dir, 'library', '*.py', test_folder)
        collect_all(root_dir, 'keywords', '*.robot', test_folder)

        print("Archive content:")
        for file in test_folder.glob("**/*"):
            print(f"\t\t{file.relative_to(test_folder)}")

        try:
            zip_folder = Path(tempfile.mkdtemp())
            os.chdir(test_folder)
            archive = Path(shutil.make_archive(
                'tests', 'zip',
                root_dir=test_folder.parent,
                base_dir=test_folder.name
            ))
            return base64.encodebytes(archive.read_bytes()).decode('utf-8')

        finally:
            shutil.rmtree(zip_folder)

    finally:
        shutil.rmtree(working_space)
        os.chdir(pwd)
