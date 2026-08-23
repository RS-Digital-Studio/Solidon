# What's new

This file is what the update window shows, and nothing else. It is **not** a
list of changes: of 97 commits between 0.1.1 and 0.1.2, eight lines are left,
and choosing them is the work. A point belongs here if someone notices it
while using the program.

So: no commit messages, no module names, no section numbers. "The bar vanished
while the application was still computing for four seconds" is a good commit
and a poor entry; "Progress now stays until the computation is really done"
says the same thing to the person sitting in front of it.

One file per language in this folder, as with the catalogues — and all of them
carry the same points in the same order (`tests/test_changelog.py`).
`tools/make_download.py` takes the section for the current version and writes
it into `website/version.json`.

## 0.1.3

- The exact kernel can now drill: “Drill an exact hole” works directly on the exact body, without the detour through a mesh.
- Fillets and chamfers are recognised more reliably. A fillet was previously reported as a boss now and then — with a diameter that did not exist.
- The bundled examples no longer greet you with warnings that are none.
- The start screen fits on small screens without scrolling.
- A clicked feature colours itself. Previously the whole body took the selection colour, and you could not see what was meant.
- The object tree names the dimension of every recognised feature.
- Exported meshes no longer contain empty triangles.
- Saving twice gives you the same file twice.
- The five translations have been reviewed. Technical terms are now called what the slicers call them.
- The toolbar is tidier: the widest field was the one you need least often.
- A second program error no longer puts a second window over the first.

## 0.1.2

- Typed decimal numbers are read correctly everywhere. "12.5" stays twelve and a half — before, it could turn into 125, with no question and no warning.
- Every one of the fifty-six fields in the print settings now says what it does when you move it.
- Print time and material use are estimated more accurately, above all for hollowed parts.
- The handover to the slicer lands on the plate. With CuraEngine, parts ended up beside it.
- When splitting with pins, the matching holes now sit in the correct half.
- Millimetres and inches now apply wherever a number appears — including the tool bars and painting.
- Progress stays until the computation is really done, and the window remains usable throughout.
- Every keyboard shortcut is now in one overview: in the Help menu under "Keyboard shortcuts", or by pressing the question mark key.
