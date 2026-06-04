import click

from panoptic.main import start


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Panoptic CLI — no subcommand launches the server."""
    if ctx.invoked_subcommand is None:
        start()


if __name__ == '__main__':
    cli()
