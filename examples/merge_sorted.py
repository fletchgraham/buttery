"""Merging two sorted lists, one comparison per beat. Run: uv run python examples/merge_sorted.py

The merge is simulated in plain Python up front to produce a list of steps (which head wins, where it
lands). Each step then becomes a set of keyframes: both heads pop and light up while a readout shows the
comparison, the smaller value arcs down into the next output slot, and that list's pointer advances.
Because every property is a pure function of time, a cell that has already moved simply holds its final
keys, so nothing needs to be tracked frame to frame.
"""

from buttery import Group, Rect, Scene, T, Text, clamp, keyframes

# --- data and beats ---------------------------------------------------------
A = [1, 4, 7]
B = [2, 3, 8]
START = 1.0         # hold before the first comparison
STEP = 1.6          # seconds per comparison (compare, move, then a beat of rest)
POP = 0.55          # compare phase: heads scale up, readout appears
MOVE = 0.6          # travel time from the head slot to the output slot
LIFT = 0.35         # how high the arc rises above a straight path

# --- layout -----------------------------------------------------------------
CELL = 0.62
GAP = 0.78
Y_A, Y_B, Y_OUT = 1.35, 0.4, -1.3
X_IN = -1.85                         # x of the first cell in rows A and B
X_OUT = -(len(A) + len(B) - 1) * GAP / 2
X_READ = 2.15                        # readout column on the right

BG = "#0e0e11"
COL_A, COL_B = "#4a90d9", "#e0a54a"
DIM = "#26262d"
INK = "#e8e8ee"
MUTED = "#8a8a94"


def x_in(i: int) -> float:
    return X_IN + i * GAP


def x_out(j: int) -> float:
    return X_OUT + j * GAP


# simulate the merge, recording what each beat does
steps = []                            # (src, i, value, j, a_head, b_head)
i = j = 0
while i < len(A) or j < len(B):
    a = A[i] if i < len(A) else None
    b = B[j] if j < len(B) else None
    if b is None or (a is not None and a <= b):
        steps.append(("A", i, a, i + j, a, b))
        i += 1
    else:
        steps.append(("B", j, b, i + j, a, b))
        j += 1


def beat(k: int) -> float:
    return START + k * STEP


# --- objects ----------------------------------------------------------------
objs = []

title = Text("title", content="merge two sorted lists", y=1.98, size=0.32, fill=INK)
label_a = Text("label_a", content="A", x=-2.55, y=Y_A, size=0.34, fill=COL_A)
label_b = Text("label_b", content="B", x=-2.55, y=Y_B, size=0.34, fill=COL_B)
label_out = Text("label_out", content="out", x=X_OUT - 0.85, y=Y_OUT, size=0.3, fill=MUTED)
objs += [title, label_a, label_b, label_out]

# empty output slots, so the destination is visible before anything lands
for n in range(len(A) + len(B)):
    objs.append(Rect(f"slot{n}", x=x_out(n), y=Y_OUT, w=CELL, h=CELL, corner_radius=0.12,
                     fill=None, stroke=DIM, stroke_width=0.035))


def make_cells(name: str, values: list[int], y: float, color: str) -> list[Group]:
    cells = []
    for idx, v in enumerate(values):
        box = Rect(f"{name}{idx}_box", w=CELL, h=CELL, corner_radius=0.12, fill=color,
                   stroke=color, stroke_width=0.045)
        num = Text(f"{name}{idx}_num", content=str(v), size=0.34, fill="#111116")
        cells.append(Group(f"{name}{idx}", x=x_in(idx), y=y).add(box, num))
    return cells


cells = {"A": make_cells("a", A, Y_A, COL_A), "B": make_cells("b", B, Y_B, COL_B)}
rows_y = {"A": Y_A, "B": Y_B}
colors = {"A": COL_A, "B": COL_B}

# pointers: a small diamond under the current head of each row
pointers = {}
for name in "AB":
    d = Rect(f"ptr_{name.lower()}", w=0.16, h=0.16, rotation=45, fill=colors[name],
             y=rows_y[name] - 0.5)
    pointers[name] = d

# per-step keyframes -------------------------------------------------------------
ptr_x = {"A": [(0.0, x_in(0))], "B": [(0.0, x_in(0))]}
ptr_op = {"A": [(0.0, 1.0)], "B": [(0.0, 1.0)]}
scale_keys = {}     # cell id -> list of (t, scale)
stroke_keys = {}    # cell id -> list of (t, color)
readouts = []

for k, (src, idx, value, dest, a_head, b_head) in enumerate(steps):
    t0 = beat(k)
    t_move = t0 + POP
    t_land = t_move + MOVE
    winner = cells[src][idx]
    heads = []
    if a_head is not None:
        heads.append(cells["A"][A.index(a_head)])
    if b_head is not None:
        heads.append(cells["B"][B.index(b_head)])

    # both heads pop and get a white outline while being compared
    for cell in heads:
        box_id = f"{cell.id}_box"
        base = colors["A" if cell.id.startswith("a") else "B"]
        sk = scale_keys.setdefault(cell.id, [(0.0, 1.0)])
        ck = stroke_keys.setdefault(box_id, [(0.0, base)])
        sk += [(t0, 1.0), (t0 + 0.18, 1.12)]
        ck += [(t0, base), (t0 + 0.15, "#ffffff")]
        if cell is winner:
            sk += [(t_land, 1.12), (t_land + 0.25, 1.0)]
            ck += [(t_land, "#ffffff"), (t_land + 0.3, base)]
        else:
            sk += [(t_move, 1.12), (t_move + 0.2, 1.0)]
            ck += [(t_move, "#ffffff"), (t_move + 0.2, base)]

    # the winner arcs from its head slot into the next output slot
    u = clamp((T - t_move) / MOVE, 0, 1)
    winner.x = keyframes([(t_move, x_in(idx)), (t_land, x_out(dest))], ease="in_out_cubic")
    winner.y = keyframes([(t_move, rows_y[src]), (t_land, Y_OUT)], ease="in_out_cubic") + LIFT * 4 * u * (1 - u)

    # that row's pointer advances (or fades out if the row is exhausted)
    nxt = idx + 1
    if nxt < len(cells[src]):
        ptr_x[src] += [(t_land - 0.1, x_in(idx)), (t_land + 0.25, x_in(nxt))]
    else:
        ptr_op[src] += [(t_land - 0.1, 1.0), (t_land + 0.25, 0.0)]

    # readout: "1 < 2" then "take 1 from A"
    if a_head is not None and b_head is not None:
        sym = "<" if src == "A" else ">"
        line1 = f"{a_head} {sym} {b_head}"
    else:
        line1 = ("B" if a_head is not None else "A") + " is empty"
    line2 = f"take {value} from {src}"
    fade = keyframes([(t0, 0), (t0 + 0.2, 1), (t0 + STEP - 0.2, 1), (t0 + STEP - 0.02, 0)], ease="out_quad")
    slide = keyframes([(t0, 0.12), (t0 + 0.3, 0.0)], ease="out_cubic")
    readouts.append(Text(f"read{k}_cmp", content=line1, x=X_READ, y=1.05, size=0.4, fill=INK,
                         opacity=fade))
    readouts[-1].y = 1.05 + slide
    readouts.append(Text(f"read{k}_take", content=line2, x=X_READ, y=0.62, size=0.26, fill=colors[src],
                         opacity=fade))
    readouts[-1].y = 0.62 + slide

for name in "AB":
    for cell in cells[name]:
        if cell.id in scale_keys:
            cell.scale = keyframes(scale_keys[cell.id], ease="out_cubic")
        box = cell.children[0]
        if box.id in stroke_keys:
            box.stroke = keyframes(stroke_keys[box.id], ease="out_quad")
    pointers[name].x = keyframes(ptr_x[name], ease="in_out_cubic")
    pointers[name].opacity = keyframes(ptr_op[name], ease="out_quad")

END = beat(len(steps))
caption = Text("caption", content="compare the heads, take the smaller, advance that pointer",
               y=-2.0, size=0.26, fill=MUTED)
done = Text("done", content="sorted", x=X_OUT + (len(A) + len(B) - 0.5) * GAP + 0.7, y=Y_OUT,
            size=0.28, fill=INK, opacity=keyframes([(END, 0), (END + 0.4, 1)], ease="out_quad"))

# draw order: pointers behind, B row before A row, each row reversed so the head is on top of the cells
# it passes while moving (an A cell crosses row B on its way down)
objs += list(pointers.values()) + cells["B"][::-1] + cells["A"][::-1] + readouts + [caption, done]
scene = Scene(duration=END + 1.4, background=BG).add(*objs)

if __name__ == "__main__":
    scene.save("examples/merge_sorted.json")
    scene.preview(beat(1) + POP + MOVE / 2, path="examples/merge_sorted_preview.png")
    print(scene.render("examples/merge_sorted.mp4"))
