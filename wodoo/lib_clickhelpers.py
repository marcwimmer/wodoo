from . import click

if click:

    class AliasedGroup(click.Group):
        """
        Uses startswith to match command
        """

        def get_command(self, ctx, cmd_name):
            rv = click.Group.get_command(self, ctx, cmd_name)
            if rv is not None:
                return rv
            matches = list(
                filter(
                    lambda x: x[1].startswith(cmd_name),
                    map(
                        lambda y: (click.Group.get_command(self, ctx, y), y),
                        self.list_commands(ctx),
                    ),
                )
            )
            # search recursivley
            for _cmd_name in self.list_commands(ctx):
                cmd = click.Group.get_command(self, ctx, _cmd_name)
                if type(cmd) == type(self):
                    filtered = filter(
                        lambda cmd: cmd.startswith(cmd_name), cmd.list_commands(ctx)
                    )
                    matches += list(
                        map(
                            lambda cmd_name: (
                                cmd.get_command(ctx, cmd_name),
                                _cmd_name,
                            ),
                            filtered,
                        )
                    )

            if len(matches) > 1:
                # try to reduce to exact match
                try_matches = list(
                    filter(lambda match: match[0].name == cmd_name, matches)
                )
                if try_matches:
                    matches = try_matches

            if len(matches) == 1:
                cmd = matches[0][0]
                # print("Using command: {}.{}".format(self.name, cmd.name))
                return matches[0][0]
            elif len(matches) > 1:
                click.echo(
                    "Not unique command: {}\n\n".format(
                        "\n\t".join(x[1] + "/" + x[0].name for x in matches)
                    )
                )
            return None
