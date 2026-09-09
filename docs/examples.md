# Examples

Every example in [`examples/`](https://github.com/fletchgraham/buttery/tree/main/examples) exists as a Python
script and as the JSON it saves. Run one with `uv run python examples/merge_sorted.py`. The prompts above each
one are what was typed into Claude Code with the buttery skill installed.

## Merging two sorted lists

```
❯ Use buttery to make an animated explainer of merging two sorted lists.
```

![Merging two sorted lists, one comparison per beat](media/merge_sorted.gif){ .example }

[`examples/merge_sorted.py`](https://github.com/fletchgraham/buttery/blob/main/examples/merge_sorted.py): the
merge is simulated in Python, then each step becomes keyframes.

## Red-black tree rotation

```
❯ Use buttery to show a red-black tree left rotation one step at a time.
```

![Red-black tree left rotation, one step at a time](media/rb_rotation.gif){ .example }

[`examples/rb_rotation.py`](https://github.com/fletchgraham/buttery/blob/main/examples/rb_rotation.py): nodes
are groups, edges are lines whose endpoints reference the nodes, so the edges follow the rotation for free.
The before and after trees are two tuples; the script diffs them.

## Walking through a function

```
❯ Use buttery to walk through a small Python function one line at a time.
```

![Walking through a function, one line at a time](media/code_walk.gif){ .example }

[`examples/code_walk.py`](https://github.com/fletchgraham/buttery/blob/main/examples/code_walk.py): the
function is revealed a line per beat, then a caption walks through it. Each step selects the part it talks
about with spans whose `background` tweens in and out, while the syntax coloring underneath stays put.

## Syntax theme

```
❯ Use buttery to show every token color of the syntax highlighter, one kind per beat.
```

![Every color of the syntax highlighter, side by side](media/syntax_theme.gif){ .example }

[`examples/syntax_theme.py`](https://github.com/fletchgraham/buttery/blob/main/examples/syntax_theme.py): a
custom `theme` colors all six token kinds; the legend walks them one per beat and every token of that kind
pulses in the code.

## Smaller ones

- [`bounce.py`](https://github.com/fletchgraham/buttery/blob/main/examples/bounce.py): a ball on a sine wave
  with a ring that follows it by reference.
- [`squash_bounce.py`](https://github.com/fletchgraham/buttery/blob/main/examples/squash_bounce.py): decaying
  ballistic arcs and squash on impact, all as expressions of `t` with no state.
- [`launch_demo.json`](https://github.com/fletchgraham/buttery/blob/main/examples/launch_demo.json): a scene
  written directly as JSON.
