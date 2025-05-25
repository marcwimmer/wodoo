# Odoo Docker Framework

Provides functionalities:

- setup empty new odoo with one bash command `odoo init --version 15.0`

- setup full fleged odoo server environment containing
  - supports MANIFEST file in odoo root directory to install and uninstall modules
  - postgres with pg_activity, enhanced pgcli
  - fake webmail to receive AND SEND mails
  - logs.io integration to display container output on web browser
  - dividing web, cron, queuejob container per default
  - progress bar on postgres dump/restore

- fzf compatible creation of and AST of your project

- fast restore / create snapshots of complete databases using btrfs, which helps testing things on customer databases

## How to install

### Install minimum

```bash
pipx install wodoo
```


### optional: To be not blocked when working on btrfs/zfs volumes and so, this is suggested on dev machines:


```bash
cat << 'EOF' > /etc/sudoers.d/odoo
Cmnd_Alias ODOO_COMMANDS_ODOO = /usr/bin/find *, /var/lib/wodoo_env/bin/odoo *, /usr/bin/btrfs subvolume *, /usr/bin/mkdir *, /usr/bin/mv *, /usr/bin/rsync *, /usr/bin/rm *,  /usr/bin/du *, /usr/local/bin/odoo *, /usr/bin/btrfs subvol show *, /usr/sbin/gosu *
odoo ALL=NOPASSWD:SETENV: ODOO_COMMANDS_ODOO

EOF
```

## How To: Make new empty odoo instance

```bash
odoo init <folder>
cd <folder>
odoo reload
odoo -f db reset
odoo up -d

# now open browser on http://localhost
```

## Store settings in ./odoo of source code


## How to extend an existing service

- make a docker-compose file like ~/.odoo/docker-compose.yml

```yml
services:
  odoo3:
    labels:
      compose.merge: base-machine
    environment:
      WHAT YOU WANT
    volumes:
      WHAT YOU WANT

```

### Example for fixed ip addresses

```yml
services:
    proxy:
        networks:
            network1:
                ipv4_address: 10.5.0.6
networks:
    network1:
        driver: bridge
        ipam:
            config:
                - subnet: 10.5.0.0/16
```

### Some labels

```yml
services:
    new_machine:
        ...
        labels:
          odoo_framework.apply_env: 0  # do not apply global environment from settings here

```

## Using the registry

### Pushing

* Configure HUB_URL on the pusher side.
* `>odoo login`
* `>odoo build`
* `>odoo regpush`
* All images even base images like redis are pushed; tag name contains SHA name

### Pulling

* Configure `REGISTRY=1` in settings and setup `HUB_URL`
* `>odoo login`
* `>odoo regpull`
* All images will be pulled from registry

## Services Explained

### Proxy

* nodejs application
* between user browser and odoo
* if odoo is being restarted catches the requests, holds them and releases them to odoo if it is up again
* manages handling of /longpolling path; so if used in custom proxy setups, just refer to that one port here


## Tools

## Backup and Restore

```
odoo backup odoo-db <path> (or default name used)
odoo restore odoo-db <path> (or select from list)
```

### Show Database activity

```
odoo pgactivity
```


## Configurations in ~/.odoo/settings explained

| Setting      | Description|
| :---        |    :----   |
| PROJECT_NAME| Pasted into container names, postgres volumes and so on; please keep it as short as possible, as there are limits example docker containername 53 characters at time of writing|
| DBNAME | Uses projectname or a configured one|
| HUB_URL=value| user:password@host:port/paths.. to configure|
| REGISTRY=1      | Rewrites all build and images urls to HUB_URL. Should be used on production systems to force pull only from registry and block any local buildings.|
| POSTGRES_VERSION=13| Choose from 11, 12, 13, 14|
| ODOO_ENABLE_DB_MANAGER| Enables the odoo db manager|
| DEVMODE=1 | At restore runs safety scripts to disable cronjobs and mailserver and resets passwords|
| RUN_PROXY=1| If the built-in nodejs proxy is enabled |
| RUN_PROXY_PUBLISHED=0/1| If the proxy is reachable from outside the docker network example from 127.0.0.1:8069|
| PROXY_PORT| The port on which you can access with plain http the odoo|
| ODOO_IMAGES_BRANCH| The branch used for ~/.odoo/images|
| ODOO_INSTALL_LIBPOSTAL=1| If set, then the libpostal lib is installed|
| ODOO_QUEUEJOBS_CRON_IN_ONE_CONTAINER=1 | Runs queuejobs and cronjob in the odoo container where also the web application resides|
| ODOO_QUEUEJOBS_CHANNELS=root:40,magento2:1 | Configures queues for queuejob module |
|NAMED_ODOO_POSTGRES_VOLUME| Use a specific external volume; not dropped with down -v command|
|CRONJOB_DADDY_CLEANUP=0 */1 * * * ${JOB_DADDY_CLEANUP}|Turn on grandfather-principle based backup|
|RESTART_CONTAINERS=1|Sets "restart unless-stopped" policy|
|ODOO_DEBUG_LOGLEVEL=info,error,debug|Loglevel for debug inside odoo container|
|APT_PROXY_IP=<ip>|Name/IP where to reach the apt-cacher on the host at buildtime from containers|
|RUN_APT_CACHER|if 1 then host apt cacher|
|PYPI_HOST||

## Odoo Server Configuration in ~/.odoo/settings/odoo.config and odoo.config.${PROJECT_NAME}

Contents will be appended to [options] section of standard odoo configuration.

Configuration may simple look like:


```
setting1=value1
```

or like that:

```
[options]
setting1=value1

[queue_job]
settingqj=valueqj
```

The [options] is prepended automatically if missed.

# MANIFEST File

To placed in project root.

The used odoo instance must be placed in /odoo.

```yaml
{
    "server-wide-modules": [
        "web",
        "field_onchange"
    ],
    "python_version": "3.11.10",
    "version": 17.0,
    "install": [ ...  ],
    "uninstall": [
        "web_tree_many2one_clickable",
        "helpdesk_create_in_new_tab"
    ],
    "devmode_uninstall": [
        "password_security",
    ],
    "tests": [
        "helpdesk_security",
        "visitreports"
    ],
    "before-odoo-update": [
      ["update", "make-sure", "stock_delivery"]
    ],
    "addons_paths": [
        "odoo/odoo/addons",
        "odoo/addons",
        "enterprise",
        "addons_tools"
    ]
}



```

# RobotFramework Commands

## Install modules

Put #odoo-require: crm,sale_stock  in a line in your test

## Uninstall modules

Put #odoo-uninstall: partner_autocomplete  in a line in your test

The partner autocomplete nerves for example.

# Append to odoo docker file

* make files like "Dockerfile.appendix" anywhere in your repo
* to add files, put a directory "Dockerfile.appendix.dir" in the same level; you can
  access files of it with COPY Dockerfile.appendix.dir/*

# Before Reload Actions

If you develop a strange external repository you can define a pre action scripts,
that is executed before the reload and you can adapt some things.

# Pytests

Best executed with:

```bash
time sudo -E pytest
```

# Performance Check

```python
pipx runpip wodoo install line_profiler
~/.local/pipx/venvs/wodoo/bin/python3 -mkernprof -l -v odoo reload
```