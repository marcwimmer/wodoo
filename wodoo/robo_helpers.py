"""

Sample robo file

# list some modules that need to be installed
# odoo-require: account,web,stock,crm

*** Settings ***
Documentation     MyTest1
Resource          ../path/to/robot_utils/keywords/odoo_ee.robot
#Asset             /robdata



*** Keywords ***

*** Test Cases ***
Test Requirement installed
    Log To Console                  Check if test requirement is ok
    ${modules}=  					Odoo Search Records  model=ir.module.module  domain=[('name', '=', 'required_by_robot1')]  count=False
	Should Be Equal as Strings    	${modules[0].state}  installed
    Log To Console                  Module requirements checked



*** Keywords ***
Search for the admin
    Odoo Search                     model=res.users  domain=[]  count=False
    ${count}=  Odoo Search          model=res.users  domain=[('login', '=', 'admin')]  count=True
    Should Be Equal As Strings      ${count}  1
    Log To Console  ${count}





"""

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None
import json
import inquirer
from pathlib import Path
import click
import subprocess
import shutil
import tempfile
import os
import base64
import sys
import arrow
from .tools import abort
from .tools import __empty_dir


def _normalize_robot_line(line):
    line = line.split("#")[0]
    line = line.replace("\t", "  ")
    while "   " in line:
        line = line.replace("   ", "  ")

    return line


def _get_all_robottest_files(path=None):
    from .odoo_config import customs_dir

    testfiles = []
    path = path or customs_dir()
    for _file in path.glob("**/*.robot"):
        if "keywords" in _file.parts:
            continue
        if "library" in _file.parts:
            continue

        testfiles.append(_file.relative_to(path))
        del _file
    return testfiles


def collect_all(root_dir, robo_file_content):
    """collects files in all directories by glob pattern being in a directory with subdir name and copies
    the files to dest_folder

    Args:
        root_dir (string): name of the directory, where to start searching
        robo_file_content (string): Robot File Content
    """
    yield from _get_required_odoo_modules_from_robot_file(robo_file_content)
    try:
        for line in robo_file_content.splitlines():
            line = _normalize_robot_line(line)
            if line.startswith("Resource") and line.endswith(".robot"):
                filepath = line.split("  ")[1]
                filepath = root_dir / filepath
                if not filepath.exists():
                    abort((f"Could not find file {filepath}"))
                content = filepath.read_text()
                yield from collect_all(filepath.resolve().parent, content)

    except Exception as ex:  # pylint: disable=broad-except
        abort(str(ex))


def _get_required_odoo_modules_from_robot_file(filecontent):
    """Extracts modules from odoo that need to be installed for the test.
    Evaluates odoo-require: <modulelist> comment

    Args:
        filecontent (str): Robot File Content

    Yields:
        list[str]: The odoo-module names.
    """
    lines = filecontent.split("\n")
    for line in lines:
        if "odoo-require:" in line:
            line = line.split(":", 1)[1].strip().split(",")
            line = [x.strip() for x in line]
            yield from line


def get_odoo_modules(verbose, test_files, root_dir):
    """Makes archive of robot test containing all aggregated keywords.

    Args:
        test_files (list of paths): The robot test files to be packed

    Returns:
        bytes: the archive in bytes format
    """
    test_files = [x.absolute() for x in test_files]

    for file in test_files:
        file_content = file.read_text()
        yield from collect_all(file.parent, file_content)


def _eval_robot_output(
    config, output_path, started, output_json, token, rm_tokendir, results_file
):
    results_json = output_path / (results_file or "results.json")
    test_results = json.loads(results_json.read_text())
    failds = [x for x in test_results if not x.get("all_ok")]
    color_info = "green"

    def print_row(rows, fg):
        if not rows:
            return

        headers = [
            "name",
            "all_ok",
            "count",
            "avg_duration",
            "min_duration",
            "max_duration",
        ]

        def data(row):
            return [row.get(x) for x in headers]

        if tabulate:
            click.secho(
                tabulate(map(data, rows), headers=headers, tablefmt="fancy_grid"), fg=fg
            )

    print_row(list(filter(lambda x: x["all_ok"], test_results)), fg="green")
    print_row(list(filter(lambda x: not x["all_ok"], test_results)), fg="red")

    click.secho(
        (f"Duration: {(arrow.utcnow() - started).total_seconds()}s"), fg=color_info
    )

    # move completed runs without token to parent to reduce the amount of intermediate files
    find_results_path = None
    token_path = output_path / token
    for filepath in token_path.glob("*"):
        if not filepath.is_dir():
            continue
        dest_path = output_path / filepath.name
        if dest_path.exists() and dest_path.is_dir():
            shutil.rmtree(dest_path)
        elif dest_path.exists():
            dest_path.unlink()
        if rm_tokendir:
            shutil.move(filepath, dest_path)
            find_results_path = dest_path
        else:
            shutil.copytree(filepath, dest_path)
            find_results_path = filepath

    if rm_tokendir and token_path.exists():
        shutil.rmtree(token_path)

    click.secho(f"Outputs are generated in {find_results_path}", fg="yellow")
    click.secho(
        ("Watch the logs online at: " f"http://host:{config.PROXY_PORT}/robot-output")
    )

    for line in test_results:
        line["testoutput"] = str(find_results_path)

    if output_json:
        click.secho("---!!!---###---")
        click.secho(json.dumps(test_results, indent=4))
    results_json.write_text(json.dumps(test_results, indent=4))

    if failds:
        sys.exit(-1)


def _select_robot_filename(file, run_all):
    testfiles = _get_all_robottest_files()

    if file and run_all:
        click.secho("Cannot provide all and file together!", fg="red")
        sys.exit(-1)

    if file:
        match = [x for x in map(str, testfiles) if file in x]
        if len(match) > 1:
            if "/" in file:
                match = [x for x in match if x == file]
            if len(match) > 1:
                click.secho(f"Not unique: {file}", fg="red")
                sys.exit(-1)

        if match:
            filename = Path(match[0])
        else:
            click.secho(f"Not found: {file}", fg="red")
            sys.exit(-1)

        if filename not in testfiles:
            click.secho(f"Not found: {filename}", fg="red")
            sys.exit(-1)
        filename = [filename]
    else:
        testfiles = sorted(testfiles)
        if not run_all:
            message = "Please choose the unittest to run."
            try:
                filename = [
                    inquirer.prompt(
                        [inquirer.List("filename", message, choices=testfiles)]
                    ).get("filename")
                ]
            except Exception:  # pylint: disable=broad-except
                sys.exit(-1)
        else:
            filename = list(sorted(testfiles))

    return filename
