# What's new

This file is what the update window shows, and nothing else. It is **not** a
list of changes but a selection, and choosing is the work. A point belongs here
if someone notices it while using the program. How many there are is decided by
the release, not by a number.

So: no commit messages, no module names, no section numbers. “The bar vanished
while the application was still computing for four seconds” is a good commit
and a poor entry; “Progress now stays until the computation is really done”
says the same thing to the person sitting in front of it.

One file per language in this folder, as with the catalogues — and all of them
carry the same points in the same order (`tests/test_changelog.py`).
`tools/make_download.py` takes the section for the current version and writes
it into `website/version.json`.

## 0.2.2


### Drawing and shaping

- In sketch mode, points, lines, circles and outlines can be selected and dragged directly in the view. A marker and handle also show what will move.
- The sketch plane stays in space when you switch between top, front and side views. You see its real position instead of the same picture three times.
- A rectangle can be completed by typing its width and height. The dimensions remain as constraints instead of being lost after drawing.
- In the front or side view, pull a closed outline to give it height. The number and wire preview grow with it; typing a value sets the exact height.
- Pull the outline outwards to create a body or inwards to create a visible pocket. An arrow and cross make both directions grabbable.
- A box, cylinder or sketched body appears in the preview while you enter its dimensions. New bodies previously stayed invisible until you applied the step.
- Drawing tools say what the next click will do. Constraints explain their effect and required selection, and degrees of freedom are described in plain language.
- Cuboid, cylinder, bore and hollowing now appear only once in the menu. The tick “Keep faces and edges editable later” replaces the second entry, formerly called “exact”.
- That tick keeps chamfers, fillets, draft angles, offset faces and the STEP export available. The dialogue names the benefit instead of asking for a geometry engine.
- While sketching, the bar names the next step: Pull up, Carve or Done. If a closed outline or a selected body is missing, it says so as well.
- A constraint is taken back by a second click on the same button, and a right-click on the point shows what is attached to it. Before, every click added another one until nothing moved.
- The constraint bar only shows what fits the current selection. When nothing is selected, a single sentence stands there instead of ten greyed-out technical terms.
- Basic bodies are placed “on the print bed” instead of “at Z = 0”, and the drawing tool is called “curve”, like the thing it draws.

### Holes and features

- Change the diameter of a detected hole in an imported model directly, without redrawing the hole or opening a CAD program.
- The changed hole keeps its position and direction and works on meshes as well as exact bodies. A slanted hole also stays on its original axis.
- Feature markers follow the visible geometry after recalculation. A marked hole stays open instead of being covered by its marker.
- Frequent tools such as Hole, Union and Subtract are one click closer in the menu. Headings still keep the groups easy to tell apart.

### Building blocks and standard parts

- Printable screws and nuts come from the catalogue with matching threads. Choose head, length, size and clearance to suit the print.
- Common bearings now have a seat built to their standard dimensions. The bearing can remain removable with clearance or be held by a press fit.
- A screw hole can recess a countersunk head or matching washer. Head depth controls how far either one disappears into the part.
- The standard tables contain more washers, threaded inserts and bearings. Technical sizes are explained in the choice instead of appearing as cryptic codes.
- Magnet pockets, cable clips and cable glands also accept custom dimensions. Extra fields appear only when the selected variant actually uses them.
- Parts live in the catalogue with preview images instead of as a list in the menu. A right-click on the selected body leads there.
- The catalogue says before inserting when the place on the body is missing. Most parts need a selected face or hole; before, the catalogue allowed what the operation then refused.

### Printing and filament

- Each filament spool can carry its own temperatures, cooling, retraction and material values. These values remain when you change the quality level.
- Values from individual spools reach the 3MF file and slicer in the correct material slot. One colour no longer picks up another colour's print values by mistake.
- On first launch, Solidon imports the filaments loaded in the slicer with their name, type, colour and manufacturer profile. Spools do not need to be entered again.
- Included examples no longer replace your chosen printer and material with the settings used to build their preview images.
- In the Linux Flatpak, Solidon finds and starts slicers on the host, including AppImages. Both programs can reach the shared working folder.
- Splitting now puts dowel pins on one half and the matching holes on the other. The message gives their number, or says the cut face is too small for them.
- After splitting, the halves move apart. Pins and holes no longer disappear between two coincident cut faces.
- When two bodies are united, both keep their filament description including its name. The description of the second colour could previously be lost.
- When exporting to several plates, colour changes are counted per plate. Plates of a single material no longer report changes that never happen while printing.

- If the configured slicer fails, the message offers switching to another one. Before, only exporting remained — even with two working slicers sitting right next to it.
- The finished print file can be opened directly in the slicer's own window, with its own profiles. Which handover you use is remembered per project.
- The print file is checked against the model's height. A part stuck below the print bed shows up before printing — not at half height on the printer.
- ElegooSlicer accepts jobs again. And if a slicer arranges the parts itself, the report says so instead of silently replacing your planned plate layout.
- The report no longer stacks old measurements: a new run replaces what it measures anew, the same fact appears only once, and build-volume findings name the object instead of a number.
- The remembered slicer profiles know which slicer they belong to. After a switch, no foreign profile is carried into the new program any more.
- A blocking reason under the print settings disappears as soon as it no longer applies. Before, “needs a printer profile” stayed next to a button that had long been free.

### Chat and 3D generation

- Settings visibly separate cloud and local models. Before you enter a cloud key, they explain which data leaves the computer.
- Checking a slow 3D generator no longer holds the dialog open. It shows what is being checked and how to set up additional programs.
- Assigning detected features stays responsive on large models. Hundreds of features are compared together instead of one after another.
- Requests to Ollama and ComfyUI on the same computer bypass the company proxy. A running local service is no longer falsely reported as unreachable.
- In the Linux Flatpak, setup and launch of local helper programs run on the host rather than in the sandbox. ComfyUI is also found in common Linux and macOS locations.
- The Generate button is only clickable when the click actually starts something. If something is missing, the dialog says what — with a button that leads to the fix.
- If generation fails, ComfyUI's own error line appears in the dialog, together with the step it happened in. That line is exactly what you need when asking for help.
- If a language model types its tool call as text instead of running it, the proposal now explains that — with the way to “Check tools”. Before, raw JSON sat in the conversation without a word.
- The manual has a new page, “Which models Solidon uses”: which ones are proven, where they come from and how long they take. For the way from text it says which file belongs in which folder.
- A very small generated body shows its real volume instead of “0 mm³” next to “closed”.
- For the AI models used in generating, you choose per task which one computes — just like the language model. “Automatic” remains the default and takes what fits.

### View and controls

- The parameter bar keeps dimensions compact and visible. Unit, limits and expression can be changed there with undo, without hiding the value itself.
- Solidon's tool cursors follow the configured system size on Windows, macOS and Linux. Their click point is back on the drawn tip instead of beside it.
- Hovering and selection are clearly different in the view. Analysis and difference colours still take priority over a whole-body highlight.
- Menus, hints and the manual use consistent words for beginners. Specialist terms are explained where they are first needed.
- The Support dialog explains before opening PayPal that payment is voluntary and unlocks no features. If the browser fails, the link can be copied.
- Hollowing and other dependent tools show only fields used by the selected variant and explain hidden values consistently.
- The included examples now open with a guided tour. Step by step, the panel on the right says what to do, and the tour notices by itself when a step is done.
- The suggested actions for an error are kept when saving. After reopening a project, only the error itself used to remain, without the way out.
- The orientation search now examines each position only once. Positions proposed more than once cost time without giving a different result.
- Steps in the history can be deleted and brought back with Ctrl+Z. The question beforehand names the steps that build on the deleted one.
- A double-click on a combined history step says where the individual steps are. Before it did nothing, although the guided tours teach exactly this gesture.
- If a file is refused while being read, the loading indicator disappears. Before it stayed as if a file were still being calculated that had not been accepted at all.
- Solidon starts faster and the layer analysis calculates more quickly. The large calculation libraries are only loaded when something really needs calculating.

- Error messages show the details their sentences refer to. “The start of the answer is shown alongside” — now it really is, together with address and provider.
- The advice “Reduce triangles” and “Open the page in the browser” are now buttons that do exactly that, instead of sentences describing it.
- When a service does not respond, the dialog names the address to check in the browser and keeps the start attempt under “Details”. Its hints only point at buttons that exist in that situation.
- The drop-down lists in the bars below the view stay open until you choose. Before, a list could close itself right away because it moved out from under the pointer.
- The thickness field of the section bar waits until you finish typing. Before, it cut on every keystroke — first with 3 mm, then with 30.
- After opening, the report preselects the topmost finding that offers an action. “Place on the bed” is there as a button right away, without first clicking the list row.
- The note about a cancelled package manager calls the button by its full name — in all six languages. “Details” alone was a small search in five of them.

### Platforms and fixes

- Linux now has an AppImage alongside the Flatpak. Solidon can therefore run as a single executable file without a Flatpak installation.
- A Windows update started from Solidon shows only its progress and opens Solidon again afterwards. A manually launched setup retains the launch choice on its final page.
- The Linux Flatpak can be updated from inside Solidon.
- Feedback can also be sent to support from the Linux package. The package previously lacked network access for this.
- On macOS, fine cracks in a thread's STL mesh are stitched during export without accepting a mesh that became worse.
- Update checking accepts a substantial multilingual changelog. Notes no longer end mid-word, and long lists of changes no longer stop the check.
- The About dialog in the packaged application once again shows notices for every bundled library.
- Error reports show real library versions as well as session and input-method details. A dash no longer falsely says that a required library is missing.
- Individual foreign metadata values no longer make the repair of an imported mesh crash.
- Successful hollowing now reports wall thickness and removed volume for exact bodies too, instead of staying silent after a completed calculation.

## 0.2.1


### Colours and filament

- You colour faces and parts with two gestures instead of a brush: one click colours a face, one click the whole part. If an earlier step changes the dimensions, the colour moves with them.
- A click on the top face colours the top face — the boundary comes from detection, without a radius and without aiming.
- You pick the filament by name and colour — “PETG red” instead of a number. The chat understands it too.
- Twenty spools on the shelf are twenty filaments in the picker. Four spools of the same material in four colours are four entries, not one.
- A filament's colour and its temperatures now belong together. Before, the setting for red could end up on the white filament.
- The same colour gets the same nozzle — on the second plate as well.
- The viewport shows the real filament colour. A filament without its own colour is grey, and the selection stays recognisable.
- Colouring now sits where you look for colour — before it was filed under “Prepare”.
- The field “Colour of the part” showed a different colour than the view beside it in the light theme.
- Typing “PETG” answered “This material profile is unknown”. The field is now a list of the names that really exist.
- The preselection “— none —” was rejected when you confirmed. Now it holds a value the dialog accepts.
- The colour picker showed red, and after deselecting, the part was grey.

### Building blocks

- A barrel hinge that comes off the printer already moving. Nothing to assemble, nothing to insert — the printer leaves the gap open.
- A building block can combine several parts. This lets you save movable or assembled models as one reusable catalogue entry.
- Placing the pin into the hole did not work, although both features were there. Now it does.

### Printing and slicer

- When slicing you choose which plates go along. Anyone who wanted to slice plate 2 used to get three files and the spools of plate 1.
- Solidon now writes out machine and process profile for the slicer instead of pointing at its stock. Seven settings were in the file, one hundred and thirty-six went to the slicer.
- The start G-code comes from the manufacturer's printer profile instead of being written by hand.
- What no longer lays a bead is said by the nozzle: walls that are too thin stand in the report as a finding, not as a suggestion.
- The lower limit for wall thickness comes from the material profile. Two fixed numbers stood there, and both were wrong — on the Centauri it is 0.84 mm.
- The slice button invited a click although nothing followed three sentences later.
- A G-code file with the extension .nc could be opened but not found in the open dialog.

### What Solidon sees in the model

- In imported files Solidon now finds bores and pockets even when the mesh is unwelded. Before, detection found nothing there.
- The report says “several parts” only when there are several. A plate made in one piece counted as 796 parts.
- The same file is no longer examined fifteen times. That saves the seconds that used to pass while opening.
- When simplifying does not get as far as asked, Solidon says so. Until now 992 triangles stayed where 400 were wanted, without a word.
- The same note appears once in the report, not again after every step.
- Two bodies in the same place looked like one, and nobody said so.
- After a union, a feature pointed at a different hole than before.

### Chat and agent

- While the agent works, the chat shows which step is running and which tool. Before, it was silent for up to a minute.
- The list of local models says for each one how reliably it calls tools and how long it takes. A model that only writes about them is now recognisable as such.
- If the connection to the local language model breaks, Solidon says so — and offers a way on instead of reporting a program error.
- The same goes for a broken connection to the image service.
- The chat now names small changes in volume too. A drilled bore used to report “+0.00 cm³”, and the proposal looked as if nothing had happened.

### View and operation

- The object tree names pins and threads, with diameter and pitch.
- A step that creates two bodies stands in the tree with two lines — before there was one.
- If you select more bodies than an operation takes, you now see which ones are used.
- Printing showed the same time differently in two places — “10 h 5 min” below, “605 min” in the dialog.
- Numbers and units read the same everywhere: a line and its own tooltip named the same volume differently, and in inches not at all.
- A dimension can take an expression at every number field — the manual now shows the button too.
- The grid in the sketch editor showed the spacing from the moment you entered it.
- Two text fields reported themselves as optional and never were.

### Fixed

- Duplicating gave the original a new identifier, and the body vanished from the view.
- An exact body that a bore left nothing of stood in the tree as an empty object and could be saved.
- The difference view and the analysis maps stayed silent on exact bodies.
- An unknown kind of field silently turned every field into a text box.
- A dialog could be confirmed, put a step into the history — and nothing changed in the view.
- Rotating by zero degrees ran through silently instead of saying that nothing happens.
- The what's-new window showed seventy-five points as a wall. They are grouped now, and the announcement comes in your language.

## 0.2.0


### Building blocks
- Your own building blocks without a line of code: pick steps from the history and put them into the catalogue as a block — with your own fields, a preview and a value range you choose.
- A block you built travels inside the project file. Whoever opens it can insert your part without having to install anything.
- Five new blocks in the catalogue: pegboard hook, corner brace, foot, cable clip and hinge eye.
- The pegboard hook now holds even when someone lifts the part while taking things off — a springy tongue latches behind the board. Switchable, if you take the part off often.
- Wall mount, rib, tongue and groove, latch, snap fit and living hinge now appear in the menu of a clicked face. Whoever wanted to place a wall mount there used to find everything except it.
- Whoever inserts a block from the catalogue without picking a spot is now asked. Until now it sat at the origin, half inside the part and half beneath the plate.
- The block catalogue can be viewed even without a model. Inserting is then disabled and says why, instead of cancelling only after confirmation.
- The nut trap and the head clearance of the screw hole removed nothing: both built above the face instead of below it.
- The magnet pocket holds the magnet again: the retaining lip used to be added onto the pocket instead of cut out of it, and vanished inside.
- The keyhole slot now hangs vertically, so the screw jams as it sinks down. Lying sideways it used to wander off, and the head found too little room.
- The nut trap now fits the nut: for M5, M6 and M8 the table held too small a height, by six tenths of a millimetre for M5.

### Drawing
- While drawing, the grid shows what snapping follows, the grid step can be typed, dimensions sit at the pointer, and the bar says which face you are drawing on.
- Keyboard shortcuts work again in drawing mode — line, circle, arc, trim, offset, Ctrl+Z — and a right click opens the drawing's menu instead of the model's.
- Fit to view brings the drawing back into frame, and a click five millimetres from a point no longer snaps onto it.
- A construction line stays a construction line, even after being trimmed, extended, offset or mirrored. Until now a centre line turned into a profile edge and split the part.
- A step's dialog shows the dimensions from your drawing instead of the default values, and a circle appears with its full diameter, not half of it.
- A pocket from a drawing with a hole keeps the hole. Until now it milled the island away.
- A drawn hole is subtracted no matter which way round you drew it. Depending on the order of clicks, a fuller part used to come out.
- Trim now cuts only within its own segment, and Extend also finds circles and arcs as a target — until now it only saw lines.
- A loft between two drawings keeps their holes, and a pocket on a side wall cuts into the wall instead of from above.
- An outline that crosses itself is now flagged on the drawing, instead of producing a body that is not watertight and gets exported anyway.
- A drawing with a hole inside a hole keeps every level, and Project uses the plane you are drawing on — until now the third level was dropped and the cut came from below.
- Scaling to a given width measured a construction line as well. Fifty millimetres became five.

### History and steps
- Several steps in the history can be selected at once.
- The limits of a dimension can be changed afterwards — until now, what you entered when creating it was final.
- Changing a step afterwards can now be undone. Until now Ctrl+Z removed the wrong action and left the changed value standing.
- A step that points at a face of another body recalculates after every change. Until now an aligned part stayed at its old spot, even after closing the dialog.
- Features keep their names when a part is rotated or moved for printing. Steps and fits that point at them no longer run into nothing.
- If the face extrusion runs up to disappears, the error now points at that field and suggests choosing another one — instead of at the sketch plane.

### Tools and geometry
- Countersinking only worked in one direction per axis. Clicked from the wrong side it removed nothing and said nothing.
- On stepped parts, hole and plug worked into thin air: the direction came from the bounding box instead of the material at that spot.
- A through plug filled only half the bore — and left the gap all around it by which the bore had been widened for the material.
- Lattice fill placed struts beside the part instead of inside its cavity.
- The vent hole of a hollowed part now ends in the cavity instead of through the roof, and the thread groove of the twist lid no longer tears a hole in its own top.
- Union, subtraction and painting now say when nothing has happened. Until now a step stayed in the history above an unchanged model.
- If a part falls apart because a block no longer touches its carrier, the report now flags it as an error and recommends what helps. Until now the piece count was just a figure.
- A thread in a clicked bore cut only its lower half. The same applied to the heat-set insert.
- An internal thread is now subtracted, as its label promises. Until now a bolt grew into the core hole instead.

### Printing and slicers
- The material estimate for supports was off by a large factor: it computed the area beneath the overhang instead of the column below it.
- Bridge width now measures the stretch that is really spanned freely. A cable duct used to report the width of its bounding box and got the wrong advice.
- A part thinner than one printed layer is no longer stood on its edge.
- Auto split counts the pin overhang towards the bed limit and leaves behind no fits pointing at places that are gone.
- Assemblies now respond to “Place on the bed” too: they move down as a whole, the parts keeping their positions relative to each other. Until now nothing happened, without a word.
- The filament amount read from a G-code file is correct again. A command at the end of the file made everything before it compute differently and doubled the total.
- Changing printer or material keeps what you set yourself. Until now the whole set was reset without notice.
- The filament choice per material slot reaches the slicer. What was stored was the display text instead of the profile.

### View and controls
- A selected face counts: hole, block and sketch go where you pointed. Every operation on a face used to cost two clicks.
- Clicking a bore now suggests the screw that really passes through — and names the measured diameter along with it.
- After “Offset face” the part's faces can be clicked again. Until now nothing was left to draw on, drill into or set a fit against.
- A loading indicator appears immediately when opening a project. Until now the middle of the window stayed black for seconds or showed the start screen — it looked like a crash.
- A click in the view now only hits what you actually see — no hidden part and none from another plate. And after a visit to Move mode, edge lines no longer show through every face.
- The axis views from Ctrl+0 to Ctrl+6 frame the model again, instead of taking the print plate and build volume into the picture too.
- Whoever has moved a part far and then rotates it now rotates around the part again, not around a point beside it.
- A dimension in the view now uses the unit you set, a theme change recolours the print plate and build volume too, and with several plates the label and handle sit on the part instead of beside it.
- What an inserted block brings with it sits in the object tree under its name, and the node offers to change exactly that step.
- The shadow beneath the part now shows every piece on its own and appears more subdued. If a body falls apart, you can now see it in the shadow.

### Files and export
- Two imported files with the same name are no longer lost. The second used to overwrite the first, and the project could no longer be opened afterwards.
- An address without a file extension now says a web page sits there and where the download button is, instead of “Format not recognised”.
- On export, parts with the same name overwrote each other: one file, two success messages, one part gone.
- The project extension is now appended by “Save as”. A project saved as holder.stl used to be an unreadable foreign model when opened.
- A modified project is no longer lost when you drag a file onto the start screen — you are asked first.

### Speed and stability
- The application no longer vanishes without a word when a dimension changes, a drawing is read or a slice is computed. The same calculations run up to sixty times faster now.
- Hollowing out and pinning can really be cancelled now. On a scanned part the button used to stand still for minutes.
- Large files from a slicer open promptly without the window freezing. Merely counting the bodies used to read the whole file into memory.
- If a background calculation gets stuck, the application now says so. Otherwise the legend, layer analysis and the search for a new version used to stall forever.
- Cancel now also drops the next run already queued, and the progress bar no longer disappears over a file that is still being written.

### Languages
- The language chosen in the installer applies immediately, otherwise the system's does. And a language chosen in the window takes effect right away, instead of only at the next start.
- A language change now takes effect throughout the window. The print settings used to stay in the language the application started in.
- The bundled examples now name their dimensions in your language. “Breite, Tiefe, Höhe” used to stand there in German, even in an English interface.
- The command line now speaks the language you set. Until now it gave German help and German error texts, whatever was chosen.

### Chat and support
- A chat proposal that takes steps back now says beforehand which ones go with it. And Cancel really cancels instead of computing on in the background.
- The chat manages eight steps per question again instead of four, and the cost line no longer overestimates.
- What goes out with feedback to support is shown beforehand, word for word — including the log. And if it fails to arrive, the message names the real reason.

### OpenSCAD
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

- Typed decimal numbers are read correctly everywhere. “12.5” stays twelve and a half — before, it could turn into 125, with no question and no warning.
- Every one of the fifty-six fields in the print settings now says what it does when you move it.
- Print time and material use are estimated more accurately, above all for hollowed parts.
- The handover to the slicer lands on the plate. With CuraEngine, parts ended up beside it.
- When splitting with pins, the matching holes now sit in the correct half.
- Millimetres and inches now apply wherever a number appears — including the tool bars and painting.
- Progress stays until the computation is really done, and the window remains usable throughout.
- Every keyboard shortcut is now in one overview: in the Help menu under “Keyboard shortcuts”, or by pressing the question mark key.
