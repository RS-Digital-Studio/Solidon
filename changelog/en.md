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

## 0.4.1

### Drilling and placing

- When you place a hole, one tick turns it into a slot: you enter length and direction, and the preview shows both.
- A hole that is already in the model can be pulled out into a slot afterwards — the diameter stays as it was measured.
- The slot is widened by the material tolerance over its whole length. The travel a screw has inside stays the one you entered.
- If a slot hangs over the edge at one end, Solidon says so — even when its centre sits deep in the material.
- A slot stands in the object tree as a slot, with its width and its length — also in a model you opened that somebody else drew.
- An existing slot can be pulled longer afterwards, and its direction stays where it was.
- A selected hole or slot is set right in the view with “Set in the view”: a handle to move and turn it, knobs to pull it, dimension lines to edges and centres.
- Only “Apply” on the right makes a step of it; Escape discards. A pulled slot shows its length meanwhile and keeps its shape when you move it at the handle.

### Recognition

- A countersink above a hole is now kept even on a part with round, sweeping surfaces — previously it was dropped there, and the hole and its countersink could no longer be moved together.
- A cavity entirely inside the material, with no way out, appears in the object tree as an air pocket — with its volume. Previously it appeared as a hole that was not there.

### Labelling

- A label can now use eight fonts instead of three, plus bold and italic. Bold carries thicker strokes at the same height and stays legible where the regular style smears.
- Beside the upright faces there is now a round one and a handwritten one — those two come in a single style. All eight travel with the program, so a project looks the same everywhere.
- If a font is too fine for your nozzle, Solidon says from which height it carries — instead of printing it and letting the letters run together.

### Building blocks and fits

- A part from the catalogue appears in the view at once: on the selected face or on top of the body, with dimension lines and a handle. A click places it elsewhere, “Apply” inserts it.

### View and operation

- The actions for a selected body or feature live in one place on the right, in groups you can fold, with a search box. The Object, Modify and Prepare menus are gone for that; shortcuts still work.
- A right-click on a body or face shows only what exists there alone: the step behind it, the sketch on the face, hiding. The “Parts” button stands in accent colour.
- When the chain stops at a step, the actions are locked and say why; trying anyway shows the report's ways out right away. Before, the step landed silently behind the halt, never computed.

### Print bed and handover

- If a body made of loose parts — lettering, say — fits no bed as a whole, the report offers to split it and orient it right away: one click, and the parts lie on the plates.
- “Open in slicer” hands ElegooSlicer, Orca and Bambu Studio all plates in one file — one window instead of one per plate.
- For splitting, lettering and texture the report states the number in the sentence, where a placeholder in braces stood before.
- Lettering you assigned a filament to keeps it when split into letters. Before, it arrived in the slicer on a second, grey filament, with the assigned one sitting unused beside it.

## 0.4.0

### Building and editing

- Counterparts such as a dowel pin and its hole go onto both parts in a single step. You enter the shared dimensions once, and one undo takes the pair back.
- Lofting between two outlines now takes two separate sketches: round at the bottom, square at the top. That is how you build an adapter from a pipe to a duct.
- Sweeping along a path now follows a drawn path with several corners and arcs instead of a single even arc. At sharp corners Solidon mitres the joint.
- Fillets and chamfers now work on a single edge as well. You pick it from a list that names every edge with its position and its length.
- A building block goes to several places in one step: four holes get their press-fit inserts together, and one undo takes all four back.
- New is *Check the join path*: it moves a part into its final position and reports where it hits something on the way — even when both parts fit in the final position.
- Every building block can be written out as OpenSCAD source, from the catalogue or from the command line.
- The exact core can now drill into a slanted face as well, with countersink and counterbore; patterns and plug-in assemblies survive it.

### Drilling and placing

- When you place a hole, the preview shows the outline of its mouth instead of a half-transparent cylinder. The spot that matters stays clear.
- The preview follows the mouse smoothly: the face search under the pointer no longer starts over on every movement.
- The dimension fields move out of the way of the spot where the hole appears, instead of standing on top of it.
- Choosing an operation that is placed in the model starts placing right away; the button in front of it is gone.
- Once you confirm the dimensions you set the depth with the mouse. The model turns translucent and the view swings to the side so you can look into the hole.
- While you drag, the depth snaps briefly to the places that mean something: the middle of the material and its back face.
- Box, sphere and the other primitives can be moved and turned in the preview already, with the same handle as on a finished body.
- The primitives have gained a rotation angle: the direction says where the body points, the angle says how it stands around that direction.
- Drilling into a cylinder, a sphere or a torus no longer raises the warning that the hole reaches past the edge on every single hole.
- A hole with a countersink is removed completely when you confirm, instead of leaving the countersink behind with no way back.

### Features and selection

- A hole you click on now only offers the actions that do something there — labels and filament assignment used to sit there too.
- Every action on a feature appears once instead of twice, and a block heading above a single row is gone.
- On an existing countersink, *Countersink* can be reached again.
- In the object tree, features of the same kind are only bundled when their size matches too. Ten fillets with different radii are listed separately again.
- A body with an assigned filament shows its selection in the view again, instead of staying grey like all the others.
- The fields on a feature carry their name: a screen reader now says what a field belongs to, instead of six times spin box, 0.00.

### Building blocks and fits

- Your own building blocks can be opened from the catalogue for editing again, even when the project they came from is gone.
- The tolerance ladder picks up the measured size of the hole you open it on, instead of a fixed default of 6 mm.
- Snap hooks and clamping tongues now calculate with material and spring travel instead of a rule of thumb. Solidon reports an arm that breaks the first time it snaps in.
- The three calibration bodies come without a helper body, and the tolerance ladder prints as two numbered strips that plug into each other.
- The spring warning measures the actual arm, the living hinge moves, and the strain relief carries through into preview and output.
- A building block lays down supporting material before it cuts where that is needed; and their preview sits correctly even without a host.
- A building block explains which combination of dimensions it cannot build, instead of quietly capping them.

### Filaments and stock

- Your filament stock has a place of its own: a tile on the start page and a shelf instead of a list, with the fill level drawn as winding on the spool.
- Two spools with the same name are kept apart. Each carries its own remainder, and the opened one is the interesting one.
- When slicing and when handing over, Solidon asks whether it should book the consumption. After slicing that is the measured amount from the print file, otherwise an estimate.
- Every booking can be taken back, every spool carries its history, and only those who explicitly set it up book without being asked.
- An assigned filament can be removed again without the neighbouring faces losing theirs in the process.
- A painted face arrives in Orca and PrusaSlicer with its filament, no longer without.
- After a filament is cleared, the vendor profile no longer ends up on the wrong filament.
- On the shelf, search and main actions sit together, and storage place and nominal fill are in the spool dialog.

### Printing and preparing

- Solidon finds what Cura has: printers, process profiles and filaments that stayed invisible before.
- From PrusaSlicer, Solidon picks up the loaded filaments and the printer you last set.
- If your slicer does not know the printer at all, Solidon says so — instead of sending you to a list with nothing in it.
- Switching the quality level takes seconds instead of the better part of a minute, and the window stays usable while it does.
- The advice on print settings looks at every body on the plate instead of just the selection. What one body needs is kept, even when the one next to it does without.
- It calculates in the background, names the body, shows its progress and can be cancelled.
- A long bridge is judged by its actual supports, and the overhang angle holds for the printer, nozzle, layer height and line width it was measured under.
- Excessive speed is now capped on the affected kind of path, instead of heating nozzle and bed further and further.
- Suggestions you deselected stay deselected, and a change of filament, scene, plate or quality invalidates an outdated result at once.
- The spacing when arranging now counts the bed adhesion skirt and the support structure: both count twice between two neighbours.
- Parts are arranged in the middle of the bed, the way the slicers next door do it, instead of in the back left corner.
- Orienting for printing now lays the turned parts out again afterwards. A body that lies down needs more area, and used to end up inside its neighbour.
- In the print settings, the second filament picker under the slicer profiles is gone. It repeated what the filament picker already says; fetching the profile values is now a button of its own.
- Orient for printing now takes every body in the scene, not just the selected ones. The whole bed then moves to the centre instead of a turned part dodging a standing one into the corner.

### View and operation

- The Solidon mouse pointer is now used across the whole window and in every dialog, not just in the 3D view.
- Switching the variant in an operation dialog no longer ends the application.
- An open operation dialog no longer survives a change of project unnoticed.
- Long notes are no longer cut off while space next to them stays free.
- From the command line, *Assign filament* could not be called; now it can.
- The first click and the first turn no longer stutter: what the view has to prepare for them now happens at start-up.

### Update, installation and system

- Under *What is new* you find the last three versions. The full history of every release is on solidon3d.de and stays available there.

### Manual and website

- The images on solidon3d.de show the model at full width instead of a strip between the panels.
- Manual and website name every operation there is, including the new feature editors.

## 0.3.5

### View

- The 3D view now draws with a new graphics layer. It addresses the graphics card through Direct3D 12, Vulkan or Metal and stays fluid even at several million triangles.
- Recesses and edges stand out more clearly: the view darkens corners, draws depth lines and hits the point you are pointing at.
- Body edges sit as a fine wireframe above the surface, and labels hold still instead of jittering while you orbit.
- Feature names no longer overlap, and their markers stay visible inside a section as well.
- The axis indicator at the bottom left fills its field in every viewing direction, and its letters are shown in full.
- The fixed views now turn the camera around the point you are looking at. Your framing stays instead of jumping back to the whole scene; *Fit to view* still does the framing.
- Pointing through an opening at the face behind it selects that face and not the rim of the opening.
- Large models build up faster because edges and surface normals are computed only once per body.
- If the machine lacks the graphics support the view needs, the application names the two packages that have to be installed.
- Tilt the view close to an axis and it snaps there while keeping your rotation, instead of jumping to a fixed pose.

### Actions for the selection

- Report and chat now close with their own edge on the right. The actions for the selection sit below them in a card of their own, with the model visible between the two.
- Which actions come first depends on the selection: with several bodies Unite, Subtract and Intersection, with a single one Drill a bore, Hollow out and Split.
- On a bore you clicked you now find Countersink and Fill a bore, on a face Drill a bore, Cut pocket and Offset face.
- A selected body shows its filaments right there and lets you change them.
- A search field in the same card finds the remaining operations; features and parts stay in their own areas.
- The right-hand column is wider: the actions for the selection fit fully, instead of crowding into half the width.

### Building and editing

- Unite, Subtract and Cut now take every selected body at once instead of exactly two.
- Fillet no longer takes the application down when the radius is larger than the wall it is meant to round.
- A body from the exact kernel stays exact when you only move or rotate it. Fillet and chamfer remain available afterwards.
- The drilling tool now protrudes only at the mouth of the bore and rejects diameters that exceed the part many times over.
- Aligning flush means flush up to an angle, not up to a single point distance.
- Reduce triangles stops at a named resolution, and lattice fill no longer invents an interior that is not there.
- The sketch editor hits arcs on a full circle, finds circle rims, deletes the selected element with Del and does not leave Redo hanging.
- The feedback while sculpting no longer declares small changes to be without effect.
- Switches of an operation that are on by default can now be turned off from the command line as well.
- An error inside an operation names its cause: in the log, in the line that stopped it and in the error report.
- Rejected input in placement, mesh storage and recipes now comes with a suggested action instead of a bare error message.
- Parts explain which parameter combinations they will not build, instead of quietly clipping dimensions.
- An unsuitable number of selected bodies is reported before the calculation, instead of dropping an input unnoticed.
- Placing on a surface changes the document only when you accept it; a discarded preview leaves nothing behind.
- Letters and digits stay in the input field — navigation keys take effect only when you are not typing there.
- Split into separate parts turns several loose bodies in one file into one object each — what does not touch is not one part.

### Features

- An imported scan no longer carries invented domes and sockets; until now they arose in their hundreds from smoothly rounded surfaces.
- Several threads on one plate are named individually instead of being merged into a single feature.
- Sphere, torus and cone report their curvature, cylinder centres match their end rings, and thread turns follow the axis.
- The feature panel offers fits only when a second body is selected, and it knows every group the core uses.
- Automatic cut fits no longer hand out the same name twice.
- Feature detection reaches the same result faster on complex meshes.

### Printing and preparing

- The orientation search now judges in two stages: two hundred poses from the surface normals, nine of them in the layer analysis.
- Its progress bar runs to the end even when there was nothing to cut.
- The slicer receives the world of the printer instead of the one from Solidon, and a custom profile keeps its vendor base.
- Custom slicer profiles come before a vendor profile of the same name, and an AppImage finds its inventory.
- The clean-up after import keeps the filament assignments.
- The printer belongs to the project and can be changed in the header as well as in the print dialog; assigned filaments, colours and your own print values are kept.
- Every body carries its filament in the object tree: a colour field before the name, one click assigns another.
- Several spools of the same material type stay distinguishable by name and colour.
- The operations behind it are named after their purpose: *Assign filament* and *Filament on a face* instead of *Colour part* and *Colour face*.
- The slicer handover resolves every spool against its own material type; your own print values keep priority.
- If the support map takes too long, the calculation ends with an explanation and offers to reduce the triangles.
- The print dialog stays fully usable in narrow windows as well.
- Orient for printing aligns every selected body, not just the first.

### Files and projects

- A 3MF with many levels of duplication is rejected before 432 bytes turn into a thousand bodies.
- A small project file no longer asks for gigabytes of memory.
- A GLB file in millimetres arrives in millimetres and not as metres.
- A failed save no longer takes the last backup with it, and cancelling really does cancel the import.
- A late error while reading no longer clears the source of the next project.
- If the cache folder cannot be created, the finished result still stays.
- An incomplete set of variants is no longer exported silently.
- The discarded sketch can be brought back with Undo, and a second history object no longer leaves a stale Redo behind.
- Two error reports from the same second no longer overwrite each other.
- Inputs you chose explicitly survive saving and reopening, instead of being replaced by a default.
- Cancelling also ends the calculation still running behind a variant.

### Chat and AI

- An extra tool with a wrongly typed field no longer tears down the whole run of the agent.
- For sketch variants the agent now names only menu paths that exist.
- In image generation the weights arrive whole or not at all, and a single value in the structure field no longer triggers an unordered generation.
- A local model is measured even when it answers over HTTPS on a port of its own.
- The note about AI involvement applies only with written evidence, and a change of language no longer ends the remote control.
- The ComfyUI setup adopts model weights that are already complete, instead of downloading them again.

### Update, installation and system

- The minimum version is now macOS 13, alike in package, installer and on the website.
- Thirteen libraries are on their latest stable releases, and the exact kernel speaks OpenCASCADE 8.
- A package without a trust anchor in the system brings its own set along, on every platform.
- A download no longer breaks off after a fixed total time, and a trickling answer keeps the promised deadline.
- Inside the Flatpak the application finds the package manager of the machine.
- On Linux and macOS an abort no longer ends at the parent process only.
- The Linux menu entry finds the launcher even without an entry in the search path.
- On the Mac the update dialog says that Solidon comes back by itself after the installer.
- On the Mac the 3D mouse reads through the vendor driver instead of waiting beside it.
- The start screen recognises the system before the first picture, and the requirements table is no longer cut off.
- A rejected attachment no longer counts as a missing one for the feedback.
- The filament picker stays on the right spool after a cancellation and shows the eighth one too.
- A support mail opened by hand carries a readable subject and body inside Flatpak as well; cancelling leaves the report in place.

### Manual and website

- Manual and screenshots show the reworked interface in all six languages.
- The drawings in the manual keep the text contrast in their side notes as well.
- The manual window loads only its own figures and no external images.
- The website says in one place what leaves your machine.
- The introduction no longer claims a closed hole when Undo only puts the diameter back.

## 0.3.4

### Editing detected features

- A bore and its linked countersink now move together, whichever of the two you select. The feature panel identifies the link before you make the change.
- When you edit a bore, its countersink remains assigned beneath it in the object tree and can be adjusted directly as well.
- The feature panel combines identical unavailable actions and clearly names the affected groups of fields.

### Feature recognition

- Threads in imported models are recognised more reliably; incorrect cones, pins and spheres on them no longer appear as separate features.
- Narrow seams between joined shapes no longer create large numbers of incorrect features.
- Feature recognition is noticeably faster on large, detailed models.

### Analysis maps

- Analysis maps are now available for more large models.
- If an analysis map is too large for a model, the message directly offers *Reduce triangles*.
- Support-need analysis is considerably faster on large models.

## 0.3.3

### Display and selection

- The first click selects the part, the second the bore beneath it, a click beside it clears the selection — and the chosen navigation applies throughout.
- Rotating keeps the horizon level: after a gesture the view stands as upright as before, in each of the five navigation schemes.
- The navigation and the theme chosen in the settings are ticked in the *View* menu as well.
- Several selected bodies stay selected after a recalculation, and one drag moves them together.

### Working on the project

- A project can be saved even when a note is attached to a feature.
- Switching between two analysis maps of the same body shows at once what has already been computed.
- A new project starts without remnants of a preview that was still open at the time.
- Through remote control, *Undo* takes back exactly the step named, not the topmost one.

## 0.3.2

### Editing recognised features

- Moving, rotating or removing a hole leaves no material behind at its old position — on parts with a groove or a cavity as well.
- The command *Fill a bore* now fills exactly the bore as well: the plug no longer protrudes into a groove or makes the part thicker.
- A spherical socket is recognised as a sphere and not as a countersink even in finely meshed models, so it carries the actions that belong to it.
- A duplicated hole gets an identity of its own rather than that of a deleted one, so a fit still refers to the feature it means.
- When rotating too, a through hole says if it no longer goes through at its new orientation.
- A newly created feature appears at the end of the object tree, not in the middle of the older ones.
### Display and selection

- The preview disappears once the change is applied; until now the comparison body with its “not yet applied” banner stayed on top of the finished hole.
- The space bar again toggles between before and after only where a preview is shown, and no longer everywhere in the application.
- A hole no longer glows in the selection colour when nothing is selected at all.
- The rotation arc, the shadow, the drag markers and the brush ring disappear with the action they belong to — including on tool change, undo or closing the project.
- A measurement stays with its part, even when the view switches to another print bed or to all of them.
### Printing and memory

- If not everything fits on one bed, as many beds are created as needed; until now the remainder was left beside the bed, where it cannot be printed.
- The feature cache of large models stays bounded; until now it could occupy up to a gigabyte.
## 0.3.1

### Editing recognised features

- Recognised features can be moved, rotated, duplicated and removed: a hole, a peg or a dome — the dome without rotating, as it has no orientation.
- Resizing now works for a peg or a dome as well; until now only a hole could be resized.
- The measured values are already in the fields — no more filling in and re-drilling from numbers copied by hand.
- A moved hole stays the same hole: every fit that refers to it keeps its reference.
- Where an action makes no sense for a feature, it stays visible and says why in one sentence, instead of quietly missing.
- A *Feature* panel opens on the right as soon as you click the first feature and shows what was measured there; it can be detached, closed and brought back under *View*.
- Every number in it can be changed: position, diameter, depth and axis are set right in the field, with no dialog in between.
- A changed number appears as a preview in the view before it takes effect.
- A checkbox *Apply to all of the same kind* changes a whole row of holes at once, with a single step to undo it.
- Two selected features report their distance centre to centre and per axis.
- A hole names its standard size — “measures 5.19 mm, the clearance hole for M5” — and says so when none fits.
- A second hole like the first comes from duplicating it, instead of typing the dimensions again.
- The Delete key removes the selected feature and no longer the whole body.
- A double click on a row in the object list opens what changes it — the matching dialog for a recognised feature, the step with its dimensions for one you built.
- A through hole that no longer goes through after being moved says so — and a countersink that would close its hole cannot be moved.
- Shrinking a hole until it is no longer one brings an explanation instead of a request to file an error report.
- On a face, a button leads to the parts catalogue instead of rows that only say what is impossible there.
### Moving, rotating and selecting

- The move handle sits on whatever is selected — on a hole at its opening, no longer in the middle of the part.
- What is selected is what moves: with a hole selected, handle and toolbar move the hole, not the whole part.
- While dragging, a transparent preview shows where the hole is going and a pale copy where it came from.
- The shadow follows while moving and thereby shows the height above the bed.
- While rotating, an arc shows how far it has turned and that the angle snaps to multiples of 45 degrees.
- Small rotations get through — until now an invisible angle snap swallowed every drag below its step.
- On a face the move toolbar offers only what is possible there and gives the reason on the button, not in a message after the click.
- The *Apply* button is gone: you apply with Enter in the field or by dragging the handle — exactly once, no longer twice.
- A moved part no longer flicks back to its old position when you let go.
- A right click in the object list hits the row you are pointing at, not the two above it.
### View and object tree

- The view has a control scheme of its own, and it is the new default: dragging left pans, right orbits, the pressed wheel tilts, the wheel zooms.
- W, A, S and D fly through the scene, Q and E tilt — the flight passes through a part, while zooming stops in front of it.
- Anyone used to a different scheme picks it in the settings: those for Cura, for Bambu Studio, Orca and PrusaSlicer, for a CAD program and for Blender remain.
- The entry *Fit to view* frames the part you clicked; with nothing selected, the whole scene as before.
- A part below the print bed is visible — it is the bed that is transparent now, not the model.
- Semi-transparent bodies are drawn in the right depth order, whatever order they were created in.
- The view you set is kept, instead of falling back at the next step.
- Selecting and switching in the 3D view run with soft transitions instead of hard jumps.
- From four features of the same name on, the object tree shows one expandable row with their count instead of hundreds of single rows.
- Only what a printer can make is shown: features below half a millimetre are dropped — on a hose holder, 296 out of 1130.
- Fillets with a radius of zero therefore disappear from the object tree.
- A click on a body costs no waiting time any more; on a 63 MB assembly it took three quarters of a second.
- Switching the display and rebuilding the image of large models take a third of the time they used to.
### Drawing and precise input

- Length and width of a selected drawing can be edited; the drawing follows the changed number together with its dimensions.
- A dimension set by mistake can be undone on its own, instead of only together with all the others.
- After extruding a sketch, the dialog also offers the way back to cutting it away.
- A typed dimension counts as typed: 0.1 no longer becomes 0.166667.
- The units dialog asks for millimetres and shows a number instead of “nan”.
- The chamfer field is called width, and its message speaks of the width too, not of a radius.
- A click in a slider's groove puts it where you clicked, not one page further.
- When measuring, the target point snaps to the model's edges and not to lines that are not in the picture.
### Opening, saving and exchange files

- The first model of a project sits centred on the print bed instead of wherever its file puts it; every further one keeps its position.
- A broken file is refused when opening, instead of being accepted and ending up in the project when you save.
- The refusal names the reason — empty, truncated, not an STL, not a 3MF, without triangles, with unusable coordinates — and offers *Choose another file*.
- An interrupted download of a model file is recognised as such.
- Files over eight megabytes are read with a loading indicator and progress, instead of leaving the window unresponsive for fourteen seconds.
- A file name reaches the disk the way it was typed — with spaces, accents, brackets and a plus sign.
- A model can be saved as 3MF without Solidon's print settings, for when it should reach the slicer unchanged.
- Where STEP is impossible for a mesh, the refusal offers *Save as 3MF* right away.
- A model with too fine a mesh gets *Reduce triangles* as a button on the finding, not just as advice in the text.
- A finding that affects several bodies can be fixed for all at once — with a choice of which, and one Ctrl+Z for the whole action.
- The command *Auto Split* says when a cut leaves an open surface, and a cut through an editable body no longer leaves the stage empty.
- Scaling a part below what the machine can make now raises a finding; until now there was one only for too large.
- Custom parts carry the same warning notice as the ones supplied.
### Printing, slicer and filament

- The print dialog shows the profiles that match the selected printer, instead of a stock of 1001 entries.
- For an Elegoo Centauri Carbon that is four, with the right one preselected.
- Changing the printer in the project brings build volume, nozzle and start code along — a Prusa project no longer gets the Elegoo's machine.
- The slicer is given the machine details and returns a print file, instead of aborting with “not compatible with printer”.
- If the slicer is set to a different printer than the project, Solidon says so instead of quietly accepting it.
- The notice about a missing profile names the printer it is about.
- The filament list stays empty until a machine profile is chosen and gives that as the reason, instead of offering 5962 spools.
- The filament selection can be filtered by manufacturer, material and the values a profile brings.
- Where Solidon adds a brim, it states which part needs it and why.
- What the machine cannot do is stated on every field affected, not on just one.
- Recommendations from the report that the slicer does not accept no longer promise an effect.
- Objects of different materials end up on separate print beds — the TPU seal no longer on the bed of the PETG housing.
- The printing notice gives advice instead of pointing to clause numbers of the licence agreement.
### Messages, buttons and information

- Locked buttons now say on the button what they are missing — by mouse, by keyboard and for a screen reader.
- Among them are *Slice* and *Open in slicer* without a slicer set up, *Insert* in the parts catalogue and *Create* in the model dialog.
- Refusals no longer end with the sentence alone, but with the way out.
- An unexpected error is explained in the language you have set, instead of reciting an internal English text.
- The About dialog names who is behind Solidon and who answers feedback.
- A link to an older release leads to the current one instead of an error page.
- The Windows installation now completes on machines where it used to abort with “corrupt file”; in return the setup file is 23 megabytes larger.
### Chat and model support

- If a reference to a feature is ambiguous, the chat stops, highlights the candidates in the view and asks — naming the body each one belongs to.
- When the chat arranges objects on print beds, the result is visible in the view afterwards.
- A finding about an assembly points at the body it concerns and carries its action; where none is offered, it is a plain note.
- The chat knows the new actions on recognised features and carries them out on request.
## 0.3.0

### Getting started and orientation

- Four guided introductions explain the main routes from a first design to a printable result.
- The start screen now makes full use of smaller and narrower windows, with no clipped cards or hidden content.
- Recent projects appear before the introductory tours, making them quicker to reach.
- The start screen no longer moves the selection unexpectedly and is fully usable with mouse and keyboard.
- The *New*, *Open* and *Examples* entries are more clearly organised and explain where they lead before opening.
- Feedback and voluntary support are available directly from the start screen and work with the keyboard and assistive technologies.
- The chat remains usable even with a low window height: the input stays fixed at the bottom while the content scrolls.
- The top toolbar remains visible with open projects and narrow windows instead of slipping out of the workspace.
- A new drawing example leads directly into the sketch workflow and complements the existing example projects.
- The start screen has a *Open model …* button, and the drop area can be clicked as well.
### Interface and controls

- Menus have clearly visible headings and consistently aligned icon columns.
- The command overview aligns shortcuts and explanations cleanly, making long entries easier to scan.
- Extensive dialogs use consistent columns and field widths.
- The former combined page for adhesion, retraction and filament is split into smaller, logically named settings areas.
- All 56 print settings can be searched by their visible English labels.
- Search also recognises 146 common slicer terms, including *perimeters* and *wall loops*.
- Number fields respond reliably to arrow keys, step sizes and rounding without changing values unexpectedly.
- Sliders have a consistent look with an easy-to-grab handle.
- The accent colour is reserved for the main button; the active tool is marked at its edge, and inactive controls recede visually.
- Very short calculations run without a flickering indicator, medium ones show a wait cursor, and long ones add progress and cancellation.
- Tool hints stay on one line where space allows and wrap in a controlled way in narrow windows.
- Thumbnails in the object tree are large enough to recognise the actual shapes.
- The filament list scrolls independently; *Add filament* and *Print values* remain reachable even with many spools.
- Warnings and errors remain readable without conveying their meaning through text colour alone.
- Disabled selection fields are clearly distinguishable from active selected fields.
- A 3D mouse (SpaceMouse) moves the model on all six axes as soon as it is plugged in; one device button fits everything into view.
- The build plate can be hidden with one click or Ctrl+Shift+D and stays hidden until it is needed again.
### Drawing and precise input

- Circles are entered by diameter, so an M3 hole can be created directly as 3.2 mm.
- A diameter constraint remains an editable expression after solving, saving and reopening.
- Dimensions can be edited directly with a double click, avoiding the previous lengthy selection path.
- X, Y and Z position, angle and scale can be entered directly in the movement toolbar.
- Exact input creates the same undoable action as moving with the mouse.
- Multiple selected bodies use a shared centre for exact rotation and scaling.
- Escape steps back by exactly one drawing level: current line, current tool, then the entire sketch.
- Redo now also works while a sketch is open.
- An empty sketch shows a clickable hint that opens the ready-made basic shapes.
- The basic-shapes button is named after what one click does. The remaining shapes are behind the arrow beside it.
- The section tool opens inside the body instead of in an empty view outside the model.
- Front, side, top and opposite views snap reliably to all six axes.
- The pull handle remains visible with a flat or angled camera and shows a useful measurement.
- The measurement tool ends a measurement with visible feedback instead of apparently losing the result.
- While pulling up, the dimension sits right on the wireframe, and after releasing every value stays editable in the dialog.
- Dimensions while drawing follow the grid, not the pointer — you see the size you actually get.
- Circle sizes can be switched between diameter and radius right at the field; the choice applies in sketches and dialogs and is remembered.
- A circle with a fixed centre and a dimensioned diameter counts as fully determined; the status line no longer reports a missing dimension.
### View, history and shape editing

- Multiple selected bodies can be moved together.
- Multiple selected bodies rotate around a shared centre while preserving their spacing.
- After rotation, bodies can be placed neatly back on the print bed within the same action.
- Consecutive movements of the same body are combined into one understandable history step.
- Related actions appear as an expandable entry instead of overloading the history with individual lines.
- One continuous user action can be completely reverted with a single Undo.
- History entries show their type and a unique step number.
- Downloaded and imported models can be cut immediately.
- Selecting a report finding reliably goes to the affected location, body or matching history step.
- When jumping to a finding, the camera frames the target instead of ending in a grey close-up.
- Named faces and findings move with their body during arrangement and placement.
- Brush modelling reports when strokes miss the model or produce no printable change.
- Text on a side wall sits level and upright instead of at an arbitrary angle; on top and bottom faces the set angle still decides the direction.
- If lettering ends up inside the body instead of on it, the operation says so and names the way out: click the face the text belongs on.
- Hollowed bodies keep the requested wall thickness on slanted and curved faces too.
- A deliberately enlarged hole keeps its name and its fits instead of counting as lost in the report.
- Spheres with very many segments stay a manageable mesh instead of twenty million triangles.

### Custom parts and exchange files

- Custom parts can be saved as local .solidon-part files and added back to the catalogue.
- Part files can be opened, dragged in and imported through the operating system file association.
- The file name and extension make it immediately clear that a file belongs to Solidon.
- Import, sharing and the local library use complete interface text in all six languages.
- Before saving, a custom part can be built from multiple editable steps and values.
- Sharing offers a choice of unrestricted use, attribution, or attribution with share-alike terms.
- When a custom part has been named locally, that name takes precedence over an imported name.
- Origin and sharing terms remain traceable when exchanging a part.
- Snap fits, hinge eyes, pegboard hooks and feet have stronger transitions without enclosed inner surfaces.
- Catalogue cards retain their position and selected face when their previews finish loading.
- The fit ladder labels every step with its own number.
- Exported GLB files stand upright in other programs instead of lying on their side.

### Splitting, printing and filament

- Auto Split prefers load-bearing seams and avoids choosing the thinnest possible weak point.
- The appropriate connector is chosen separately for each seam and stored as a concrete shape.
- Notes about glued joints remain attached to the selected seam.
- Auto Split responds reproducibly to changed requirements and can be cancelled during calculation.
- Orientation search checks only genuinely distinct positions and stays within its intended time budget even for demanding bodies.
- Large 3MF files are recognised and processed faster without changing the resulting file.
- Material, fit and tolerances follow the filament spool actually selected or the occupied printer slot.
- The header shows the material actually in use and no longer offers a second, conflicting material choice.
- When disabled, *Save print file* explains that the file is created only during slicing.
- Repairs already completed in the same workflow no longer reappear as open recommendations.
- Pin bores open at the split with a lead-in chamfer, and the catch of a snap pocket sits at the seam.
- A pin diameter you choose yourself has to fit the seam; if it becomes thinner for that, the report says so.

### Report, stability, platforms and languages
- On Linux in a Wayland session Solidon starts and shows the 3D view; if the system lacks a library for it, the application still starts and names the missing one.

- Similar report findings are grouped without losing their connection to affected bodies and locations.
- Numbers and measurements in the report have complete labels instead of unexplained individual values.
- If a repair cannot be completed, the unchanged original body is restored in full.
- A closed imported mesh is no longer torn open by prematurely removing a problematic triangle.
- Action buttons from the report no longer keep an already closed window in memory unnoticed.
- Bundled parts and activation load at startup without blocking each other.
- The 3D view closes before the window, helping Windows, Linux and macOS windows shut down more reliably.
- On Windows 11 the title bar follows the application's colour scheme; other platforms remain unchanged.
- Standard buttons such as Open, Save and Cancel change language immediately without a restart.
- Automatically created body and part names switch language correctly even after cached content has already been used.
- Translations and report values are equally up to date in German, English, Spanish, French, Italian and Portuguese.
- A part without findings offers the *Hand over to the slicer …* button right in the report.
- Every analysis map explains on hover what it shows, and the unit question on import names the units in words.
- A part that fills the print bed is read in millimetres without asking.
- Thin ribs next to thick plates are recognised as a thin place, and bridges are measured at their truly free width.
- A part that stands on itself gets no supports from the print bed recommended.
- The print recommendations check every speed, calculate the first layer with its own dimensions, and report a bed or a chamber that stays too cold for the material.
- Stacked lugs each keep their bore, and fine scratches count neither as a bore nor as a pin.
### Chat and model support

- Chat opens with a clear description of its purpose instead of an empty area or technical model terms.
- Technical token counters have been removed from the normal customer interface.
- Identical notes about lost shape details reach the assistant counted instead of one by one.
- The Generate dialog turns text or an image into a model through local ComfyUI and brings it into the same editable scene.
- The bundled TripoSG workflow creates a GLB that is then repaired, scaled and checked for printability automatically.
- Local Ollama and local ComfyUI run one after the other so that they do not occupy the graphics card at the same time.
- After an agent proposal or 3D generation, Solidon unloads local models and releases graphics memory.
- Cancelling removes only the ComfyUI job started by Solidon; other jobs running there remain untouched.
- Before the first use of a cloud model, Solidon clearly shows which content leaves the computer.
- The dialog for additional programs shows only what is still missing and describes the state of ComfyUI in plain words.
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
- The notice about very small loose parts now offers the button “Remove small parts”. Before, it only said that nothing was deleted and left you to find the way yourself.
- Repairs already done during import appear as a note in the report, no longer as a warning. The report used to open in yellow on every other model although there was nothing left to do.
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
