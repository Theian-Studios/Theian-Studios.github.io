"""Build the BYU Pac-Man maze + cropped map from byu_campus_map_1.svg.

Outputs (into OUT dir):
  map.svg   - cropped campus map (only elements intersecting the play region)
  data.js   - grid, building centroids, region info
  debug.svg - grid overlay for eyeballing
"""
import xml.etree.ElementTree as ET, re, json, sys, os, collections

SRC = sys.argv[2] if len(sys.argv) > 2 else 'src/byu_campus_map_1.svg'
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(OUT, exist_ok=True)

# Play region in map units (core academic campus)
X0, Y0, X1, Y1 = 560, 770, 1150, 1240
CELL = int(os.environ.get('CELL', 12))  # 12 map units per cell
W = (X1 - X0) // CELL
H = (Y1 - Y0) // CELL

SVGNS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVGNS)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
ns = {'s': SVGNS}
root = ET.parse(SRC).getroot()
m = root.find('s:g[@id="map"]', ns)
def tag(e): return e.tag.split('}')[1]

NUM = re.compile(r'-?\d+(?:\.\d+)?')
def nums(s):
    v = [float(x) for x in NUM.findall(s)]
    return list(zip(v[0::2], v[1::2]))

def geom_points(e):
    """All coordinate pairs of an element (incl. descendants)."""
    pts = []
    for el in e.iter():
        if el.get('points'): pts += nums(el.get('points'))
        if el.get('d'): pts += nums(el.get('d'))
        if el.get('x') and el.get('y'):
            try: pts.append((float(el.get('x')), float(el.get('y'))))
            except ValueError: pass
        if el.get('cx'): pts.append((float(el.get('cx')), float(el.get('cy'))))
    return pts

def intersects(pts, pad=0):
    if not pts: return False
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return not (max(xs) < X0-pad or min(xs) > X1+pad or max(ys) < Y0-pad or min(ys) > Y1+pad)

# ---------- 1. rasterize walkways + roads into grid ----------
grid = [[0]*W for _ in range(H)]
def cell(x, y): return int((x - X0)//CELL), int((y - Y0)//CELL)
def plot(cx, cy):
    if 0 <= cx < W and 0 <= cy < H: grid[cy][cx] = 1

def line4(p, q):
    """4-connected walk from p to q in cell space (sample finely)."""
    (x0, y0), (x1, y1) = p, q
    dist = max(abs(x1-x0), abs(y1-y0))
    n = max(1, int(dist / (CELL/4)))
    prev = None
    for i in range(n+1):
        t = i/n
        c = cell(x0 + (x1-x0)*t, y0 + (y1-y0)*t)
        if prev is not None and c != prev:
            if c[0] != prev[0] and c[1] != prev[1]:
                plot(c[0], prev[1])  # bridge diagonal
        plot(*c); prev = c

def rasterize_group(g):
    for el in g:
        if el.get('points'):
            pts = nums(el.get('points'))
            for a, b in zip(pts, pts[1:]): line4(a, b)

rasterize_group(m.find('s:g[@id="paths"]', ns))
rasterize_group(m.find('s:g[@id="roads"]/s:g[@id="road-fill"]', ns))

# buildings are hard walls: clear any cell whose center lies inside a footprint
def point_in_poly(x, y, poly):
    inside = False
    for i in range(len(poly)):
        (xa, ya), (xb, yb) = poly[i], poly[i-1]
        if (ya > y) != (yb > y):
            xi = xa + (y-ya)*(xb-xa)/(yb-ya)
            if x < xi: inside = not inside
    return inside

buildings = []
bgroup = m.find('s:g[@id="buildings"]', ns)
for g in bgroup:
    if tag(g) != 'g': continue
    polys = []
    for p in g.findall('s:path', ns):
        for sub in re.split(r'(?=M)', p.get('d')):
            pts = nums(sub)
            if len(pts) >= 3: polys.append(pts)
    allpts = [pt for poly in polys for pt in poly]
    if not intersects(allpts): continue
    cx = sum(p[0] for p in allpts)/len(allpts); cy = sum(p[1] for p in allpts)/len(allpts)
    buildings.append({'code': g.get('data-code'), 'name': g.get('data-name'), 'x': round(cx,1), 'y': round(cy,1)})
    for poly in polys:
        xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
        for gy in range(H):
            for gx in range(W):
                px = X0 + gx*CELL + CELL/2; py = Y0 + gy*CELL + CELL/2
                if min(xs) <= px <= max(xs) and min(ys) <= py <= max(ys) and point_in_poly(px, py, poly):
                    grid[gy][gx] = 0


# ---- thin the walkway blob to 1-cell skeleton (Zhang-Suen), then make it 4-connected ----
def zhang_suen():
    def P(x,y): return grid[y][x] if 0<=x<W and 0<=y<H else 0
    changed=True
    while changed:
        changed=False
        for step in (0,1):
            rm=[]
            for y in range(H):
                for x in range(W):
                    if not grid[y][x]: continue
                    p2,p3,p4,p5,p6,p7,p8,p9 = P(x,y-1),P(x+1,y-1),P(x+1,y),P(x+1,y+1),P(x,y+1),P(x-1,y+1),P(x-1,y),P(x-1,y-1)
                    nb=[p2,p3,p4,p5,p6,p7,p8,p9]
                    B=sum(nb)
                    if B<2 or B>6: continue
                    A=sum(1 for i in range(8) if nb[i]==0 and nb[(i+1)%8]==1)
                    if A!=1: continue
                    if step==0 and (p2*p4*p6!=0 or p4*p6*p8!=0): continue
                    if step==1 and (p2*p4*p8!=0 or p2*p6*p8!=0): continue
                    rm.append((x,y))
            for x,y in rm: grid[y][x]=0
            if rm: changed=True
zhang_suen()
# bridge diagonal-only links so the maze is 4-connected
for y in range(H-1):
    for x in range(W):
        if not grid[y][x]: continue
        for dx in (-1,1):
            nx=x+dx
            if 0<=nx<W and grid[y+1][nx] and not grid[y][nx] and not grid[y+1][x]:
                grid[y+1][x]=1

def neighbors(x, y):
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < W and 0 <= ny < H and grid[ny][nx]: yield nx, ny

# prune dead-end stubs (limited depth so the network keeps its shape)
for _ in range(int(os.environ.get('PRUNE', 4))):
    leaves = [(x,y) for y in range(H) for x in range(W) if grid[y][x] and sum(1 for _ in neighbors(x,y)) <= 1]
    for x,y in leaves: grid[y][x] = 0

# keep the largest connected component
seen = set(); best = []
for y in range(H):
    for x in range(W):
        if grid[y][x] and (x,y) not in seen:
            comp = []; stack=[(x,y)]; seen.add((x,y))
            while stack:
                c = stack.pop(); comp.append(c)
                for n in neighbors(*c):
                    if n not in seen: seen.add(n); stack.append(n)
            if len(comp) > len(best): best = comp
grid = [[0]*W for _ in range(H)]
for x,y in best: grid[y][x] = 1
print(f'grid {W}x{H}, open cells {len(best)}', file=sys.stderr)

# ---------- 2. crop the map ----------
keep_layers = ['landcover','parking','tracks','water','roads','paths','buildings','building-labels','area-labels','road-labels']
out = ET.Element(f'{{{SVGNS}}}svg', {'viewBox': f'{X0} {Y0} {X1-X0} {Y1-Y0}',
                         'width': str(X1-X0), 'height': str(Y1-Y0),
                         'font-family': root.get('font-family','sans-serif')})
out.append(root.find('s:defs', ns))
ET.SubElement(out, f'{{{SVGNS}}}rect', {'x':str(X0),'y':str(Y0),'width':str(X1-X0),'height':str(Y1-Y0),'fill':'#efece4'})
def crop_group(g):
    ng = ET.Element(g.tag, dict(g.attrib))
    for el in g:
        if tag(el) == 'g' and not el.get('class','').startswith('building'):
            sub = crop_group(el)
            if len(sub): ng.append(sub)
        elif intersects(geom_points(el), pad=20):
            # drop textPath road labels (they reference paths that may be cropped)
            if el.find('s:textPath', ns) is not None: continue
            ng.append(el)
    return ng
for lid in keep_layers:
    g = m.find(f's:g[@id="{lid}"]', ns)
    if g is not None: out.append(crop_group(g))
ET.ElementTree(out).write(f'{OUT}/map.svg', encoding='unicode')

# ---------- 3. data.js ----------
data = {'x0':X0,'y0':Y0,'x1':X1,'y1':Y1,'cell':CELL,'w':W,'h':H,
        'grid': [''.join('#' if not c else '.' for c in row) for row in grid],
        'buildings': buildings}
with open(f'{OUT}/data.js','w') as f: f.write('window.BYU_DATA = ' + json.dumps(data) + ';\n')

# ---------- 4. debug overlay ----------
dbg = ET.parse(f'{OUT}/map.svg').getroot()
og = ET.SubElement(dbg, f'{{{SVGNS}}}g', {'opacity':'0.7'})
for y in range(H):
    for x in range(W):
        if grid[y][x]:
            ET.SubElement(og, f'{{{SVGNS}}}rect', {'x':str(X0+x*CELL),'y':str(Y0+y*CELL),'width':str(CELL),'height':str(CELL),'fill':'#e0107f'})
ET.ElementTree(dbg).write(f'{OUT}/debug.svg', encoding='unicode')
print('done', file=sys.stderr)
