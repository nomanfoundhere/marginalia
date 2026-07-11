#!/usr/bin/env python3
"""Extract a transparent icon silhouette from a light generation canvas."""

import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter


def color_distance(pixel, background):
    return max(abs(pixel[i] - background[i]) for i in range(3))


def corner_background(image, sample=16):
    pixels = image.load()
    width, height = image.size
    values = []
    for x0, y0 in ((0, 0), (width - sample, 0), (0, height - sample), (width - sample, height - sample)):
        for y in range(y0, y0 + sample):
            for x in range(x0, x0 + sample):
                values.append(pixels[x, y][:3])
    return tuple(sorted(value[i] for value in values)[len(values) // 2] for i in range(3))


def edge_barrier(image, background, color_threshold, edge_threshold, radius):
    width, height = image.size
    gray = image.convert("L").load()
    pixels = image.load()
    edges = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            if color_distance(pixels[x, y], background) >= color_threshold:
                edges[y * width + x] = 1
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            gx = (
                gray[x + 1, y - 1]
                + 2 * gray[x + 1, y]
                + gray[x + 1, y + 1]
                - gray[x - 1, y - 1]
                - 2 * gray[x - 1, y]
                - gray[x - 1, y + 1]
            )
            gy = (
                gray[x - 1, y + 1]
                + 2 * gray[x, y + 1]
                + gray[x + 1, y + 1]
                - gray[x - 1, y - 1]
                - 2 * gray[x, y - 1]
                - gray[x + 1, y - 1]
            )
            if abs(gx) + abs(gy) >= edge_threshold:
                edges[y * width + x] = 1

    barrier = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            if not edges[y * width + x]:
                continue
            for ny in range(max(0, y - radius), min(height, y + radius + 1)):
                for nx in range(max(0, x - radius), min(width, x + radius + 1)):
                    barrier[ny * width + nx] = 1
    return barrier


def outside_mask(width, height, barrier):
    mask = bytearray(width * height)
    queue = deque()

    def add(x, y):
        index = y * width + x
        if mask[index] or barrier[index]:
            return
        mask[index] = 1
        queue.append((x, y))

    for x in range(width):
        add(x, 0)
        add(x, height - 1)
    for y in range(height):
        add(0, y)
        add(width - 1, y)

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1), (x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1), (x + 1, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                add(nx, ny)
    return mask


def extract(source, output, color_threshold, edge_threshold, edge_inset):
    image = Image.open(source).convert("RGBA")
    background = corner_background(image)
    barrier = edge_barrier(image, background, color_threshold, edge_threshold, 4)
    outside = outside_mask(*image.size, barrier)
    pixels = image.load()
    width, height = image.size

    for y in range(height):
        for x in range(width):
            index = y * width + x
            if not outside[index]:
                continue
            pixels[x, y] = (0, 0, 0, 0)

    if edge_inset:
        image.putalpha(image.getchannel("A").filter(ImageFilter.MinFilter(2 * edge_inset + 1)))

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(f"wrote {output} (background sampled as {background})")


def main():
    parser = argparse.ArgumentParser(description="Remove a light, border-connected canvas from an icon image.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--color-threshold", type=int, default=64)
    parser.add_argument("--edge-threshold", type=int, default=360)
    parser.add_argument("--edge-inset", type=int, default=15)
    args = parser.parse_args()
    extract(args.source, args.output, args.color_threshold, args.edge_threshold, args.edge_inset)


if __name__ == "__main__":
    main()
