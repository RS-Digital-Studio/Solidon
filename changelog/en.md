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

## 0.2.0

- Your own building blocks without a line of code: pick steps from the history and put them into the catalogue as a block — with your own fields, a preview and a checked value range.
- A block you built travels inside the project file. Whoever opens it can insert your part without having to install anything.
- Five new blocks in the catalogue: pegboard hook, corner brace, foot, cable clip and hinge eye.
- The pegboard hook now holds even when someone lifts the part while taking things off — a springy tongue latches behind the board. Switchable, if you take the part off often.
- A selected face counts: hole, block and sketch go where you pointed. Every operation on a face used to cost two clicks.
- Wall mount, rib, tongue and groove, latch, snap fit and living hinge now appear in the menu of a clicked face. Whoever wanted to place a wall mount there used to find everything except it.
- Whoever inserts a block from the catalogue without picking a spot is now asked. Until now it sat at the origin, half inside the part and half beneath the plate.
- The block catalogue can be viewed even without a model. Inserting is then disabled and says why, instead of cancelling only after confirmation.
- While drawing, the grid shows what snapping follows, the grid step can be typed, dimensions sit at the pointer, and the bar says which face you are drawing on.
- Keyboard shortcuts work again in drawing mode — line, circle, arc, trim, offset, Ctrl+Z — and a right click opens the drawing's menu instead of the model's.
- Fit to view brings the drawing back into frame, and a click five millimetres from a point no longer snaps onto it.
- A construction line stays a construction line, even after being trimmed, extended, offset or mirrored. Until now a centre line turned into a profile edge and split the part.
- A step's dialog shows the dimensions from your drawing instead of the default values, and a circle appears with its full diameter, not half of it.
- Several steps in the history can be selected at once.
- The limits of a dimension can be changed afterwards — until now, what you entered when creating it was final.
- The application no longer vanishes without a word when a dimension changes, a drawing is read or a slice is computed. The same calculations run up to sixty times faster now.
- Changing a step afterwards can now be undone. Until now Ctrl+Z removed the wrong action and left the changed value standing.
- Hollowing out and pinning can really be cancelled now. On a scanned part the button used to stand still for minutes.
- A step that points at a face of another body recalculates after every change. Until now an aligned part stayed at its old spot, even after closing the dialog.
- The material estimate for supports was off by a large factor: it computed the area beneath the overhang instead of the column below it.
- Bridge width now measures the stretch that is really spanned freely. A cable duct used to report the width of its bounding box and got the wrong advice.
- Countersinking only worked in one direction per axis. Clicked from the wrong side it removed nothing and said nothing.
- On stepped parts, hole and plug worked into thin air: the direction came from the bounding box instead of the material at that spot.
- A through plug filled only half the bore — and left the gap all around it by which the bore had been widened for the material.
- Lattice fill placed struts beside the part instead of inside its cavity.
- The vent hole of a hollowed part now ends in the cavity instead of through the roof, and the thread groove of the twist lid no longer tears a hole in its own top.
- Union, subtraction and painting now say when nothing has happened. Until now a step stayed in the history above an unchanged model.
- If a part falls apart because a block no longer touches its carrier, the report now flags it as an error and recommends what helps. Until now the piece count was just a figure.
- Features keep their names when a part is rotated or moved for printing. Steps and fits that point at them no longer run into nothing.
- A thread in a clicked bore cut only its lower half. The same applied to the heat-set insert.
- An internal thread is now subtracted, as its label promises. Until now a bolt grew into the core hole instead.
- The nut trap and the head clearance of the screw hole removed nothing: both built above the face instead of below it.
- The magnet pocket holds the magnet again: the retaining lip used to be added onto the pocket instead of cut out of it, and vanished inside.
- The keyhole slot now hangs vertically, so the screw jams as it sinks down. Lying sideways it used to wander off, and the head found too little room.
- The nut trap now fits the nut: for M5, M6 and M8 the table held too small a height, by six tenths of a millimetre for M5.
- A part thinner than one printed layer is no longer stood on its edge.
- Auto split counts the pin overhang towards the bed limit and leaves behind no fits pointing at places that are gone.
- A pocket from a drawing with a hole keeps the hole. Until now it milled the island away.
- A drawn hole is subtracted no matter which way round you drew it. Depending on the order of clicks, a fuller part used to come out.
- Trim now cuts only within its own segment, and Extend also finds circles and arcs as a target — until now it only saw lines.
- A loft between two drawings keeps their holes, and a pocket on a side wall cuts into the wall instead of from above.
- An outline that crosses itself is now flagged on the drawing, instead of producing a body that is not watertight and gets exported anyway.
- A drawing with a hole inside a hole keeps every level, and Project uses the plane you are drawing on — until now the third level was dropped and the cut came from below.
- After "Offset face" the part's faces can be clicked again. Until now nothing was left to draw on, drill into or set a fit against.
- If the face extrusion runs up to disappears, the error now points at that field and suggests choosing another one — instead of at the sketch plane.
- Clicking a bore now suggests the screw that really passes through — and names the measured diameter along with it.
- Large files from a slicer open promptly without the window freezing. Merely counting the bodies used to read the whole file into memory.
- Assemblies now respond to "Place on the bed" too: they move down as a whole, the parts keeping their positions relative to each other. Until now nothing happened, without a word.
- Two imported files with the same name are no longer lost. The second used to overwrite the first, and the project could no longer be opened afterwards.
- An address without a file extension now says a web page sits there and where the download button is, instead of "Format not recognised".
- The filament amount read from a G-code file is correct again. A command at the end of the file made everything before it compute differently and doubled the total.
- Scaling to a given width measured a construction line as well. Fifty millimetres became five.
- On export, parts with the same name overwrote each other: one file, two success messages, one part gone.
- A loading indicator appears immediately when opening a project. Until now the middle of the window stayed black for seconds or showed the start screen — it looked like a crash.
- A click in the view now only hits what you actually see — no hidden part and none from another plate. And after a visit to Move mode, edge lines no longer show through every face.
- The axis views from Ctrl+0 to Ctrl+6 frame the model again, instead of taking the print plate and build volume into the picture too.
- Whoever has moved a part far and then rotates it now rotates around the part again, not around a point beside it.
- A dimension in the view now uses the unit you set, a theme change recolours the print plate and build volume too, and with several plates the label and handle sit on the part instead of beside it.
- What an inserted block brings with it sits in the object tree under its name, and the node offers to change exactly that step.
- The shadow beneath the part now shows every piece on its own and appears more subdued. If a body falls apart, you can now see it in the shadow.
- If a background calculation gets stuck, the application now says so. Otherwise the legend, layer analysis and the search for a new version used to stall forever.
- Cancel now also drops the next run already queued, and the progress bar no longer disappears over a file that is still being written.
- The language chosen in the installer applies immediately, otherwise the system's does. And a language chosen in the window takes effect right away, instead of only at the next start.
- A language change now takes effect throughout the window. The print settings used to stay in the language the application started in.
- The bundled examples now name their dimensions in your language. "Breite, Tiefe, Höhe" used to stand there in German, even in an English interface.
- The command line now speaks the language you set. Until now it gave German help and German error texts, whatever was chosen.
- Changing printer or material keeps what you set yourself. Until now the whole set was reset without notice.
- The filament choice per material slot reaches the slicer. What was stored was the display text instead of the profile.
- The project extension is now appended by "Save as". A project saved as holder.stl used to be an unreadable foreign model when opened.
- A modified project is no longer lost when you drag a file onto the start screen — you are asked first.
- A chat proposal that takes steps back now says beforehand which ones go with it. And Cancel really cancels instead of computing on in the background.
- The chat manages eight steps per question again instead of four, and the cost line no longer overestimates.
- What goes out with feedback to support is shown beforehand, word for word — including the log. And if it fails to arrive, the message names the real reason.
- Free-form shapes no longer need a second program: what OpenSCAD did, the drawing tools and the building blocks do — one installation less to look after.
- A project holding OpenSCAD source still opens, and everything else in it computes as before. The Report names the step, and “Show the values” copies its source out.


## 0.1.5

- Sketching now happens in the view itself: the drawing surface lies over the model instead of replacing it, and a click in the view sets a point on the sketch plane.
- The grid on the drawing surface shows what snapping actually uses again. For a while it stood at a tenth of a millimetre and lay half behind the toolbar.
- A click in the middle of a hole selects the hole. It used to hit the face beside it or nothing at all — in top view it even cleared the selection.
- A click into a rectangular cut-out selects the part instead of clearing the selection.
- The chat now finds your local model whatever way you write the address. Until now it had to be the full address ending in /api/chat.
- An access key the provider rejects no longer locks out your local model. The chat moves to the next available model by itself instead of sending the same key again.
- Chat error messages now say which model they mean. Above a key error there used to be nothing but a line saying the language model had not answered.
- The field for a service address gives an example and says that a folder does not belong there. Enter one anyway and you get it back with the reason above it.
- The setup dialog no longer crashes when an address field holds a folder path, or the key field holds accidentally pasted text.
- Drop-down menus show all their entries again. Once a field had keyboard focus, the open menu was missing half an entry.
- Ctrl+Z and Ctrl+Y now appear on their menu entries, like the other fourteen shortcuts. They always worked; nothing ever named them.
- Error messages while drawing say which limit was exceeded. “Between three and sixty-four corners” used to sit under nothing but “The input could not be used that way”.
- Merged actions sit in the same menu and appear only once in the command search — hollowing out and hollowing out exactly, for instance.
- A menu entry called “Thread” now says where the thread goes — into a hole or onto a bolt.
- The Spanish interface names features the same way everywhere. The same list used to hold two words for the same thing.
- The application releases memory when a window closes, and shuts down more cleanly.
- The screenshot that goes with a piece of feedback now shows the model as well. There used to be a black area in the middle — exactly where the part in question sits.


## 0.1.4

- During the demo Solidon asks once: after half an hour of work a card settles over the view and asks how it is going. It holds nothing up, and nothing goes out without your click.
- Click a face and insert a part, and it now sits perpendicular to that face instead of pointing straight up. On a side wall a screw hole used to run across the wall.
- A part placed at a hole takes over its size. At a hole of 5.19 mm the press-fit insert used to suggest M3 — which removes nothing there.
- A click with a slightly unsteady hand selects again instead of nudging the part by a tenth of a millimetre.
- A selected part can be moved directly with the mouse — grab and drag, without fetching “Move” first. The handle stays for the precise work: per axis, in grid steps and in height.
- From below you now look through the print bed. If you work on the underside of a part, turn the view beneath it and you see the part instead of the plate.
- A hole can also be selected by clicking into the middle of it — not only on its wall.
- The command search now understands everyday words: “copy”, “delete”, “open” and “colour” led nowhere before, although all four exist.
- The search also finds things for people who do not know the technical term. Type “stiffen”, “snap” or “screw” and you land on the stiffening rib, the snap hook and the screw hole.
- Two menu entries were both called “remesh”. They are now “Refine edges” and “Even out triangles” — the first splits long edges, the second evens out triangle sizes.
- The program speaks the language you hear elsewhere: “exact body” instead of “B-rep”, bed instead of print surface, plate for the layout.
- At startup Solidon checks whether a newer version is out and offers it. It is downloaded and installed only on your confirmation; you can switch this off in the settings.
- A local language model may now compute for ten minutes. Before, the chat gave up after two and asked for an error report — for a calculation that simply took longer.
- A ring is recognised as one feature instead of three beads stacked on top of each other.
- The entry “Thicken surface” now does what it promises. Before, it offset the surface.
- The window title names the model you opened, even when there is no project file for it yet.
- While drawing, the dimension sits at the tip of the line instead of at the window edge.
- A disabled menu entry now says why it is disabled. The reason was there before and invisible.
- The error report carries the state of the scene: objects with dimensions, features, parameters and the history. That makes a fault reproducible instead of guessed.
- Several crashes when closing windows and dialogs are fixed.

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
