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

## 0.1.4

- At startup Solidon checks whether a newer version is out and offers it. It is downloaded and installed only on your confirmation; you can switch this off in the settings.
- A local language model may now compute for ten minutes. Before, the chat gave up after two and asked for an error report — for a calculation that simply took longer.
- A ring is recognised as one feature instead of three beads stacked on top of each other.
- The entry “Thicken surface” now does what it promises. Before, it offset the surface.
- The window title names the model you opened, even when there is no project file for it yet.
- While drawing, the dimension sits at the tip of the line instead of at the window edge.
- A disabled menu entry now says why it is disabled. The reason was there before and invisible.
- When the calculation stops, it says at which step and why.
- The error report carries the state of the scene: objects with dimensions, features, parameters and the history. That makes a fault reproducible instead of guessed.
- Several crashes when closing windows and dialogs are fixed.
- The version file is signed, and Solidon checks the signature before it offers an update.
- The print surface is called the bed everywhere and its layout the plate — the way the slicers name them.

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
