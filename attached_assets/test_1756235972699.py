#!/usr/bin/env python3
# tools/netbox_to_diagram.py
"""
Standalone, stdlib-only script to produce a hierarchical network diagram (SVG + DOT)
from a NetBox CSV export. Works on Python 3.6+ and handles both
- Connections exports (A Device / B Device)
- Interfaces exports (Device, Link Peers)
"""

from __future__ import print_function
import sys
import csv
import re
import argparse
from collections import defaultdict, deque
from pathlib import Path

# -------------------------
# Utilities (no dataclasses)
# -------------------------
def normalize_device_token(token):
    """Extract the device token from a raw Link-Peers-like string.

    Examples handled:
      "SW-01(12:12:12:12:12) > 1"
      "SW-01 (12:12:12:12:12) > 1"
      "server-01:eth0"
      "SER-WRS-01"
    Return the left-most alphanumeric/hyphen/underscore token.
    """
    if not token:
        return ""
    t = token.strip()
    m = re.match(r"^\s*([A-Za-z0-9_\-]+)", t)
    if m:
        return m.group(1)
    return t

def classify_node(name):
    ln = name.lower()
    # switches: sw- prefix (or sw<digit> variants)
    if ln.startswith("sw-") or (ln.startswith("sw") and len(ln) > 2 and ln[2].isdigit()):
        return "switch"
    if "wss" in ln or ln.startswith("but-wss") or ln.startswith("wss"):
        return "workstation"
    if ln.startswith("but-tool") or ln.startswith("ser-") or "tool" in ln:
        return "server"
    return "other"

# -------------------------
# CSV parsing
# -------------------------
def sniff_device_columns(headers):
    lowered = [h.strip().lower() for h in headers]
    a_idx = None
    b_idx = None
    for i, h in enumerate(lowered):
        if h in ("a device", "a_device", "device a", "device_a", "a device name"):
            a_idx = i
            break
    for i, h in enumerate(lowered):
        if h in ("b device", "b_device", "device b", "device_b", "b device name"):
            b_idx = i
            break
    if a_idx is not None and b_idx is not None:
        return a_idx, b_idx
    nonempty = [i for i, h in enumerate(headers) if h.strip()]
    if len(nonempty) >= 2:
        return nonempty[0], nonempty[1]
    return 0, 1

def read_edges(csv_path):
    nodes = set()
    edges = set()  # store sorted tuple (a,b)

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        # Detect Interfaces export with Device + Link Peers
        if any(h.lower() == "device" for h in headers) and any(h.lower() == "link peers" for h in headers):
            for row in reader:
                a_raw = row.get("Device") or row.get("device") or ""
                b_raw = row.get("Link Peers") or row.get("link peers") or ""
                if not a_raw or not b_raw:
                    continue
                a = normalize_device_token(a_raw)
                b = normalize_device_token(b_raw)
                if not a or not b or a == b:
                    continue
                nodes.add(a)
                nodes.add(b)
                edges.add(tuple(sorted((a, b))))
        else:
            # fallback to connection-style CSV
            a_idx, b_idx = sniff_device_columns(headers)
            try:
                a_key = headers[a_idx]
                b_key = headers[b_idx]
            except Exception:
                a_key = headers[0] if headers else None
                b_key = headers[1] if len(headers) > 1 else None
            if a_key is None or b_key is None:
                return nodes, []
            for row in reader:
                a_raw = row.get(a_key, "")
                b_raw = row.get(b_key, "")
                if not a_raw or not b_raw:
                    continue
                a = normalize_device_token(a_raw)
                b = normalize_device_token(b_raw)
                if not a or not b or a == b:
                    continue
                nodes.add(a)
                nodes.add(b)
                edges.add(tuple(sorted((a, b))))

    edges_list = [{"a": e[0], "b": e[1]} for e in sorted(edges)]
    return nodes, edges_list

# -------------------------
# Layering & layout
# -------------------------
def assign_layers(nodes, edges):
    adj = {n: set() for n in nodes}
    for e in edges:
        adj[e["a"]].add(e["b"])
        adj[e["b"]].add(e["a"])

    types = {n: classify_node(n) for n in nodes}
    seeds = [n for n, t in types.items() if t == "server"]
    if not seeds:
        seeds = [n for n, t in types.items() if t == "switch"]
    if not seeds and nodes:
        seeds = [next(iter(nodes))]

    dist = {n: float("inf") for n in nodes}
    q = deque()
    for s in seeds:
        dist[s] = 0
        q.append(s)

    while q:
        u = q.popleft()
        for v in adj.get(u, []):
            if dist[v] > dist[u] + 1:
                dist[v] = dist[u] + 1
                q.append(v)

    finite = [d for d in dist.values() if d != float("inf")]
    min_d = min(finite) if finite else 0
    for n in nodes:
        if dist[n] == float("inf"):
            dist[n] = 0
        else:
            dist[n] = int(dist[n] - min_d)

    max_d = max(dist.values()) if dist else 0
    for n, t in types.items():
        if t == "workstation":
            dist[n] = max(dist[n], max_d)

    layers = sorted(set(dist.values()))
    mapping = {old: i for i, old in enumerate(layers)}
    for n in list(dist.keys()):
        dist[n] = mapping[dist[n]]
    return dist

def layout_positions(layers_map, nodes):
    per_layer = defaultdict(list)
    for n in nodes:
        per_layer[layers_map[n]].append(n)
    for k in per_layer:
        per_layer[k].sort(key=lambda x: (classify_node(x), x))

    ordered = [per_layer[i] for i in sorted(per_layer.keys())]
    margin_x = 80; margin_y = 80
    step_x = 240; step_y = 110
    box_w = 180; box_h = 44

    positions = {}
    for ix, col in enumerate(ordered):
        for iy, n in enumerate(col):
            x = margin_x + ix * step_x
            y = margin_y + iy * step_y
            positions[n] = (x, y)

    canvas_w = margin_x * 2 + max(0, len(ordered) - 1) * step_x + box_w
    canvas_h = margin_y * 2 + (max((len(c) for c in ordered), default=1) - 1) * step_y + box_h
    return positions, ordered, canvas_w, canvas_h, box_w, box_h

# -------------------------
# SVG rendering
# -------------------------
def svg_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def render_svg(out_path, nodes, edges, layers_map):
    pos, ordered_layers, w, h, box_w, box_h = layout_positions(layers_map, nodes)
    header = '<?xml version="1.0" encoding="UTF-8"?>\\n'
    header += '<svg xmlns="http://www.w3.org/2000/svg" version="1.1"'
    header += ' width="{w}" height="{h}" viewBox="0 0 {w} {h}">\\n'.format(w=w, h=h)
    header += '<style>text{font-family:Arial,Helvetica,sans-serif;font-size:12px;fill:#0f172a} .node{rx:8;ry:8;stroke:#0f172a;stroke-width:1}</style>\\n'

    parts = [header]
    parts.append('<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>')
    parts.append('<text x="16" y="20">Network diagram</text>')

    for e in edges:
        a = e["a"]; b = e["b"]
        if a not in pos or b not in pos:
            continue
        x1, y1 = pos[a]; x2, y2 = pos[b]
        x1c = x1 + box_w / 2; y1c = y1 + box_h / 2
        x2c = x2 + box_w / 2; y2c = y2 + box_h / 2
        parts.append('<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" stroke="#475569" stroke-width="1.2"/>'.format(x1c, y1c, x2c, y2c))

    color_map = {"server": "#dbeafe", "switch": "#dcfce7", "workstation": "#fde68a", "other": "#e5e7eb"}
    for n in sorted(nodes):
        x, y = pos[n]; t = classify_node(n); fill = color_map.get(t, "#e5e7eb")
        parts.append('<rect class="node" x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" fill="{}"/>'.format(x, y, box_w, box_h, fill))
        parts.append('<text x="{:.1f}" y="{:.1f}">{}</text>'.format(x + 8, y + box_h / 2 + 5, svg_escape(n)))

    # legend
    lx = w - 220; ly = 20
    parts.append('<g class="legend">')
    parts.append('<text x="{}" y="{}">Legend</text>'.format(lx, ly))
    i = 0
    for k, c in [("server", "#dbeafe"), ("switch", "#dcfce7"), ("workstation", "#fde68a"), ("other", "#e5e7eb")]:
        yy = ly + 16 + i * 22
        parts.append('<rect x="{}" y="{}" width="14" height="14" fill="{}" rx="4" ry="4"/>'.format(lx, yy, c))
        parts.append('<text x="{}" y="{}">{}</text>'.format(lx + 20, yy + 12, k))
        i += 1
    parts.append("</g>")

    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path

# -------------------------
# DOT export (optional)
# -------------------------
def render_dot(out_path, nodes, edges, layers_map):
    lines = ["graph network {", "  overlap=false;", "  splines=true;"]
    for n in sorted(nodes):
        t = classify_node(n)
        if t == "switch":
            lines.append('  "%s" [shape=box, style=filled, fillcolor=lightblue];' % n)
        elif t == "server":
            lines.append('  "%s" [shape=component, style=filled, fillcolor=lightgreen];' % n)
        elif t == "workstation":
            lines.append('  "%s" [shape=ellipse, style=filled, fillcolor=gold];' % n)
        else:
            lines.append('  "%s" [shape=ellipse];' % n)
    for e in edges:
        lines.append('  "%s" -- "%s";' % (e["a"], e["b"]))
    lines.append("}")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path

# -------------------------
# CLI
# -------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(description="NetBox CSV -> hierarchical SVG diagram")
    p.add_argument("csv_file", type=Path)
    p.add_argument("-o", "--output", default=None, help="Output prefix (default: csv basename)")
    p.add_argument("--no-dot", action="store_true", help="Do not write DOT file")
    return p.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    csv_path = args.csv_file
    if not csv_path.exists():
        print("ERR: CSV not found:", csv_path, file=sys.stderr)
        return 2

    out_prefix = Path(args.output) if args.output else csv_path.with_suffix("")

    nodes, edges = read_edges(csv_path)
    if not edges:
        print("WARN: No edges parsed from CSV. No diagram produced.", file=sys.stderr)
        return 1

    layers_map = assign_layers(nodes, edges)
    svg_path = render_svg(Path(str(out_prefix) + ".svg"), nodes, edges, layers_map)
    print("Wrote:", svg_path)

    if not args.no_dot:
        dot_path = render_dot(Path(str(out_prefix) + ".dot"), nodes, edges, layers_map)
        print("Wrote:", dot_path)

    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
