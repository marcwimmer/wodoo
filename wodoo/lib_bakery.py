"""
Bake your docker images
* source code included
* configuration with environment variables
"""

import click
from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup
from .cli import cli, pass_config, Commands

WHITELIST_PROPS = [
    "DBNAME",
    "DB_HOST",
    "DB_MAXCONN",
    "DB_PORT",
    "DB_PWD",
    "DB_USER",
    "project_name",
    "ODOO_FILES",
    "ODOO_QUEUEJOBS_CRON_IN_ONE_CONTAINER",
    "LIMIT_MEMORY_HARD_CRON",
    "LIMIT_MEMORY_HARD_MIGRATION",
    "LIMIT_MEMORY_HARD_UPDATE",
    "LIMIT_MEMORY_HARD_WEB",
    "LIMIT_MEMORY_SOFT_CRON",
    "LIMIT_MEMORY_SOFT_QUEUEJOBS",
    "LIMIT_MEMORY_SOFT_UPDATE",
    "LIMIT_MEMORY_SOFT_WEB",
    "ODOO_CONFIG_DIR",
]


@cli.group(cls=AliasedGroup)
@pass_config
def bakery(config):
    pass


@bakery.command()
@click.argument("params", nargs=-1)
@click.option("-I", "--no-update-images", is_flag=True)
@pass_config
@click.pass_context
def bake(ctx, config, params, no_update_images):
    from .odoo_config import customs_dir
    from tabulate import tabulate

    metadata = _get_metadata(ctx, config)
    metadata["SHA_IN_DOCKER"] = "1"
    metadata["SRC_EXTRA"] = "0"
    metadata["DOCKER_MACHINE"] = "1"

    for param in params:
        if "=" not in param:
            raise click.BadParameter(
                f"Invalid format: {param}. Use key=value."
            )
        key, value = param.split("=", 1)
        metadata[key] = value

    click.secho(f"Baking with effective parameters:")
    click.secho(
        tabulate(
            sorted(metadata.items(), key=lambda k: k[0].lower()),
            headers=["Key", "Value"],
            tablefmt="grid",
        ),
        fg="yellow",
    )

    metadata_str = "\n".join(
        map(
            lambda k: f"{k[0]}={k[1]}",
            sorted(metadata.items(), key=lambda k: k[0].lower()),
        )
    )
    Commands.invoke(
        ctx,
        "reload",
        additional_config_raw=metadata_str,
        no_update_images=no_update_images,
    )
    output_env_file = customs_dir() / "{project_name}.env"
    output_env_file.write_text(
        "\n".join(
            map(
                lambda k: f"{k[0]}={k[1]}",
                sorted(
                    metadata.items(),
                    key=lambda x: x[0].lower(),
                ),
            )
        )
    )

    tips = [
        "-------------------------------------",
        "How to deploy image to AWS/Kubernetes/Artefacts",
        "-------------------------------------",
        "",
        "1. All in one container: odoo web service, odoo cronjobs, odoo queuejobs",
        """
        odoo bake ODOO_QUEUEJOBS_CRON_IN_ONE_CONTAINER=1
        """,
        "",
        "2. Correctly setup proxy regarding longpolling/websocket:",
        """
        * Odoo web service exposes port 8069
        * On port 8072 either longpolling or websocket is running
        * the path /longpolling  or /websocket (since V16) must point to that service
        * either setup your own nginx or use the proxy container
        """,
        "3. a new database is not initialized automatically - just take an existing dump or make a new dump locally",
        """
        (locally:)
        * odoo -f db reset
        * odoo update
        * odoo backup odoo-db <path to a file>
        * odoo down -v
        """,
        "",
        "4. Odoo needs an own file store to store attachments and sessions; it must be a mapped folder:",
        """
        services:
          odoo:
            volumes:
              - {volume dir}:/opt/files
                """,
        "5. Upload to registry",
        """
          * odoo setting HUB_URL=registry.url:433/<path>
          * odoo setting DOCKER_IMAGE_TAG=latest
          * odoo registry push
        """,
        "6. Reduce amount of images",
        """
          * odoo setting RUN_POSTGRES=0
          * odoo setting RUN_CRONJOBS=0
        """,
        "7. Setting up connection to database and other settings",
    ]
    for tip in tips:
        click.secho(tip, fg="green")

    for config in WHITELIST_PROPS:
        click.secho(f"\todoo setting {config}", fg="green")


def _get_metadata(ctx, config):
    import yaml

    content = yaml.safe_load(config.files["docker_compose"].read_text())
    all_envs = content["services"]["odoo"]["environment"]
    res = {}
    for key in all_envs.keys():
        if key in WHITELIST_PROPS:
            res[key] = all_envs[key]
    return res
