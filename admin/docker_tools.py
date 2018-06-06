import subprocess
import os

def __get_docker_image():
    hostname = os.environ['HOSTNAME']
    result = [x for x in subprocess.check_output(["/opt/docker/docker", "inspect", hostname]).split("\n") if "\"Image\"" in x]
    if result:
        result = result[0].split("sha256:")[-1].split('"')[0]
        return result[:12]
    raise Exception("Image not determined")

def get_run_command():
    """
    Returns bash ready command to call simplebash self by run.

    """
    host_odoo_home = os.environ["ODOO_HOME"]
    local_odoo_home = os.environ['LOCAL_ODOO_HOME']
    cmdline = []
    cmdline.append("/opt/docker/docker")
    cmdline.append("run")
    cmdline.append('-e')
    cmdline.append('ODOO_HOME={}'.format(host_odoo_home))
    envfile = os.path.join(local_odoo_home, 'run/settings')
    if os.path.exists(envfile):
        cmdline.append('--env-file')
        cmdline.append(envfile)
    cmdline.append("--rm")
    cmdline.append('-v')
    cmdline.append("{HOST_ODOO_HOME}:{HOST_ODOO_HOME}".format(HOST_ODOO_HOME=os.environ["ODOO_HOME"]))
    cmdline.append("--workdir")
    cmdline.append(host_odoo_home)
    cmdline.append(__get_docker_image())
    return cmdline
