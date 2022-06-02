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
# as root:
python3 -m venv /var/lib/wodoo_env
. /var/lib/wodoo_env/bin/activate
python3 -mpip install wheel
python3 -mpip install gimera
python3 -mpip install wodoo
```

### Give sudo rights

To be not blocked when working on btrfs volumes and so, this is suggested on dev machines:

```bash
> /usr/local/sbin/odoo <EOF
#!/bin/bash
sudo -E /opt/odoo/odoo "$@"
EOF

chmod a+x /usr/local/sbin/odoo
```

```bash
> /etc/sudoers.d/odoo <EOF
Cmnd_Alias ODOO_COMMANDS_ODOO = /usr/bin/find *, /opt/odoo/odoo *, /usr/bin/btrfs subvolume *, /usr/bin/mkdir *, /usr/bin/mv *, /usr/bin/rsync *, /usr/bin/rm *,  /usr/bin/du *, /usr/local/bin/odoo *, /opt/odoo/odoo *, /usr/bin/btrfs subvol show *, /usr/sbin/gosu *
odoo ALL=NOPASSWD:SETENV: ODOO_COMMANDS_ODOO

EOF
```

## Make new empty odoo instance

```bash
odoo init <folder>
cd <folder>
odoo reload
odoo -f db reset
odoo up -d

# now open browser on http://localhost
```

## Store settings in ./odoo of source code

This is excellent for jenkins jobs where different branches are tested.

```bash
odoo reload --local --devmode --headless --project-name 'unique_name'
```

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
| ENABLE_DB_MANAGER| Enables the odoo db manager|
| DEVMODE=1 | At restore runs safety scripts to disable cronjobs and mailserver and resets passwords|
| RUN_PROXY=1| If the built-in nodejs proxy is enabled |
| RUN_PROXY_PUBLISHED=0/1| If the proxy is reachable from outside the docker network example from 127.0.0.1:8069|
| PROXY_PORT| The port on which you can access with plain http the odoo|
