# Map and comparison design

The map is the main working surface: edit candidate ambulance bases, then compare
the population covered by each method on that same case. This is a projected
metric diagram, not a navigation map or emergency response-time tool.

Palette: paper `#F3F7FA`, surface `#FFFFFF`, ink `#24343D`, greedy amber
`#A85912`, exact teal `#007D83`, QAOA violet `#7150AD`. Demand dots use ink
with opacity; method colours identify both comparison controls and map layers.
Type: Aptos with Trebuchet MS/system fallbacks, humanist headings and tabular
numerals for comparisons. Labels use sentence case.

Desktop layout is left aligned:

```
Purpose / data selection
Metric map (flexible) | Candidate editor (fixed readable width)
Greedy              | Exact                | QAOA
Source and model notes / portable case snapshot
```

Mobile keeps the map first, followed by the editor and stacked comparisons.
Map markers are the distinctive visual element; all other surfaces stay quiet.
Review against the brief: removed decorative statistics and generic dashboard
cards. The comparison columns represent three actual methods; their colours
connect directly to selected sites and covered-zone layers.

Implementation boundaries: plain ES modules with an injected JSON transport;
Python remains the sole coverage/solver implementation. Canvas draws all demand
centroids; accessible DOM markers provide pointer and keyboard interaction.
Display bounds are a fixed padded extent of the original dataset, explicitly
not administrative borders. No map service, framework, browser storage or
external job API is required. Stale results cannot provide current overlays.

Qollab integration and remote lifecycle require an actual platform smoke test;
the local preview harness verifies browser interactions against the real Python
bridge without submitting remote jobs.
