import sys


def force_utf8_output():
    """Force l'UTF-8 sur stdout/stderr.
    Sur une console Windows non-UTF-8 (cp1252), l'affichage de caractères comme
    "✓" ou "→" lève sinon une UnicodeEncodeError.
    Doit être appelé avant tout import qui affiche quelque chose.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
