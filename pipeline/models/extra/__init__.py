"""Drop-in ranking systems. Any module here (not starting with _) that defines KEY and snapshots() is exported automatically
by pipeline.export.systems as a matrix systems/<season>.json[KEY][snapshot][team]. Then add [KEY, "Label"] to web/config/site.json
("rankingSystems") to expose it in the Rankings toggle. See docs/EXTENDING.md."""
