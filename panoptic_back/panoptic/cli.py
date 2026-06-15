import asyncio
import sys

import click
from typing import Optional

from panoptic.main import start as start_api
from panoptic.core.panoptic import Panoptic
from panoptic.models import PluginType

# Instance globale de Panoptic
panoptic = Panoptic()

PLUGIN_TYPE_CHOICES = [pt.value for pt in PluginType]


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


@click.group(invoke_without_command=True)
@click.option('--test', is_flag=True, help='Start with temp directory')
@click.option('--install', is_flag=True, help='Install vision plugin')
@click.option('--dry', is_flag=True, help='Run setup then exit without starting the server (CI checks)')
@click.pass_context
def cli(ctx, test, install, dry):
    """Panoptic CLI

    Sans arguments, lance l'API Panoptic.
    Avec des commandes, utilise le CLI.
    """
    _force_utf8_output()
    # Si aucune sous-commande n'est invoquée, lancer l'API
    if ctx.invoked_subcommand is None:
        click.echo("Lancement de Panoptic...")
        if test:
            click.echo("Lancement de l'API en mode test")
        if install:
            click.echo("Installation du plugin vision par défaut...")
        if dry:
            click.echo("Mode dry : configuration puis arrêt sans démarrer le serveur")
        start_api(test=True if test else False, install=True if install else False, dry=True if dry else False)


@cli.group()
def plugins():
    """Gestion des plugins Panoptic"""
    pass


@plugins.command()
@click.argument('name')
@click.option('--source', '-s', help='Source du plugin (URL, path, etc.)')
@click.option('--type', '-t', 'plugin_type',
              type=click.Choice(PLUGIN_TYPE_CHOICES, case_sensitive=False),
              help='Type de plugin')
def add(name: str, source: Optional[str], plugin_type: Optional[str]):
    panoptic.start()
    """Ajouter un plugin

    Exemples:
        panoptic plugins add vision  # Installe le plugin vision par défaut
        panoptic plugins add mon-plugin --source https://... --type text
    """
    # Cas spécial : plugin vision par défaut
    if name.lower() == 'vision' and not source and not plugin_type:
        click.echo("Installation du plugin vision par défaut...")
        asyncio.run(panoptic.add_plugin(
            name='PanopticVision',
            source='panopticml',
            ptype=PluginType.pip
        ))
        click.secho("✓ Plugin vision installé avec succès!", fg='green')
        panoptic.close()
        return

    # Validation pour les autres cas
    if not source:
        raise click.UsageError("L'option --source est requise (sauf pour 'vision')")

    if not plugin_type:
        raise click.UsageError("L'option --type est requise (sauf pour 'vision')")

    # Convertir la string en PluginType enum
    try:
        plugin_type_enum = PluginType(plugin_type.lower())
    except ValueError:
        raise click.BadParameter(f"Type invalide. Choix: {', '.join(PLUGIN_TYPE_CHOICES)}")

    asyncio.run(panoptic.add_plugin(name, source, plugin_type_enum))
    click.secho(f"✓ Plugin {name} ajouté avec succès!", fg='green')
    panoptic.close()


@plugins.command()
def list():
    panoptic.start()
    for plugin in panoptic.get_plugin_paths():
        click.secho(f"Name: {plugin.name}", fg='green')
        click.secho(f"Type: {plugin.type}", fg='green')
        click.secho(f"Source: {plugin.source}", fg='green')
        click.secho("==================")
    panoptic.close()

if __name__ == '__main__':
    cli()