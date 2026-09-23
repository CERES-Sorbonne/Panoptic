import sys

from panoptic.macos_openmp import ensure_single_openmp
ensure_single_openmp()

import click

from panoptic.core.panoptic.panoptic import Panoptic
from panoptic.core.plugin.plugin_installer import SOURCE_GIT, SOURCE_PATH, SOURCE_PIP
from panoptic.main import get_db_path, start

SOURCE_CHOICES = [SOURCE_PIP, SOURCE_GIT, SOURCE_PATH]

# plugin vision par défaut : même nom / source que celui enregistré par le front (FirstModal)
VISION_NAME = 'PanopticML'
VISION_SOURCE = 'panopticml'


def _force_utf8_output():
    """Force l'UTF-8 sur stdout/stderr.
    Sur une console Windows non-UTF-8 (cp1252), l'affichage de caractères comme
    "✓" lève sinon une UnicodeEncodeError.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _open_panoptic() -> Panoptic:
    panoptic = Panoptic(get_db_path())
    panoptic.start()
    return panoptic


@click.group(invoke_without_command=True)
@click.option('--dry', is_flag=True, help='Run setup then exit without starting the server (CI checks)')
@click.pass_context
def cli(ctx, dry):
    """Panoptic CLI

    Sans arguments, lance l'API Panoptic.
    Avec des commandes, utilise le CLI.
    """
    _force_utf8_output()
    if ctx.invoked_subcommand is not None:
        return
    if dry:
        click.echo("Mode dry : configuration puis arrêt sans démarrer le serveur")
        _open_panoptic().close()
        click.secho("✓ Panoptic est correctement installé", fg='green')
        return
    click.echo("Lancement de Panoptic...")
    start()


@cli.group()
def plugins():
    """Gestion des plugins Panoptic"""
    pass


@plugins.command()
@click.argument('name')
@click.option('--source', '-s', help='Source du plugin (nom pip, URL git, chemin local)')
@click.option('--type', '-t', 'source_type',
              type=click.Choice(SOURCE_CHOICES, case_sensitive=False),
              help='Type de source')
def add(name: str, source: str | None, source_type: str | None):
    """Ajouter un plugin

    Exemples:
        panoptic plugins add vision  # Installe le plugin vision par défaut
        panoptic plugins add mon-plugin --source https://... --type git
    """
    # Cas spécial : plugin vision par défaut
    if name.lower() == 'vision' and not source and not source_type:
        name, source, source_type = VISION_NAME, VISION_SOURCE, SOURCE_PIP
    elif not source or not source_type:
        raise click.UsageError("Les options --source et --type sont requises (sauf pour 'vision')")

    panoptic = _open_panoptic()
    try:
        # idempotent : relancer l'installateur ne doit pas échouer si le plugin est déjà là
        # (y compris sous un autre nom, ex. "PanopticVision" importé d'une ancienne base)
        existing = next((p for p in panoptic.get_plugins()
                         if p.id == name or (p.source_type == source_type and p.source_path == source)), None)
        if existing:
            click.secho(f"✓ Plugin {existing.id} déjà installé", fg='green')
            return
        click.echo(f"Installation du plugin {name}...")
        panoptic.add_plugin(name, source, source_type.lower())
        click.secho(f"✓ Plugin {name} ajouté avec succès!", fg='green')
    finally:
        panoptic.close()


@plugins.command('list')
def list_plugins():
    """Lister les plugins installés"""
    panoptic = _open_panoptic()
    try:
        for plugin in panoptic.get_plugins():
            click.secho(f"Name: {plugin.id}", fg='green')
            click.secho(f"Type: {plugin.source_type}", fg='green')
            click.secho(f"Source: {plugin.source_path}", fg='green')
            click.secho("==================")
    finally:
        panoptic.close()


if __name__ == '__main__':
    cli()
