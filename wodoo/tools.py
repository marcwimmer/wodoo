import platform
import requests
import stat
from contextlib import contextmanager
import re
import docker
try:
    import arrow
except ImportError: pass
from pathlib import Path
import io
import traceback
import json
import pipes
import tempfile
from datetime import datetime
try:
    from retrying import retry
except ImportError: retry = None
from .wait import tcp as tcp_wait
import shutil
try:
    import click
except ImportError: pass
import os
import subprocess
import time
import sys
from threading import Thread
from queue import Queue
import inspect
from copy import deepcopy
from passlib.context import CryptContext

class DBConnection(object):
    def __init__(self, dbname, host, port, user, pwd):
        assert dbname
        assert host
        assert port
        assert user
        assert pwd
        self.dbname = dbname
        self.host = host
        self.port = int(port)
        self.user = user
        self.pwd = pwd

    def shortstr(self):
        return "{}:{}/{}".format(self.host, self.port, self.dbname)

    def clone(self, dbname=None):
        result = deepcopy(self)
        if dbname:
            result.dbname = dbname
        return result

    def get_psyco_connection(self, db=None):
        import psycopg2
        conn = psycopg2.connect(
            dbname=db or self.dbname,
            user=self.user,
            password=self.pwd,
            host=self.host,
            port=self.port,
            connect_timeout=int(os.getenv("PSYCOPG_TIMEOUT", "3")),
        )
        return conn

    @contextmanager
    def connect(self, db=None):
        conn = self.get_psyco_connection(db=db)
        cr = conn.cursor()
        try:
            yield cr
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cr.close()
            conn.close()

def __assert_file_exists(path, isdir=False):
    if not Path(path).exists():
        raise Exception("{} {} not found!".format(
            'Directory' if isdir else 'File',
            path
        ))

def __safe_filename(name):
    name = name or ''
    for c in [':\\/+?*;\'" ']:
        name = name.replace(c, "_")
    return name

def __write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

def __append_line(path, line):
    if not Path(path).exists():
        content = ""
    else:
        with open(path, 'r') as f:
            content = f.read().strip()
    content += "\n" + line
    with open(path, 'w') as f:
        f.write(content)

def __read_file(path, error=True):
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception:
        if not error:
            return""

def E2(name):
    if name.startswith("$"):
        name = name[1:]
    return os.getenv(name, "")

def __get_odoo_commit():
    from .odoo_config import MANIFEST
    commit = MANIFEST().get('odoo-commit', "")
    if not commit:
        raise Exception("No odoo commit defined.")
    return commit

def _execute_sql(connection, sql, fetchone=False, fetchall=False, notransaction=False, no_try=False, params=None, return_columns=False):

    @retry(wait_random_min=500, wait_random_max=800, stop_max_delay=30000)
    def try_connect(connection):
        try:
            if hasattr(connection, 'clone'):
                connection = connection.clone(dbname='postgres')
            _execute_sql(connection, "SELECT * FROM pg_catalog.pg_tables;", no_try=True)
        except Exception as e:
            click.secho(str(e), fg='red')

    if not no_try:
        try_connect(connection)

    def _call_cr(cr):
        cr.execute(sql, params)
        if fetchone:
            return cr.fetchone()
        elif fetchall:
            return cr.fetchall()

    if isinstance(connection, DBConnection):
        conn = connection.get_psyco_connection()
        conn.autocommit = notransaction
        cr = conn.cursor()
        try:
            res = _call_cr(cr)
            conn.commit()
            if return_columns:
                return [x.name for x in cr.description], res
            else:
                return res
        except Exception:
            conn.rollback()
            raise
        finally:
            cr.close()
            conn.close()
    else:
        return _call_cr(connection)

def _exists_db(conn):
    sql = "select count(*) from pg_database where datname='{}'".format(conn.dbname)
    conn = conn.clone()
    conn.dbname = 'postgres'
    record = _execute_sql(conn, sql, fetchone=True)
    if not record or not record[0]:
        return False
    return True


def _exists_table(conn, table_name):
    record = _execute_sql(conn, """
    select exists(
        select 1
        from information_schema.tables
        where table_name = '{}'
    )
    """.format(table_name), fetchone=True)
    return record[0]

def _wait_postgres(config):
    if config.run_postgres:
        conn = config.get_odoo_conn().clone(dbname='postgres')
        container_ids = __dc_out(['ps', '-a', '-q', '--filter', 'name=postgres']).decode('utf-8').strip().split("\n")
        client = docker.from_env()
        postgres_containers = []
        for container_id in container_ids:
            container = client.containers.get(container_id)
            if not container:
                continue
            if not container.attrs['State']['Running']:
                continue
            postgres_containers += [container]

        # if running containers wait for health state:
        if not postgres_containers:
            raise Exception("No running container found!")

        _wait_for_port(conn.host, conn.port, timeout=30)
        trycount = 0
        try:
            _execute_sql(conn, sql="""
            SELECT table_schema,table_name
            FROM information_schema.tables
            ORDER BY table_schema,table_name
            LIMIT 1;
            """)
        except Exception:
            if trycount > 20:
                raise
            else:
                click.secho("Waiting again for postgres...")
                time.sleep(3)
                trycount += 1

def _is_container_running(machine_name):
    import docker
    container_id = __dc_out(['ps', '-q', machine_name]).strip()
    if container_id:
        container = list(filter(lambda container: container.id == container_id, docker.from_env().containers.list()))
        if container:
            container = container[0]
            return container.status == 'running'
    return False

def is_up(*machine_name):
    assert len(machine_name) == 1
    click.echo('Running' if _is_container_running(machine_name[0]) else 'Not Running', machine_name[0])

def _isfloat(x):
    try:
        float(x)
    except Exception:
        return False
    else:
        return True

def _makedirs(path):
    path.mkdir(exist_ok=True, parents=True)

def _remove_postgres_connections(connection, sql_afterwards=""):
    click.echo("Removing all current connections from {}".format(connection.dbname))
    if os.getenv("POSTGRES_DONT_DROP_ACTIVITIES", "") != "1":
        if _exists_db(connection):
            SQL = """
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{}'
                AND pid <> pg_backend_pid();
            """.format(connection.dbname, sql_afterwards)
            _execute_sql(connection.clone(dbname='postgres'), SQL, notransaction=True)
            if sql_afterwards:
                _execute_sql(connection.clone(dbname='postgres'), sql_afterwards, notransaction=True)

def __rename_db_drop_target(conn, from_db, to_db):
    if to_db in ('postgres', 'template1'):
        raise Exception("Invalid: {}".format(to_db))
    _remove_postgres_connections(conn.clone(dbname=from_db))
    _remove_postgres_connections(conn.clone(dbname=to_db))
    _execute_sql(conn.clone(dbname='postgres'), "drop database if exists {to_db}".format(**locals()), notransaction=True)
    _execute_sql(conn.clone(dbname='postgres'), "alter database {from_db} rename to {to_db};".format(**locals()), notransaction=True)
    _remove_postgres_connections(conn.clone(dbname=to_db))

def _merge_env_dict(env):
    res = {}
    for k, v in os.environ.items():
        res[k] = v
    for k, v in env.items():
        res[k] = v
    return res

def _set_default_envs(env):
    env = env or {}
    env.update({
        'DOCKER_BUILDKIT' : '1',
        'COMPOSE_DOCKER_CLI_BUILD': '1',
    })
    return env

def __dc(cmd, env={}):
    c = __get_cmd() + cmd
    env = _set_default_envs(env)
    return subprocess.check_call(c, env=_merge_env_dict(env))

def __dc_out(cmd, env={}):
    c = __get_cmd() + cmd
    env = _set_default_envs(env)
    return subprocess.check_output(c, env=_merge_env_dict(env))

def __dcexec(cmd, interactive=True, env=None):
    env = _set_default_envs(env)
    c = __get_cmd()
    c += ['exec']
    if not interactive:
        c += ['-T']
    if env:
        for k, v in env.items():
            c+= ['-e', f"{k}={v}"]
    c += cmd
    if interactive:
        subprocess.call(c)
    else:
        return subprocess.check_output(cmd)

def __dcrun(cmd, interactive=False, env={}, returncode=False, pass_stdin=None):
    env = _set_default_envs(env)
    cmd2 = [os.path.expandvars(x) for x in cmd]
    cmd = ['run']
    if not interactive:
        cmd += ['-T']
    cmd += ['--rm']
    for k, v in env.items():
        cmd += ['-e{}={}'.format(k, v)]
    cmd += cmd2
    del cmd2
    cmd = __get_cmd() + cmd
    if interactive:
        optional_params = {}
        if pass_stdin:
            optional_params['input'] = pass_stdin
            optional_params['universal_newlines'] = True
        else:
            optional_params['stdin'] = sys.stdin
        subprocess.run(cmd, check=True, **optional_params)
    else:
        if returncode:
            process = subprocess.Popen(cmd)
            process.wait()
            return process.returncode
        else:
            optional_params = {}
            if pass_stdin:
                optional_params['input'] = pass_stdin
                optional_params['universal_newlines'] = True
            return subprocess.check_output(cmd, **optional_params)

def _askcontinue(config, msg=None):
    if msg:
        click.echo(msg)
    if config and config.force:
        return
    input("Continue? (Ctrl+C to break)")

def _wait_for_port(host, port, timeout=None):
    res = tcp_wait.open(port, host=host, timeout=timeout)
    if not res and timeout:
        raise Exception("Timeout elapsed waiting for {}:{}".format(host, port))

def __replace_in_file(filepath, text, replacewith):
    with open(filepath, 'r') as f:
        content = f.read()
    content = content.replace(text, replacewith)
    with open(filepath, 'w') as f:
        f.write(content)

def __rm_file_if_exists(path):
    if path.exists():
        path.unlink()

def __rmtree(path):
    config = _get_missing_click_config()
    if not path or path == '/':
        raise Exception("Not allowed: {}".format(path))
    if not path.startswith("/"):
        raise Exception("Not allowed: {}".format(path))
    if not any(path.startswith(config.dirs['odoo_home'] + x) for x in ['/tmp', '/run/']):
        if "/tmp" in path:
            pass
        else:
            raise Exception('not allowed')
    shutil.rmtree(path)

def __safeget(array, index, exception_on_missing, file_options=None):
    if file_options:
        if file_options.exists():
            file_options = '\n' + '\n'.join(file_options.glob("*"))
    file_options = file_options or ''
    if len(array) < index + 1:
        raise Exception(exception_on_missing + file_options)
    return array[index]

def __get_cmd():
    config = _get_missing_click_config()
    cmd = config.commands['dc']
    cmd = [os.path.expandvars(x) for x in cmd]
    return cmd

def __cmd_interactive(*params):
    cmd = __get_cmd() + list(params)
    proc = subprocess.Popen(cmd)
    proc.wait()
    return proc.returncode
    # ctrl+c leads always to error otherwise
    # if proc.returncode:
    # raise Exception("command failed: {}".format(" ".join(params)))

def __empty_dir(dir, user_out=False):
    dir = Path(dir)
    try:
        for x in dir.glob("*"):
            if x.is_dir():
                if user_out:
                    click.secho("Removing {}".format(x.absolute()))
                shutil.rmtree(x.absolute())
            else:
                if user_out:
                    click.secho("Removing {}".format(x.absolute()))
                x.unlink()
    except:
        click.secho(f"Could not delete: {dir}", fg='red')
        raise

def __file_default_content(path, default_content):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(default_content)

def __file_get_lines(path):
    return path.read_text().strip().split("\n")

def _get_machines():
    config = _get_missing_click_config()
    cmd = config.commands['dc'] + ['ps', '--services']
    out = subprocess.check_output(cmd, cwd=config.dirs['odoo_home'])
    out = set(filter(lambda x: x, out.split("\n")))
    return list(sorted(out))


if retry:
    @retry(wait_random_min=500, wait_random_max=800, stop_max_delay=30000)
    def __get_docker_image():
        """
        Sometimes this command fails; checked with pudb behind call, hostname matches
        container id; seems to be race condition or so
        """
        hostname = os.environ['HOSTNAME']
        result = [x for x in subprocess.check_output(["/opt/docker/docker", "inspect", hostname]).split("\n") if "\"Image\"" in x]
        if result:
            result = result[0].split("sha256:")[-1].split('"')[0]
            return result[:12]
        return None

def _file2env(filepath, out_dict=None):
    from . import MyConfigParser
    if not filepath.exists():
        return
    config = MyConfigParser(filepath)
    for k in config.keys():
        if out_dict:
            out_dict[k] = config[k]
        else:
            os.environ[k] = config[k]

def _get_bash_for_machine(machine):
    return 'bash'

def __get_installed_modules(config):
    conn = config.get_odoo_conn()
    rows = _execute_sql(
        conn,
        sql="SELECT name, state from ir_module_module where state in ('installed', 'to upgrade');",
        fetchall=True
    )
    return [x[0] for x in rows]

def __splitcomma(param):
    if isinstance(param, str):
        if not param:
            return []
        return [x.strip() for x in param.split(',') if x.strip()]
    elif isinstance(param, (tuple, list)):
        return list(param)
    raise Exception("not impl")

def __make_file_executable(filepath):
    st = os.stat(filepath)
    os.chmod(filepath, st.st_mode | stat.S_IEXEC)

def __try_to_set_owner(UID, path, recursive=False, autofix=False):
    if path.is_dir():
        filename = tempfile.mktemp(suffix='.findoutput')
        find_command = f"find '{path}' -not -type l -not -user {UID}"
        os.system(f"{find_command} > '{filename}'")
        filename = Path(filename)
        try:
            res = filename.read_text().strip().split("\n")
            filename.unlink()
            if not res:
                return

            runs = ['sudo'] if os.getenv("SUDO_UID") else ['', 'sudo']
            for irun, run in enumerate(runs):
                # dont set to UID:UID --> group not necessarily matches user id
                for line in res:
                    if not line: continue
                    GID = os.stat(line).st_gid
                    try:
                        os.chown(line, UID, GID)
                    except:
                        click.secho(traceback.format_stack())
                        click.secho(f"Could not set owner {UID} {GID} on directory {line}")
                        sys.exit(-1)

        finally:
            if filename.exists():
                filename.unlink()

def _display_machine_tips(config, machine_name):
    dir = config.dirs['images'] / machine_name
    if not dir.is_dir():
        return

    for filename in config.dirs['images'].glob("**/tips.txt"):
        filepath = config.dirs['images'] / filename
        if filepath.parent.name == machine_name:
            content = (config.dirs['images'] / filename).read_text()
            click.echo("")
            click.echo("Please note:")
            click.echo("---------------")
            click.echo("")
            click.echo(content)
            click.echo("")
            click.echo("")

def __do_command(cmd, *params, **kwparams):
    cmd = cmd.replace('-', '_')
    return globals()[cmd](*params, **kwparams)


def _get_dump_files(backupdir, fnfilter=None):
    import humanize
    _files = list(backupdir.glob("*"))

    def _get_ctime(filepath):
        if fnfilter and fnfilter not in filepath.name:
            return False
        try:
            return (backupdir / filepath).stat().st_ctime
        except Exception:
            return 0
    rows = []
    for i, file in enumerate(sorted(filter(lambda x: _get_ctime(x), _files), reverse=True, key=_get_ctime)):
        filepath = backupdir / file
        delta = arrow.get() - arrow.get(filepath.stat().st_mtime)
        rows.append((
            i + 1,
            file.name,
            humanize.naturaltime(delta),
            humanize.naturalsize(filepath.stat().st_size),
        ))

    return rows

def __get_dump_type(filepath):
    temp = Path(tempfile.mktemp(suffix='.check'))
    MARKER = "PostgreSQL database dump"
    FNULL = open(os.devnull, 'w')
    proc = subprocess.Popen(['gunzip', '-c', filepath], stdout=subprocess.PIPE, stderr=FNULL, bufsize=1)

    def reader(proc, pipe):
        try:
            lines = 0
            with pipe:
                for line in iter(pipe.readline, ''):
                    with temp.open('a') as f:
                        f.write(line.decode("utf-8", errors='ignore'))
                        lines += 1
                        if lines > 20:
                            break
        finally:
            if not proc.returncode:
                proc.kill()

    Thread(target=reader, args=[proc, proc.stdout]).start()
    proc.wait()

    if temp.exists():
        content = temp.read_text()
        if MARKER in content:
            return 'zipped_sql'
        if content.startswith("PGDMP"):
            return "zipped_pgdump"
    with open(filepath, 'r') as f:
        for i, line in enumerate(f):
            if i == 0 and line.startswith("PGDMP"):
                return 'pgdump'
            if i > 50:
                break
            if MARKER in line:
                return "plain_text"
    return 'unzipped_pgdump'

def _dropdb(config, conn):
    import inquirer
    if _exists_db(conn):
        # TODO ask for name
        if not config.force:
            questions = [
                inquirer.Text('name',
                              message="Database {} will be dropped. Please enter the name to delete it ({})".format(conn.dbname, conn.shortstr()))
            ]
            answer = inquirer.prompt(questions)
            if answer['name'] != conn.dbname:
                click.secho("Dropping aborted - you did not answer: {}".format(conn.dbname), fg='red')
                sys.exit(1)
    else:
        click.echo("Database does not exist yet: {}".format(conn.dbname))
    click.echo("Stopping all services and creating new database")
    _remove_postgres_connections(conn, 'drop database {};'.format(conn.dbname))

    click.echo("Database dropped {}".format(conn.dbname))

def remove_webassets(conn):
    click.echo("Removing web assets")
    conn = conn.get_psyco_connection()
    cr = conn.cursor()
    try:
        cr.execute("delete from ir_attachment where res_model = 'ir.ui.view' and name ilike '%assets_%';")
        cr.execute("delete from ir_attachment where res_model = 'ir.ui.view' and name ilike '%web_editor.summernote%';")
        cr.execute("delete from ir_attachment where res_model = 'ir.ui.view' and name ilike '%.less%';")
        cr.execute("delete from ir_attachment where res_model = 'ir.ui.view' and name ilike '%.scss%';")
        cr.execute("delete from ir_attachment where name ilike '/web/%web%asset%'")
        cr.execute("delete from ir_attachment where name ilike 'import_bootstrap.less'")
        cr.execute("delete from ir_attachment where name ilike '%.less'")
        cr.execute("delete from ir_attachment where name ilike '%.scss'")
        cr.execute("delete from ir_attachment where name ilike 'web_icon_data'")
        cr.execute("delete from ir_attachment where name ilike 'web_editor.summernote.%'")
        conn.commit()
    finally:
        cr.close()
        conn.close()
    click.secho("A restart is usually required, when deleting web assets.", fg='green')

def get_dockercompose():
    from . import files
    import yaml
    content = __read_file(files['docker_compose'])
    compose = yaml.safe_load(content)
    return compose

def get_volume_names():
    from . import project_name
    vols = get_dockercompose()['volumes'].keys()
    return [f"{project_name}_{x}" for x in vols]

def __running_as_root_or_sudo():
    output = subprocess.check_output(["/usr/bin/id", '-u']).strip().decode('utf-8')
    return output == "0"

def __replace_all_envs_in_str(content, env):
    """
    Docker does not allow to replace volume names or service names, so we do it by hand
    """
    all_params = re.findall(r'\$\{[^\}]*?\}', content)
    for param in all_params:
        name = param
        name = name.replace("${", "")
        name = name.replace("}", "")
        if name in env.keys():
            content = content.replace(param, env[name])
    return content

def __remove_tree(dir, retry=3, interval=2):
    if retry == 0:
        retry = 1
        interval = 0

    E = None
    for i in range(retry):
        try:
            shutil.rmtree(dir)
        except Exception as e:
            E = e
            time.sleep(interval)
        else:
            return
    if E:
        raise E

def __hash_odoo_password(pwd):
    from .odoo_config import current_version
    if current_version() in [
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
            10.0,
            9.0,
    ]:
        setpw = CryptContext(schemes=['pbkdf2_sha512', 'md5_crypt'])
        return setpw.encrypt(pwd)
    else:
        raise NotImplementedError()

def abort(msg, nr=1):
    click.secho(msg, fg='red', bold=True)
    sys.exit(nr)

def sync_folder(dir, dest_dir, excludes=None):
    dir = Path(dir)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(exist_ok=True, parents=True)
    if not dir or not dest_dir or len(str(dir)) < 5 or len(str(dest_dir)) < 5:
        raise Exception('invalid dirs: {} {}'.format(
            dir,
            dest_dir
        ))
    if platform.system() in ['Linux', 'Darwin']:
        cmd = ['rsync', str(dir) + "/", str(dest_dir) + "/", "-r", "--delete-after"]
        for exclude in (excludes or []):
            cmd += ["--exclude={}".format(exclude)]
        subprocess.check_call(cmd)
    else:
        raise NotImplementedError()

def copy_dir_contents(dir, dest_dir, exclude=None):
    assert dir.is_dir()
    assert dest_dir.is_dir()
    exclude = exclude or []
    for x in dir.glob("*"):
        if exclude:
            if x.name in exclude:
                continue
        if not x.is_dir():
            shutil.copy(str(x.absolute()), str((dest_dir / x.name).absolute()))
        else:
            shutil.copytree(str(x.absolute()), str((dest_dir / x.name).absolute()))

def _get_host_ip():
    conn = os.getenv("SSH_CONNECTION", "")
    if conn:
        conn = [x for x in conn.split(" ") if x]
        return conn[2]

def _is_dirty(repo, check_submodule, assert_clean=False):
    from git import Repo
    from git import InvalidGitRepositoryError
    from git import NoSuchPathError

    def raise_error():
        if assert_clean:
            click.secho("Dirty directory - please cleanup: {}".format(repo.working_dir), bold=True, fg='red')
            sys.exit(42)

    if repo.is_dirty() or repo.untracked_files:
        raise_error()
        return True
    if check_submodule:
        try:
            repo.submodules
        except AttributeError:
            pass
        else:
            for submodule in repo.submodules:
                try:
                    sub_repo = Repo(submodule.path)
                except InvalidGitRepositoryError:
                    click.secho("Invalid Repo: {}".format(submodule), bold=True, fg='red')
                except NoSuchPathError:
                    click.secho("Invalid Repo: {}".format(submodule), bold=True, fg='red')
                else:
                    if _is_dirty(sub_repo, True, assert_clean=assert_clean):
                        raise_error()
                        return True
    return False

def __assure_gitignore(gitignore_file, content):
    p = Path(gitignore_file)
    if not p.exists():
        p.write(content + "\n")
        return
    exists = [l for l in gitignore_file.read_text().split("\n") if l.strip() == content]
    if not exists:
        with p.open('a') as f:
            f.write(content)
            f.write("\n")

def __needs_docker(config):
    if not config.use_docker:
        click.secho("Docker needed USE_DOCKER=1", fg='red')
        sys.exit(1)

def exec_file_in_path(filename):
    def _g():
        for p in [
            '/usr/local/bin',
            '/usr/bin',
            '/bin',
        ]:
            filepath = Path(p) / filename
            if filepath.exists():
                yield filepath
    try:
        return next(_g())
    except StopIteration:
        raise Exception(f"Could not find in path: {filename}")

def measure_time(method):
    def wrapper(*args, **kwargs):
        started = datetime.now()
        result = method(*args, **kwargs)
        ended = datetime.now()
        click.secho("Took: {} seconds".format((ended - started).total_seconds()), fg='yellow')
        return result
    return wrapper

def _extract_python_libname(x):
    regex = re.compile(r'[\w\-\_]*')
    x = x.replace('-', '_')
    match = re.findall(regex, x)[0]
    return match

def split_hub_url(config):
    """
    Splits hub url into user, password and url and prefix
    user:password@registry.itewimmer.de:443/prefix
    """
    url = config.HUB_URL
    if not url:
        return None
    username, password = url.split(":", 1)
    password = password.split("@")[0]
    url = url.split("@")[1]
    url, prefix = url.split("/", 1)
    return {
        'url': url,
        'password': password,
        'username': username,
        'prefix': prefix,
    }

def _get_missing_click_config():
    from .click_config import Config
    config = Config(quiet=True)
    for stack in inspect.stack():
        frame = stack.frame
        if 'ctx' in frame.f_locals and 'config' in frame.f_locals:
            config = frame.f_locals['config']
    return config

def execute_script(config, script, message):
    if script.exists():
        click.secho(f"Executing reload script: {script}", fg='green')
        os.system(script)
    else:
        if config.verbose:
            click.secho(f"{message}\n{script}", fg='yellow')

def get_services(config, based_on, yml=None):
    import yaml
    content = yml or yaml.safe_load(config.files['docker_compose'].read_text())

    def collect():
        for service_name, service in content['services'].items():
            merge = service.get('labels', {}).get('compose.merge')
            if merge and based_on in merge or merge == based_on:
                yield service_name

    res = list(set(collect()))
    return res

def search_env_path(executable_file):
    def _search():
        for path in os.getenv("PATH").split(":"):
            yield from Path(path).glob(executable_file)
    res = list(_search())
    if res:
        return res[0]
    raise Exception(f"Not found: {executable_file}")

def download_file_and_move(url, dest):
    file = download_file(url)
    file.rename(dest)

def download_file(url):
    print(f"Downloading {url}")
    local_filename = url.split('/')[-1]
    with requests.get(url, stream=True) as r:
        with open(local_filename, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

    return Path(local_filename)
