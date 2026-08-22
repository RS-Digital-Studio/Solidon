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

## 0.1.2

- Typed decimal numbers are read correctly everywhere. "12.5" stays twelve and a half — before, it could turn into 125, with no question and no warning.
- Every one of the fifty-six fields in the print settings now says what it does when you move it.
- Print time and material use are estimated more accurately, above all for hollowed parts.
- The handover to the slicer lands on the plate. With CuraEngine, parts ended up beside it.
- When splitting with pins, the matching holes now sit in the correct half.
- Millimetres and inches now apply wherever a number appears — including the tool bars and painting.
- Progress stays until the computation is really done, and the window remains usable throughout.
- The manual has gained an overview of every keyboard shortcut.
