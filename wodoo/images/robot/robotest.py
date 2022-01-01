import base64
import robot
import sys
import shutil
import os
import time
from flask import redirect
import arrow
import subprocess
from flask import jsonify
from flask import make_response
from flask import Flask
from flask import render_template
from flask import url_for
from datetime import datetime
from flask import request
import json
from pathlib import Path
import threading
import logging
import tempfile


FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger('')  # root handler

Browsers = {
    'chrome': {
        'driver': 'Chrome',
        'alias': 'Chrome',
    },
    'firefox': {
        'driver': 'Firefox',
        'alias': 'Headless Firefox',
    }
}

def _get_variables_file(parent_path, content):
    variables_conf = parent_path / 'variables.json'
    variables_conf.write_text(json.dumps(content, indent=4))
    variables_file = parent_path / 'variables.py'
    variables_file.write_text("""
import json
from pathlib import Path

def get_variables():
    return json.loads(Path('{path}').read_text())
""".format(path=variables_conf))
    return variables_file


def _run_test(test_file, output_dir, url, dbname, user, password, browser='firefox', selenium_timeout=20, **run_parameters):
    assert browser in Browsers
    browser = Browsers[browser]

    if password is True:
        password = '1'  # handle limitation of settings files

    variables = {
        "SELENIUM_DELAY": 0,
        "SELENIUM_TIMEOUT": selenium_timeout,
        "ODOO_URL": url,
        "ODOO_URL_LOGIN": url + "/web/login",
        "ODOO_USER": user,
        "ODOO_PASSWORD": password,
        "ODOO_DB": dbname,
        "BROWSER": browser['alias'],
        "ALIAS": browser['alias'],
        "DRIVER": browser['driver'],
    }
    variables_file = _get_variables_file(test_file.parent, variables)
    logger.info(f"Configuration:\n{variables}")
    return not robot.run(
        test_file, outputdir=output_dir, variablefile=str(variables_file),
        **run_parameters,
        )


def _run_tests(params, test_dir, output_dir):
    # init vars
    test_results = []

    started = arrow.get()

    # iterate robot files and run tests
    for test_file in test_dir.glob("*.robot"):
        output_sub_dir = output_dir / f"{test_file.stem}"

        # build robot command: pass all params from data as parameters to the command call
        logger.info(f"Running test {test_file.name} using output dir {output_sub_dir}")
        output_sub_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = 'failed'
            if _run_test(test_file=test_file, output_dir=output_sub_dir, **params):
                result = 'ok'
        except Exception:
            pass
        duration = (arrow.get() - started).total_seconds()

        test_results.append({
            'result': result,
            'name': test_file.stem,
            'duration': duration,
        })
        logger.info(f"Test finished in {duration} seconds.")
        del duration

    return test_results


def run_tests(params, test_file):
    """
    Call this with json request with following data:
    - params: dict passed to robottest.sh
    - archive: robot tests in zip file format
    Expects tar archive of tests files to be executed.


    """
    # setup workspace folders
    logger.info(f"Starting test with params:\n{params}")
    working_space = Path(tempfile.mkdtemp())
    output_dir = Path(os.environ['OUTPUT_DIR'])
    for file in output_dir.glob("*"):
        if file.is_dir():
            shutil.rmtree(file)
        else:
            file.unlink()

    try:
        test_dir = working_space / 'test'
        test_zip = working_space / 'test.zip'
        test_dir.mkdir()
        test_results = []

        # extract tests
        test_zip.write_bytes(base64.b64decode(test_file))
        shutil.unpack_archive(test_zip, extract_dir=test_dir)
        os.chdir(test_dir)

        for test_sub_dir in test_dir.glob("*"):
            test_results += _run_tests(
                params,
                test_sub_dir,
                output_dir,
            )

    finally:
        shutil.rmtree(working_space)

    (output_dir / 'results.json').write_text(json.dumps(test_results))


if __name__ == '__main__':
    archive = sys.stdin.read().rstrip()
    archive = base64.b64decode(archive)
    data = json.loads(archive)
    del archive

    run_tests(**data)
    logger.info("Finished calling robotest.py")
