import shutil
from retrying import retry
import hashlib
import os
import tempfile
import click
import humanize
from tools import __assert_file_exists
from tools import __system
from tools import __safe_filename
from tools import __find_files
from tools import __read_file
from tools import __write_file
from tools import __append_line
from tools import __exists_odoo_commit
from tools import __get_odoo_commit
from tools import _get_dump_files, __dc
from . import cli, pass_config, dirs, files
from lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def image(config):
    """
    Database related actions.
    """
    click.echo("database-name: {}, in ram: {}".format(config.dbname, config.run_postgres_in_ram))
    pass

@image.command(name='import')
@click.argument('filename', required=True)
def image_import(filename):
    """
    Imports binary image of machine
    """
    from . import BACKUPDIR
    filename = _get_dump_files("Choose image to import")
    if not filename:
        return
    dump_path = os.path.join(BACKUPDIR, os.path.basename(filename))
    __system([
        "docker",
        "load",
        dump_path
    ])

@image.command(name='export')
@click.argument('filename', required=False)
@pass_config
@click.pass_context
def image_export(ctx, config, filename):
    """
    Exports all images of the customizations to one file.
    Can be imported via image-import.
    """
    from . import BACKUPDIR
    dump_path = os.path.join(BACKUPDIR, config.customs + '.docker.images.tar')
    folder = tempfile.mkdtemp()
    image_ids = __dc([
        'images',
        '-q',
    ], suppress_out=True).split("\n")
    filesize = 0
    for image in image_ids:
        if not image:
            continue
        filepath = os.path.join(folder, image)
        click.echo("Storing {} to {}".format(image, filepath))
        __system([
            'docker',
            'save',
            image,
            '-o',
            filepath,
        ], suppress_out=True)
        filesize += os.stat(filepath).st_size
        click.echo("File size currently:", humanize.naturalsize(filesize))
    if not filesize:
        raise Exception("No images found!")
    __system([
        "tar",
        "cfz",
        dump_path,
        '.',
    ], cwd=folder)
    click.echo(os.path.basename(dump_path))
    compressed_size = os.stat(dump_path).st_size
    ratio = round(float(compressed_size) / float(filesize) * 100.0, 1)
    click.echo("Compressed:", humanize.naturalsize(compressed_size), "Uncompress:", humanize.naturalsize(filesize), "Ratio:", ratio)

@retry(wait_random_min=500, wait_random_max=800, stop_max_delay=30000)
def __get_docker_image():
    """
    Sometimes this command fails; checked with pudb behind call, hostname matches
    container id; seems to be race condition or so
    """
    hostname = os.environ['HOSTNAME']
    result = [x for x in __system(["/opt/docker/docker", "inspect", hostname], suppress_out=True).split("\n") if "\"Image\"" in x]
    if result:
        result = result[0].split("sha256:")[-1].split('"')[0]
        return result[:12]
    return None
