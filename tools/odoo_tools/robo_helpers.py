from pathlib import Path
import shutil
import tempfile
import os
import base64

def _make_archive(test_files):
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
                    if subdir.name in ['keywords', 'library', 'data']:
                        shutil.copytree(subdir, test_folder / subdir.name)
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
