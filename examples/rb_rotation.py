"""A red-black tree rotation, one step at a time. Run: uv run python examples/rb_rotation.py

The tree starts with a red-red violation between 20 and 30 (the kind that propagates up from a fix-up
lower down). 30's uncle 5 is black, so the fix is a left rotation at 10 plus a recolor. The rotation is
shown as three separate moves so the reparenting is visible: unlink 15 from 20 and park it, rotate 10 and
20, then attach 15 as 10's right child. After the recolor, each root-to-leaf path is highlighted in turn
to show the black counts match.

Every node is a group holding a circle and a label, and every edge is a line whose endpoints reference
the two nodes, so edges follow the nodes wherever they tween. Highlights are accumulated per object as
keyframe lists and assigned once at the end, since a property can hold only one expression.
"""

from buttery import Circle, Group, Line, Scene, Text, keyframes

# --- timing: each step holds long enough to read, motion is a fraction of it ------------
HOLD = 3.0          # seconds per step
MOVE = 1.2          # seconds of motion inside a step
RAMP = 0.25         # highlight fade in/out

T_VIOLATE = 1.0
T_UNCLE = T_VIOLATE + HOLD
T_DETACH = T_UNCLE + HOLD
T_ROTATE = T_DETACH + HOLD
T_ATTACH = T_ROTATE + HOLD
T_RECOLOR = T_ATTACH + HOLD
T_CHECK = T_RECOLOR + HOLD
CHECK_EACH = 2.2    # per root-to-leaf path
T_DONE = T_CHECK + 4 * CHECK_EACH
END = T_DONE + 3.0

# --- tree -------------------------------------------------------------------
R = 0.36
LEVEL_Y = [1.3, 0.45, -0.4, -1.25]
LEVEL_DX = [0.0, 1.6, 0.8, 0.4]      # horizontal offset from the parent at each depth
PARK = (0.0, -1.3)                   # where 15 waits between being unlinked and reattached

BG = "#0e0e11"
RED = "#d9484a"
BLACK = "#2a2a33"
INK = "#e8e8ee"
MUTED = "#8a8a94"
EDGE = "#55555f"
FLASH = "#ffb3b3"
GOLD = "#e0a54a"
THIN, THICK = 0.055, 0.1             # edge widths
RING, RING_HI = 0.035, 0.09          # node outline widths
CAPTION_WIDTH = 7.2                  # captions wrap inside the 8-unit frame

# (value, color, left, right): the tree before and after the fix
BEFORE = (10, BLACK, (5, BLACK, None, None),
          (20, RED, (15, BLACK, None, None),
           (30, RED, (25, BLACK, None, None), (35, BLACK, None, None))))
AFTER = (20, BLACK, (10, RED, (5, BLACK, None, None), (15, BLACK, None, None)),
         (30, RED, (25, BLACK, None, None), (35, BLACK, None, None)))


def black_height(tree, parent_color=BLACK, allow_red_red=False) -> int:
    """Black nodes on every root-to-nil path; raises if the paths disagree or a red has a red child."""
    if tree is None:
        return 0
    value, color, left, right = tree
    assert allow_red_red or not (color == RED and parent_color == RED), f"red node {value} under a red parent"
    lh, rh = (black_height(c, color, allow_red_red) for c in (left, right))
    assert lh == rh, f"black heights differ under {value}: {lh} vs {rh}"
    return lh + (1 if color == BLACK else 0)


assert AFTER[1] == BLACK, "root must be black"
black_height(AFTER)                                   # the result is a valid red-black tree
black_height(BEFORE, allow_red_red=True)              # the only defect going in is the red-red pair


def layout(tree, x=0.0, depth=0, pos=None, edges=None):
    """value -> (x, y) and the set of (parent, child) pairs."""
    pos = {} if pos is None else pos
    edges = set() if edges is None else edges
    value, _, left, right = tree
    pos[value] = (x, LEVEL_Y[depth])
    for child, sign in ((left, -1), (right, 1)):
        if child is not None:
            edges.add((value, child[0]))
            layout(child, x + sign * LEVEL_DX[depth + 1], depth + 1, pos, edges)
    return pos, edges


def colors(tree, out=None):
    out = {} if out is None else out
    value, color, left, right = tree
    out[value] = color
    for child in (left, right):
        if child is not None:
            colors(child, out)
    return out


def paths(tree, prefix=()):
    """Root-to-leaf paths as tuples of values."""
    value, _, left, right = tree
    here = prefix + (value,)
    if left is None and right is None:
        return [here]
    return sum((paths(c, here) for c in (left, right) if c is not None), [])


pos0, edges0 = layout(BEFORE)
pos1, edges1 = layout(AFTER)
color0, color1 = colors(BEFORE), colors(AFTER)
undirected0 = {frozenset(e) for e in edges0}
undirected1 = {frozenset(e) for e in edges1}
(removed,) = undirected0 - undirected1                # the one edge that goes away: 20-15
(added,) = undirected1 - undirected0                  # the one edge that appears: 10-15
(moved,) = removed & added                            # the node that changes parent: 15

# --- highlight accumulators ---------------------------------------------------------------
stroke_keys: dict[str, list] = {}
width_keys: dict[str, list] = {}


def pulse(obj_id: str, base_color: str, hi_color: str, base_w: float, hi_w: float, t0: float, t1: float) -> None:
    stroke_keys.setdefault(obj_id, [(0.0, base_color)])
    width_keys.setdefault(obj_id, [(0.0, base_w)])
    stroke_keys[obj_id] += [(t0, base_color), (t0 + RAMP, hi_color), (t1 - RAMP, hi_color), (t1, base_color)]
    width_keys[obj_id] += [(t0, base_w), (t0 + RAMP, hi_w), (t1 - RAMP, hi_w), (t1, base_w)]


def node_pulse(v: int, t0: float, t1: float, color: str = GOLD) -> None:
    pulse(f"n{v}_disc", INK, color, RING, RING_HI, t0, t1)


def edge_pulse(a: int, b: int, t0: float, t1: float, color: str = GOLD) -> None:
    pulse(edge_id(a, b), EDGE, color, THIN, THICK, t0, t1)


def edge_id(a: int, b: int) -> str:
    return f"e_{a}_{b}" if (a, b) in edges0 | edges1 else f"e_{b}_{a}"


# --- nodes ------------------------------------------------------------------
nodes: dict[int, Group] = {}
discs: dict[int, Circle] = {}
for v in pos0:
    disc = Circle(f"n{v}_disc", r=R, fill=color0[v], stroke=INK, stroke_width=RING)
    label = Text(f"n{v}_num", content=str(v), size=0.3, fill=INK)
    g = Group(f"n{v}").add(disc, label)
    (x0, y0), (x1, y1) = pos0[v], pos1[v]
    if v == moved:
        xs = [(T_DETACH, x0), (T_DETACH + MOVE, PARK[0]), (T_ATTACH, PARK[0]), (T_ATTACH + MOVE, x1)]
        ys = [(T_DETACH, y0), (T_DETACH + MOVE, PARK[1]), (T_ATTACH, PARK[1]), (T_ATTACH + MOVE, y1)]
    else:
        xs = [(T_ROTATE, x0), (T_ROTATE + MOVE, x1)]
        ys = [(T_ROTATE, y0), (T_ROTATE + MOVE, y1)]
    g.x = keyframes(xs, ease="in_out_cubic")
    g.y = keyframes(ys, ease="in_out_cubic")
    if color0[v] != color1[v]:
        disc.fill = keyframes([(T_RECOLOR + 0.3, color0[v]), (T_RECOLOR + 0.3 + MOVE * 0.6, color1[v])],
                              ease="out_quad")
    nodes[v], discs[v] = g, disc

# --- edges ------------------------------------------------------------------
edges: dict[str, Line] = {}
for a, b in sorted(edges0 | edges1):
    ln = Line(f"e_{a}_{b}", x1=nodes[a].ref.x, y1=nodes[a].ref.y, x2=nodes[b].ref.x, y2=nodes[b].ref.y,
              stroke=EDGE, stroke_width=THIN)
    if frozenset((a, b)) == removed:
        ln.opacity = keyframes([(T_DETACH, 1), (T_DETACH + MOVE * 0.5, 0)], ease="out_quad")
    elif frozenset((a, b)) == added:
        ln.opacity = keyframes([(T_ATTACH + MOVE * 0.5, 0), (T_ATTACH + MOVE, 1)], ease="out_quad")
    edges[ln.id] = ln

# --- steps ------------------------------------------------------------------
# 1. the red-red edge flashes
flash = [(0.0, EDGE), (T_VIOLATE, EDGE)]
for k in range(3):
    t = T_VIOLATE + 0.45 * k
    flash += [(t + 0.05, FLASH), (t + 0.3, EDGE)]
flash += [(T_UNCLE - RAMP, EDGE)]
stroke_keys[edge_id(20, 30)] = flash
width_keys[edge_id(20, 30)] = [(0.0, THIN), (T_VIOLATE, THIN), (T_VIOLATE + 0.1, THICK),
                               (T_UNCLE - RAMP, THICK), (T_UNCLE, THIN)]
# 2. the uncle is named
node_pulse(5, T_UNCLE, T_DETACH)
# 3. unlink the node that will change parents
node_pulse(moved, T_DETACH, T_ATTACH + MOVE + 0.6)
# 4. rotate: the two nodes that swap roles
node_pulse(10, T_ROTATE, T_ATTACH, color=INK)
node_pulse(20, T_ROTATE, T_ATTACH, color=INK)
# 5. reattach: the new edge lights up
edge_pulse(*added, T_ATTACH + MOVE * 0.5, T_ATTACH + MOVE + 0.6)
# 7. check every root-to-leaf path
for k, path in enumerate(paths(AFTER)):
    t0 = T_CHECK + k * CHECK_EACH
    t1 = t0 + CHECK_EACH
    for a, b in zip(path, path[1:]):
        edge_pulse(a, b, t0, t1)
    for v in path:
        if color1[v] == BLACK:
            node_pulse(v, t0, t1)

for obj_id, keys in stroke_keys.items():
    target = edges.get(obj_id) or discs[int(obj_id[1:-5])]
    target.stroke = keyframes(keys, ease="out_quad")
    target.stroke_width = keyframes(width_keys[obj_id], ease="out_quad")

# --- captions ---------------------------------------------------------------
def caption(name: str, content: str, t0: float, t1: float, color: str = INK, size: float = 0.28) -> Text:
    fade = keyframes([(t0, 0), (t0 + RAMP, 1), (t1 - RAMP, 1), (t1, 0)], ease="out_quad")
    rise = keyframes([(t0, -0.1), (t0 + 0.3, 0.0)], ease="out_cubic")
    c = Text(name, content=content, x=0.0, size=size, fill=color, opacity=fade, max_width=CAPTION_WIDTH)
    c.y = -1.9 + rise
    return c


title = Text("title", content="red-black tree: left rotation", y=1.98, size=0.3, fill=INK)
caps = [
    caption("cap_violate", "20 and 30 are both red: violation", T_VIOLATE, T_UNCLE, color=RED),
    caption("cap_uncle", "uncle 5 is black, so the fix is a left rotation at 10", T_UNCLE, T_DETACH),
    caption("cap_detach", "step 1: unlink 15 from 20 and set it aside", T_DETACH, T_ROTATE, color=GOLD),
    caption("cap_rotate", "step 2: rotate. 20 takes the root, 10 becomes its left child", T_ROTATE, T_ATTACH),
    caption("cap_attach", "step 3: 15 becomes 10's right child", T_ATTACH, T_RECOLOR, color=GOLD),
    caption("cap_recolor", "step 4: recolor. 20 black, 10 red", T_RECOLOR, T_CHECK),
    caption("cap_done", "balanced: root is black, no red-red, two black nodes on every path", T_DONE, END,
            color=MUTED),
]
for k, path in enumerate(paths(AFTER)):
    t0 = T_CHECK + k * CHECK_EACH
    blacks = [v for v in path if color1[v] == BLACK]
    text = "check path " + " > ".join(map(str, path)) + f": black nodes {blacks[0]} and {blacks[1]}"
    caps.append(caption(f"cap_check{k}", text, t0, t0 + CHECK_EACH, color=GOLD))

# edges behind nodes; deeper nodes first so a node rising past its old parent draws on top
order = sorted(nodes, key=lambda v: pos0[v][1])
scene = Scene(duration=END, background=BG).add(title, *edges.values(), *(nodes[v] for v in order), *caps)

if __name__ == "__main__":
    scene.save("examples/rb_rotation.json")
    scene.preview(T_ATTACH + MOVE * 0.7, path="examples/rb_rotation_preview.png")
    print(scene.render("examples/rb_rotation.mp4"))
