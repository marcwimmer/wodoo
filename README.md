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

## How to extend odoo docker image

* make folder ```docker/odoo``` in your source repo
* add file:

```
# docker/odoo/docker-compose.run_odoo_version.14.0.yml
services:
  odoo_appendix:
    build:
        context: $CUSTOMS_DIR/docker/odoo
        dockerfile: $CUSTOMS_DIR/docker/odoo/Dockerfile
```
* add Docker file:

```
# docker/odoo/Dockerfile
FROM ubuntu:22.04
RUN apt update && \
apt install -y tar && \
mkdir /tmp/pack

ADD ibm-iaccess-1.1.0.27-1.0.amd64.deb /tmp/pack
ADD install.sh /tmp/pack/install.sh
ADD odbc.ini /tmp/pack/odbc.ini

RUN chmod a+x /tmp/pack/install.sh
RUN tar cfz /odoo_install_appendix.tar.gz /tmp/pack
```

# add Dockerfile.appendix
```
COPY --from=${PROJECT_NAME}_odoo_appendix /odoo_install_appendix.tar.gz /tmp/install_appendix.tar.gz
RUN \
mkdir /tmp/install_package && \
cd /tmp/install_package && \
tar xfz /tmp/install_appendix.tar.gz && \
ls -lhtra && \
./install.sh
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