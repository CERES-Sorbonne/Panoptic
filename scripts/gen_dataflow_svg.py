#!/usr/bin/env python3
"""Generate a single big poster SVG of Panoptic's full data flow."""
from html import escape

W, H = 2640, 980

# ---- palette -------------------------------------------------------------
LANE = {
    'fs':       ('#FBF6EC', '#B8860B'),
    'db':       ('#FFF7ED', '#C2410C'),
    'backend':  ('#EEF4FB', '#1E3A5F'),
    'channel':  ('#F5F0FF', '#5B21B6'),
    'frontend': ('#F0FBF3', '#166534'),
    'ui':       ('#FDF2F8', '#9D174D'),
}
BOXFILL = {
    'fs': '#FFFFFF', 'db': '#FFEFD9', 'backend': '#FFFFFF',
    'channel': '#FFFFFF', 'frontend': '#FFFFFF', 'ui': '#FFFFFF',
}
FLOW = {
    'ingest':   '#EA8A2B',
    'load':     '#2563EB',
    'realtime': '#16A34A',
    'write':    '#DB2777',
    'internal': '#7C8AA0',
    'media':    '#7C3AED',
}

boxes = {}   # id -> (x,y,w,h,cat)
svg = []

def box(id_, x, y, w, h, cat, lines, bold_first=False, fs=17):
    boxes[id_] = (x, y, w, h, cat)
    fill = BOXFILL[cat]; stroke = LANE[cat][1]
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>')
    cx = x + w / 2
    n = len(lines)
    lh = fs + 5
    y0 = y + h / 2 - (n - 1) * lh / 2
    for i, ln in enumerate(lines):
        weight = 'bold' if (bold_first and i == 0) else 'normal'
        size = fs + 1 if (bold_first and i == 0) else fs
        svg.append(f'<text x="{cx}" y="{y0 + i*lh}" font-size="{size}" '
                   f'font-weight="{weight}" text-anchor="middle" '
                   f'dominant-baseline="middle" fill="#1f2937" '
                   f'font-family="Helvetica,Arial,sans-serif">{escape(ln)}</text>')

def anchor(id_, side, frac=0.5):
    x, y, w, h, _ = boxes[id_]
    if side == 'l': return (x, y + h*frac)
    if side == 'r': return (x + w, y + h*frac)
    if side == 't': return (x + w*frac, y)
    if side == 'b': return (x + w*frac, y + h)

def arrow(a, aside, b, bside, flow, bidir=False, afrac=0.5, bfrac=0.5, width=2.6, dash=False):
    x1, y1 = anchor(a, aside, afrac)
    x2, y2 = anchor(b, bside, bfrac)
    c = FLOW[flow]
    d = f' stroke-dasharray="7 5"' if dash else ''
    start = f'url(#h-{flow})' if bidir else ''
    svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
               f'stroke="{c}" stroke-width="{width}"{d} '
               f'marker-end="url(#h-{flow})" '
               + (f'marker-start="{start}"' if bidir else '') + '/>')

def lane(x, w, title, cat, y=120, h=720):
    fill, stroke = LANE[cat]
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="2" opacity="0.95"/>')
    svg.append(f'<text x="{x + w/2}" y="{y+34}" font-size="23" font-weight="bold" '
               f'text-anchor="middle" fill="{stroke}" '
               f'font-family="Helvetica,Arial,sans-serif">{escape(title)}</text>')

# ---- header --------------------------------------------------------------
svg.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#F8FAFC"/>')
svg.append(f'<text x="{W/2}" y="58" font-size="34" font-weight="bold" '
           f'text-anchor="middle" fill="#0f172a" '
           f'font-family="Helvetica,Arial,sans-serif">Panoptic — Full Data Flow '
           f'(disk → backend → channels → frontend → UI)</text>')

# ---- lanes ---------------------------------------------------------------
lane(40,  290, 'Filesystem',                'fs')
lane(360, 320, 'SQLite databases',          'db')
lane(710, 650, 'Backend · FastAPI + Socket.IO', 'backend')
lane(1390, 250, 'Channels',                 'channel')
lane(1670, 510, 'Frontend stores · Pinia',  'frontend')
lane(2210, 390, 'View pipeline & UI',       'ui')

# ---- Filesystem ----------------------------------------------------------
box('A_IMG',   70, 200, 240, 85, 'fs', ['Original images', '(jpg / png / …)'], True)
box('A_ATLAS', 70, 360, 240, 85, 'fs', ['atlas/*.png', 'thumbnail sheets'], True)
box('A_PLUG',  70, 520, 240, 85, 'fs', ['plugins/ dir', '(installed code)'], True)

# ---- Databases -----------------------------------------------------------
box('B_GLOB',  385, 175, 270, 85, 'db', ['panoptic.db (global)', 'projects · plugins · users'], True)
box('B_PROJ',  385, 300, 270, 95, 'db', ['project.db', 'config · id-allocators', 'tabs · UI state'], True)
box('B_DATA',  385, 435, 270, 120,'db', ['data.db', 'properties · tags · instances', 'files · folders · values', '+ commit log + SEQUENCE'], True)
box('B_MEDIA', 385, 600, 270, 105,'db', ['media.db', 'thumbnails (blobs) · vectors', 'atlases · maps'], True)

# ---- Backend (two subcolumns) -------------------------------------------
# left subcol
box('C_PAN',    730, 175, 290, 70, 'backend', ['Panoptic', 'loaded-projects registry'], True)
box('C_PROJ',   730, 270, 290, 80, 'backend', ['Project', 'read / write facade'], True)
box('C_RW',     730, 375, 290, 70, 'backend', ['DataReader / DataWriter'], True)
box('C_MEDIADB',730, 470, 290, 60, 'backend', ['MediaDB'], True)
box('C_TASK',   730, 560, 290, 80, 'backend', ['TaskManager', 'worker thread + multiproc'], True)
box('C_INGEST', 730, 670, 290, 80, 'backend', ['ImportFolder / Atlas tasks', 'scan → sha1 → resize'], True)
# right subcol
box('C_ROUTES', 1050, 175, 290, 90, 'backend', ['REST routes', 'panoptic_router', 'project_router'], True)
box('C_SERVER', 1050, 290, 290, 95, 'backend', ['PanopticServer', 'socket events', '+ broadcasts'], True)
box('C_WATCH',  1050, 420, 290, 70, 'backend', ['DbWatcher', 'sequence poll (100 ms)'], True)
box('C_PLUG',   1050, 520, 290, 75, 'backend', ['Plugins', 'PluginProjectInterface'], True)

# ---- Channels ------------------------------------------------------------
box('D_REST',   1410, 210, 250, 100, 'channel', ['REST (HTTP)', 'axios projectApi', '/commit · /init_state'], True)
box('D_STREAM', 1410, 380, 250, 100, 'channel', ['NDJSON streams', '/instances/base', '/column · /delta'], True)
box('D_WS',     1410, 550, 250, 100, 'channel', ['WebSocket', 'Socket.IO push', 'db_update · tasks'], True)

# ---- Frontend stores (two subcolumns) -----------------------------------
box('E_SOCK', 1690, 180, 210, 70, 'frontend', ['socketStore'], True)
box('E_PAN',  1950, 180, 210, 70, 'frontend', ['panopticStore'], True)
box('E_PROJ', 1950, 270, 210, 65, 'frontend', ['projectStore'], True)
box('E_DATA', 1690, 280, 210, 95, 'frontend', ['dataStore', '(orchestrator)'], True)
box('E_COL',  1690, 410, 470, 105,'frontend', ['columnStore', 'typed-array columnar engine', 'slotMap · masks · columns'], True)
box('E_INST', 1690, 545, 210, 65, 'frontend', ['instanceStore'], True)
box('E_MEDIA',1950, 545, 210, 65, 'frontend', ['mediaStore'], True)
box('E_TAB',  1690, 635, 210, 60, 'frontend', ['tabStore'], True)

# ---- Pipeline & UI -------------------------------------------------------
box('F_TAB',  2235, 195, 300, 70, 'ui', ['TabManager', 'collections · views'], True)
box('F_CM',   2235, 295, 300, 70, 'ui', ['CollectionManager'], True)
box('F_PIPE', 2235, 395, 300, 90, 'ui', ['Filter → Sort → Group', '(Int32Array slots)'], True)
box('F_UI',   2235, 515, 300, 95, 'ui', ['Views', 'tree · grid · map · graph'], True)
box('F_SEL',  2235, 640, 300, 60, 'ui', ['selection / user edits'], True)

# ---- arrows --------------------------------------------------------------
# Ingestion (orange)
arrow('A_IMG', 'r', 'C_INGEST', 'l', 'ingest', afrac=0.5, bfrac=0.25)
arrow('C_TASK', 'b', 'C_INGEST', 't', 'internal', afrac=0.5, bfrac=0.5)
arrow('C_INGEST', 'l', 'B_DATA', 'r', 'ingest', afrac=0.6, bfrac=0.75)
arrow('C_INGEST', 'l', 'B_MEDIA', 'r', 'ingest', afrac=0.75, bfrac=0.4)
arrow('C_INGEST', 'l', 'A_ATLAS', 'r', 'ingest', afrac=0.4, bfrac=0.5)

# Backend <-> DB (internal, bidir)
arrow('B_GLOB', 'r', 'C_PAN', 'l', 'internal', bidir=True)
arrow('B_PROJ', 'r', 'C_PROJ', 'l', 'internal', bidir=True, bfrac=0.35)
arrow('B_DATA', 'r', 'C_RW', 'l', 'internal', bidir=True, afrac=0.3)
arrow('B_MEDIA', 'r', 'C_MEDIADB', 'l', 'internal', bidir=True, afrac=0.3)

# Backend internal
arrow('C_PROJ', 'b', 'C_RW', 't', 'internal', afrac=0.35)
arrow('C_PROJ', 'b', 'C_MEDIADB', 't', 'internal', afrac=0.6)
arrow('C_PROJ', 'b', 'C_TASK', 't', 'internal', afrac=0.8)
arrow('C_PLUG', 'l', 'C_RW', 'r', 'internal', afrac=0.3, bfrac=0.7)
arrow('C_PLUG', 'l', 'C_MEDIADB', 'r', 'internal', afrac=0.6)

# Change detection -> server (realtime green)
arrow('C_PROJ', 'r', 'C_SERVER', 'l', 'realtime', afrac=0.6, bfrac=0.3)
arrow('C_TASK', 'r', 'C_SERVER', 'l', 'realtime', afrac=0.2, bfrac=0.85)
arrow('B_DATA', 't', 'C_WATCH', 'l', 'realtime', afrac=0.9, bfrac=0.5, dash=True)
arrow('C_WATCH', 't', 'C_SERVER', 'b', 'realtime', afrac=0.5, bfrac=0.5)

# Backend <-> channels
arrow('C_ROUTES', 'r', 'D_REST', 'l', 'internal', bidir=True, bfrac=0.5)
arrow('C_ROUTES', 'r', 'D_STREAM', 'l', 'load', afrac=0.8, bfrac=0.3)
arrow('C_SERVER', 'r', 'D_WS', 'l', 'realtime', bidir=True)

# Channels <-> frontend
arrow('D_REST', 'r', 'E_DATA', 'l', 'write', bidir=True, bfrac=0.4)
arrow('D_REST', 'r', 'E_PAN', 'l', 'internal', afrac=0.25, bfrac=0.5, dash=True)
arrow('D_REST', 'r', 'E_MEDIA', 'l', 'media', afrac=0.8, bfrac=0.5)
arrow('D_STREAM', 'r', 'E_COL', 'l', 'load', bfrac=0.3)
arrow('D_WS', 'r', 'E_SOCK', 'l', 'realtime', bfrac=0.5)

# Frontend internal
arrow('E_SOCK', 'b', 'E_DATA', 't', 'realtime', afrac=0.5, bfrac=0.4)
arrow('E_DATA', 'b', 'E_COL', 't', 'load', afrac=0.5, bfrac=0.15)
arrow('E_DATA', 'b', 'E_INST', 't', 'internal', afrac=0.3)
arrow('E_DATA', 'b', 'E_TAB', 't', 'internal', afrac=0.15, bfrac=0.3)
arrow('E_PAN', 'b', 'E_PROJ', 't', 'internal')

# Pipeline
arrow('E_COL', 'r', 'F_PIPE', 'l', 'load', afrac=0.5, bfrac=0.6)
arrow('E_DATA', 'r', 'F_CM', 'l', 'realtime', afrac=0.2, bfrac=0.35)
arrow('E_TAB', 'r', 'F_TAB', 'l', 'internal', afrac=0.5, bfrac=0.7, dash=True)
arrow('F_TAB', 'b', 'F_CM', 't', 'internal')
arrow('F_CM', 'b', 'F_PIPE', 't', 'internal')
arrow('F_PIPE', 'b', 'F_UI', 't', 'internal')
arrow('F_UI', 'b', 'F_SEL', 't', 'internal')
# selection + edits back
arrow('F_SEL', 'l', 'E_COL', 'r', 'realtime', afrac=0.5, bfrac=0.75)
arrow('F_UI', 'l', 'E_DATA', 'r', 'write', afrac=0.5, bfrac=0.7)

# ---- legend --------------------------------------------------------------
ly = 880
legend = [
    ('ingest',   'Ingestion (files → DB)'),
    ('load',     'Initial load / column streams'),
    ('realtime', 'Realtime sync (sequence → delta)'),
    ('write',    'Mutations / commits'),
    ('media',    'Image & media bytes'),
    ('internal', 'Internal / registry / bidirectional'),
]
svg.append(f'<rect x="40" y="{ly-25}" width="2560" height="90" rx="12" '
           f'fill="#FFFFFF" stroke="#cbd5e1" stroke-width="1.5"/>')
lx = 80
for flow, label in legend:
    c = FLOW[flow]
    svg.append(f'<line x1="{lx}" y1="{ly+20}" x2="{lx+55}" y2="{ly+20}" '
               f'stroke="{c}" stroke-width="4" marker-end="url(#h-{flow})"/>')
    svg.append(f'<text x="{lx+70}" y="{ly+25}" font-size="19" fill="#1f2937" '
               f'font-family="Helvetica,Arial,sans-serif">{escape(label)}</text>')
    lx += 430

# ---- markers -------------------------------------------------------------
defs = ['<defs>']
for flow, c in FLOW.items():
    defs.append(f'<marker id="h-{flow}" markerWidth="11" markerHeight="11" '
                f'refX="9" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
                f'<path d="M0,0 L10,4 L0,8 Z" fill="{c}"/></marker>')
defs.append('</defs>')

# Square element with a wide viewBox: qlmanage fits the whole width into a
# square thumbnail without cropping (content letterboxed top/bottom, trimmed later).
out = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{W}" '
       f'viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">'
       + ''.join(defs) + ''.join(svg) + '</svg>')

with open('DATAFLOW.svg', 'w') as f:
    f.write(out)
print('wrote DATAFLOW.svg', len(out), 'bytes')
