#!/usr/bin/env python3
"""Generate reproducible geometry facts from a labeled UMAP PNG.

The color map is read from the supplied legend mapping. Identity labels are
never read by this tool; it only measures colored regions and their geometry.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image


def _load_shared():
    local = Path(__file__).resolve().parent
    for parent in (local, *local.parents):
        shared = parent / "shared" / "sc-annotation-evidence-core"
        if (shared / "umap_facts.py").is_file():
            if str(shared) not in sys.path:
                sys.path.insert(0, str(shared))
            import umap_facts as module
            return module
    raise RuntimeError("Shared UMAP facts module not found")


_FACTS = _load_shared()


def _rgb(value):
    if isinstance(value, list) and len(value) == 3:
        return tuple(int(item) for item in value)
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        if len(parts) == 3:
            return tuple(int(item) for item in parts)
    raise ValueError(f"Invalid RGB color: {value!r}")


def _box_distance(left, right):
    lx0, ly0, lx1, ly1 = left
    rx0, ry0, rx1, ry1 = right
    dx = max(rx0 - lx1, lx0 - rx1, 0)
    dy = max(ry0 - ly1, ly0 - ry1, 0)
    return math.hypot(dx, dy)


def _largest_component(points):
    remaining = set(points)
    best = []
    while remaining:
        seed = remaining.pop()
        queue = [seed]
        component = [seed]
        while queue:
            x, y = queue.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    neighbor = (x + dx, y + dy)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)
                        component.append(neighbor)
        if len(component) > len(best):
            best = component
    return best


def generate(image_path, color_map, plot_box, nearest_k=5, adjacency_px=24):
    image = Image.open(image_path).convert("RGB")
    x0, y0, x1, y1 = plot_box
    if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
        raise ValueError(f"plot_box is outside image bounds: {plot_box} vs {image.size}")
    pixels = image.load()
    regions = {}
    for cluster, color in sorted(color_map.items()):
        rgb = _rgb(color)
        points = [
            (x, y)
            for y in range(y0, y1)
            for x in range(x0, x1)
            if pixels[x, y] == rgb
        ]
        if not points:
            raise ValueError(f"Cluster {cluster} color {rgb} was not found in plot_box")
        component = _largest_component(points)
        xs = [item[0] for item in component]
        ys = [item[1] for item in component]
        bbox = [min(xs), min(ys), max(xs), max(ys)]
        regions[str(cluster)] = {
            "component_id": f"cluster_{cluster}_largest_component",
            "pixel_count": len(component),
            "centroid": [round(sum(xs) / len(xs), 4), round(sum(ys) / len(ys), 4)],
            "bbox": bbox,
        }
    for cluster, region in regions.items():
        centroid = region["centroid"]
        distances = sorted(
            (
                math.dist(centroid, other["centroid"]),
                other_cluster,
            )
            for other_cluster, other in regions.items()
            if other_cluster != cluster
        )
        region["nearest_clusters"] = [item[1] for item in distances[:nearest_k]]
        region["adjacent_clusters"] = [
            other_cluster
            for other_cluster, other in regions.items()
            if other_cluster != cluster and _box_distance(region["bbox"], other["bbox"]) <= adjacency_px
        ]
    facts = {
        "schema_version": _FACTS.FACTS_SCHEMA_VERSION,
        "generated_by": _FACTS.GENERATOR_ID,
        "source_image_sha256": _FACTS.sha256_file(image_path),
        "image_size": [image.width, image.height],
        "plot_box": list(plot_box),
        "cluster_colors": {str(k): list(_rgb(v)) for k, v in sorted(color_map.items())},
        "nearest_k": nearest_k,
        "adjacency_px": adjacency_px,
        "clusters": regions,
    }
    facts["facts_sha256"] = _FACTS.canonical_sha256(facts)
    return facts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--cluster-colors", required=True, help="JSON object mapping cluster IDs to RGB triplets")
    parser.add_argument("--plot-box", required=True, help="x0,y0,x1,y1 in source-image pixels")
    parser.add_argument("--output", required=True)
    parser.add_argument("--nearest-k", type=int, default=5)
    parser.add_argument("--adjacency-px", type=float, default=24)
    args = parser.parse_args()
    colors = json.loads(Path(args.cluster_colors).read_text(encoding="utf-8"))
    box = tuple(int(item.strip()) for item in args.plot_box.split(","))
    if len(box) != 4:
        raise ValueError("--plot-box must contain four comma-separated integers")
    facts = generate(args.image, colors, box, args.nearest_k, args.adjacency_px)
    Path(args.output).write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "pass", "output": args.output, "facts_sha256": facts["facts_sha256"]}))


if __name__ == "__main__":
    main()
