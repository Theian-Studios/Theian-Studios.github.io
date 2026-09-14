# Cougar-Man — Pac-Man on the BYU campus

Play: https://theian-studios.github.io/byu-pacman/

The maze is generated from the walkway + road network of the BYU campus map
(`src/byu_campus_map_1.svg`, geometry © OpenStreetMap contributors, ODbL).
`src/build.py` rasterizes the walkways into a grid, skeleton-thins them into
1-cell corridors, carves out building footprints, and writes `map.svg`
(cropped map), `data.js` (grid + building centroids). `game.js` is the game.

Regenerate: `python3 src/build.py .` (env `CELL=12 PRUNE=4` to tune).
