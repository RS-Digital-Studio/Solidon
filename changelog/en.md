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

## 0.6.0

### Operation and system

- The demo now runs until 30 November 2026. Solidon3D 1.0 is planned for 1 December, and your projects are kept.
- On the Mac, Solidon now needs macOS 14 or later. Every Mac from 2018 on can install it for free.
- Solidon now starts on Intel Macs with macOS 26. Version 0.5.3 hung there at startup.
- On the Mac, *Cancel* stops a running answer from the local model at once.
- On the Mac, Return opens the selected entry on the start screen, in *Search functions* and in the report.
- On Linux, input through Fcitx5 and IBus now reaches the text field in the Flatpak and the AppImage too.
- Uninstalling on Windows removes all of Solidon's file association entries.
- Del also works while the *Selection* tab has focus, and it removes several marked bodies in one step. When the key does nothing, the status bar gives the reason.
- Right-clicking bodies offers *Remove object* and, for several, *Unite*. *Hollow out* is also available on a selected face, which becomes the opening.
- The left and right panels can be moved by their handle, docked to an edge or left floating. *View → Panels back to their place* puts them back.
- Panels can also be placed at the bottom left, bottom right and along the bottom edge.
- Tabs can be reordered or dragged into their own windows, also on a second screen. Closing the window or *Return to Solidon* brings the content back.
- Solidon remembers the layout. The windows stay within reach even when a screen is disconnected.
- While Solidon recalculates, the report says *Recalculating …* and shows the previous lines as the earlier state. Until now, old errors looked as if they still applied.
- If the quick calculation fails at a step, Solidon calculates it thoroughly in the same run instead of stopping.
- A finding that says a step had no effect opens that step at the matching field.
- Once you remove a body, the report no longer talks about it, and the history shows which steps leave nothing behind.
- A selected hole no longer falls back silently to its body after recalculation. Until now, Del could then remove the whole body.
- Every function has the same name everywhere. The *Split* tool offers *Split at a plane*, *Split along a drawn line* and *Split into separate parts*.
- On the selected body, *Split automatically …* now sits under *Prepare*.
- In the resting window only *Parts* is highlighted in colour. Red is kept for buttons that discard or delete, and confirmations open with the focus on *Cancel*.
- In sketch mode the *Selection* tab is hidden. The list of constraints shows those of the selected points and lines, plus any conflict.
- In the parameter card, a dimension shows “Not used” only where that is true. The button says how many fixed numbers can be bound to dimensions.
- The error report attaches a crash log only when Solidon actually crashed.
- The tour card is as tall as its steps. A step unfolds with a click or the space bar, and no tooltip bubble covers the view any more.
- When a tour step points at the report, the tour stays visible. The tab is framed, and the step tells you which tab to open.
- Clicking the i next to an action in the *Selection* tab opens the manual where that action is explained.
- Every dimension of a part can be bound to a project dimension with fx, even before it holds an expression.
- After dragging the handle of a preview, no number stays above the view. A number typed during the drag moves the preview, not the selected body.
- After *Repair and try again* and similar ways, the history no longer calls a step that keeps working “deleted”. If the chain stops again, that step is marked.
- The *Filaments* button now sits in the header. It lists the project's filaments and leads to the filament inventory.
- A different filament only changes the colour, on parts and STEP bodies too. The shape is not recalculated for it. Selected bodies show their filament colour beneath the highlight.
- In the *Selection* tab, the filament field assigns only on a click or Enter. Arrow keys and typing just browse, and the mouse wheel scrolls the tab.
- In the translated versions, *New filament* no longer scrolls sideways when the window is shorter than its content.
- Large models load noticeably faster and need less memory, even with a long history and on computers with 8 GB.
- Even in a long history, a new step takes hardly longer to calculate than the first.
- On models with thousands of features, moving and other steps that leave the shape unchanged finish up to twice as fast.
- After reopening a project, the check report still says which free spot an inserted model went to.
- Undo and redo are faster, and memory that is no longer needed is freed right away.
- Repairing and resolving overlaps are up to four times as fast on large models, and exporting as 3MF is considerably faster.
- The workspace appears faster when opening large 3MF files.
- An added model is in view afterwards, even when it lands next to a model you zoomed in on.
- In the part catalogue, *Manage parts* is open as long as there is no part of your own yet.

### Printing and slicer handover

- On Linux, Solidon now also creates the print file with Cura as a Flatpak or AppImage.
- On Linux, the printers of OrcaSlicer, Bambu Studio, ElegooSlicer and Creality Print as an AppImage are offered right away, even if the slicer has never been opened.
- The print dialog offers the printers of the selected slicer, like *First steps* and *Settings*. A printer taken over this way stays with its slicer.
- In the print dialog you can switch the slicer as in *First steps*, also via *Choose program …* for one that Solidon does not find by itself.
- A printer from Solidon's list and the same one from the slicer count as one device. The print dialog picks the slicer profile with the right nozzle, and the print file carries the start code.
- Without a saved slicer profile, export and main window use what the print dialog suggests for the printer, including the manufacturer's machine and process.
- Only slicers Solidon works with are offered, plus resin slicers such as ChituBox and Lychee. Bambu Studio as an AppImage now counts too.
- Start code and build volume come only from exactly your printer, not from another model of the same series.
- The print dialog matches the slicer's profiles much faster, when opening and after every slicer change.
- A 3MF export only rereads the slicer's profiles when something changed there, which makes it considerably faster.
- The estimated print time is closer to the slicer's, much closer for parts with supports.
- Whether supports and skirt fit on the bed is now measured only under the overhangs. Parts near the edge no longer get a needless warning.
- Accepted suggestions hardly leave any overhang that needs support without it. *Keep channels clear* now only blocks space a support could never be removed from.
- Where supports under small overhangs rest on the model, Solidon suggests tree supports. They leave fewer marks there.
- For small tips, Solidon suggests a lower *Minimum slowdown speed* so they do not go soft. The setting reaches every slicer.
- Narrow rims that hold up on their own stay free of support with *No support under rims*. Prints need noticeably less support that way.
- Supports come off more easily and cleanly: the gap follows the material and layer height of each part, even with several materials on one plate. The interface follows the surface above.
- Where a support stands on the part, Solidon also suggests an interface layer below it so its foot leaves no marks. Under tree supports only with slicers that print it there.
- Under tree supports and next to a prime tower, Solidon suggests the support gap in whole layers, the way the slicer prints it.
- Under a large flat underside, Solidon suggests grid instead of tree supports, and hybrid where fine details need support too. For tall tree supports, Solidon suggests two walls.
- If a suggestion in the print dialog applies to some parts only, its row and field also name the parts that get a different value with it.
- With Cura and grid supports, the support gap follows the material: exact on top, in whole layers below. Where Cura rounds up, the field shows the printed value.
- Under Cura's tree supports, Solidon suggests a top interface layer, because without one Cura leaves an extra layer of air.
- For PLA, Solidon suggests more clearance from tree supports beneath many fine tips. This leaves less residue from the tree tips there.
- When many small overhangs need supports together, such as a chin with a sloped underside, the check report now names the spot.
- A narrow rim that holds up on its own no longer counts as a long bridge, even next to another overhang. The check report no longer warns there, and Solidon asks for no supports for it.
- Over a channel, the check report no longer recommends a support that could not be removed from it. It names the channel and a transition below 45 degrees.
- For PETG, Solidon suggests full cooling at the support. It then comes off the part more easily.
- New in the print settings: *Interface layers below*, *Interface gap* and *Full cooling at the support*.
- The *Gap above* field is now called *Gap above and below* and applies to both sides of the support.
- If the slicer refuses filaments whose temperatures are too far apart on one plate, Solidon now names the reason and the way out instead of only saying that no print file was made.
- In the print dialog, printer, filaments and quality stay fully visible even with enlarged text. Long labels wrap instead.
- The report calculates faster and needs less memory.
- On Linux with Flatpak, Solidon now reports a slicer crash as a crash instead of only saying that no print file was made.
- Even for printers that PrusaSlicer or SuperSlicer do not know themselves, both estimate the print time with the accelerations handed over, and the file names the material of the spool.
- Even on a fully loaded computer, Solidon gives the real reason after stopping a slicer instead of a timeout. A finished print file is used.

### Threads, holes and standard parts

- Threads now come in any diameter up to 1000 mm, whether with *Printable thread*, in a hole, with *Create screw* or *Create screw lid*.
- Regular holes can now be created and plugged again at diameters up to 1000 mm. Large holes and countersinks keep their round shape.
- Screws, nuts and washers are available to ISO from M1.6 to M64. For other sizes, *Custom size* derives the dimensions from the neighbouring sizes and says so.
- With *To fit the hole*, *Pin for hole* builds the counterpart: a flush countersunk head for a countersink, an external thread of the same size and pitch for an internal thread.
- On a printed internal thread, the selection offers *Pin for hole* directly.
- If a separate part sits in a cavity such as a hole, slot, countersink or thread, even tightly or sticking far out, the actions say so. Until now it was merged or cut off.
- New is the *Threaded stud*, a headless threaded rod or stud with a chamfer at both ends and the same printable thread as screw and nut.
- In holes of parts such as the screw hole, the heat-set insert and the nut trap, *Pin for hole* also builds the matching pin. If the hole does not lie in the body, it says so.
- Placed by hand on a face, the nut trap cuts its pocket into the material. Until now the pocket sat above it, and only the screw hole was drilled.
- The nut trap's screw hole goes exactly through the part, even a thick one. Until now it ended 10 mm below the pocket or drilled into the opposite side across a gap.
- Laid in from below, the nut trap's pocket sits under the face, its slot leading down to it. Until now it sat half above, with the screw in the face.
- If the hole of a part does not go all the way through, it is now called blind. Until now it was called through.
- If the wall is thicker than entered for a *Cable gland* or *Hose barb*, the step says so and opens the wall thickness. Until now the passage silently ended in the material.

### Parts

- Parts that are a piece on their own, such as cable clips, ribs or nuts, are created without a selection as a body of their own on a free spot of the build plate, even in an empty project.
- Your own parts are created as a body of their own in the same way and do not attach to a body already in the project.
- With *Save selection as a part*, the selected body comes with exactly the steps that build it. If a second body would come along, the dialog says so before saving.
- Wall mounts, pipe clamps, profile clamps and holders take every screw from M3 to M64. If a size does not fit the other dimensions, the part says what to change.

### Editing and sketching

- With *Move feature*, the feature's material travels along as it is and the old spot is filled cleanly. Where that is not possible, the selection says so straight away.
- On beads and grooves, the selection offers only what the operation can actually do.
- If a fillet sits next to a wall, *Apply draft angle* says before calculating that it is in the way and names *Remove feature* as the way out.
- When you cut away part of a body, chamfers, threads and nut pockets of parts that lay inside it go too.
- In *Create lid* and *Create screw lid*, an empty field for the opening height means “Top edge”, and 0 is the height of the bed. Older projects keep their opening.
- A sketch solves the same on every computer and in every position, also while dragging, and an angle constraint no longer flips the lines over. Older projects calculate as saved.
- A sketch with many separate shapes solves quickly, even with hundreds of dimensioned rectangles or circles.
- If *Curvature continuous* cannot be met while you draw, the sketch editor says so within seconds instead of minutes.
- If two constraints contradict each other, the sketch editor names both instead of shrinking a line or circle to a point.
- A body takes three clicks: *Draw* in the top toolbar (Ctrl+Shift+E), then corner, opposite corner, height. Outwards it joins on, inwards it cuts.
- While pulling up, you can type the dimensions. A double-click on the step opens its dimensions, and under *Kind* it becomes a revolved body or a hole pattern without redrawing.
- From the sketch editor, *Done* leads back into the view, and the next click sets the height. Escape lays the outline aside, Ctrl+Z brings it back.
- If a new step cannot be calculated, the draft stays in the view, and *Repair and try again* calculates it without another click.
- Sculpting offers four tools, each with its own button and shortcut. Strength is a level from 1 to 10, and going over the same spot again no longer piles up.
- The brush fits the size of the body. If the mesh is too coarse for it, *Sculpt* evens out the triangles on the first stroke, and one Ctrl+Z undoes both.
- When mirroring, the plane lies where the body matches itself, even when one part sticks far out to the side.
- Sculpting follows the mouse smoothly, and even a step with hundreds of brush strokes is calculated quickly.
- In *Armature*, every click after the first sets a bone, Enter ends the chain, dragging a joint bends it, and *Done* saves everything without a dialog.
- An armature bends only what hangs on its bones, and the rest of the body stays put. Older projects calculate as saved.
- With Ctrl or Shift you select several edges and fillet or chamfer them in one step. A click on a corner selects all edges that meet there.
- On an exact body, the highlight of an edge also shows the tangentially adjoining edges that *Fillet* and *Add a chamfer* take along.
- What the selection offers for a feature, the operation carries out with exactly those values. What is greyed out, it states in the same words, also via chat and command line.
- As the spot for the copy, *Duplicate feature* suggests one and a half widths beside the original, with a wall in between and never along its axis.
- On a countersink, *Turn feature* suggests the largest angle at which it stays one, and says when a turn only lays the feature onto itself.
- If an action would hit a separate part next to the feature, or a placed feature would touch other material only along a line, Solidon says so instead of damaging the body.
- If a separate part is in the way of a feature action, *Split into separate parts and try again* separates it and runs the action. Ctrl+Z undoes both.
- Splitting into separate parts keeps every printable part, including pins and washers next to a large plate. Only small open surfaces and crumbs the printer cannot reproduce are dropped.

### Generating with AI

- The generate dialog works locally with TRELLIS.2 and FLUX.2 [klein] instead of TripoSG and SDXL. Text first becomes an image, and the image becomes the model.
- Before downloading, the setup names the licences and sizes of the models. It removes Solidon's old TripoSG setup and says beforehand which folders those are and how large.
- Thin walls, for example on a vase, arrive closed and with thickness.
- The assistant replies in the language you write in.
- With a local model the assistant has as much room as with a hosted one and handles tasks of up to twelve steps.
- Generated models arrive closed more often. Where faces only touch, Solidon separates them, and it smooths small folds in the surface instead of reporting a self-intersection.
- If an attempt already fell apart while generating, the dialog says so before you take it and offers *One more attempt*.
- If a generated model is only a thin skin around a cavity, the dialog says so before you take it and the report afterwards, each with the way to a new attempt.
- Before downloading, *Set up the chat* and *Set up ComfyUI* say how much graphics memory and disk space a model needs and whether this computer has it.
- On a Mac, *Set up the chat* suggests a local model that fits into the shared memory and says when a key for a hosted model is the better choice.

## 0.5.3

### Operation and system

- On the right, a card holds the tabs *Selection*, *Report* and *Chat*. New warnings no longer bring the report to the front; its tab shows them with a symbol and a count.
- At the top of the window, *Search functions* (Ctrl+Shift+P) finds any function. The map of functions follows the order of the menu bar.
- In the selection, a feature has one action open at a time. The others stay collapsed and show their values.
- Operation dialogs show at most four fields and one sentence up front. Rarely changed values are under *More settings*, limits under *When to avoid it?*.
- A zero with a meaning says in the field what it does, such as “automatic”, “none” or “from material”.
- All dialogs share one layout with flat sections and a common edge for the labels, including the settings, the AI dialog and activation.
- The report shows the findings first, with a line of status and counters above them. *Export …* sits next to *Hand over to the slicer …*.
- Findings, tour steps and hints are shorter. Where a button offers the action, the sentence no longer repeats it.
- The *Rebuild model* action sits on the selected body.
- The start screen shows the four ways to begin in large at the top. *First steps* asks for language, slicer and printer and collapses the rest.
- The part catalogue shows a picture and a title on each tile. On a hole, *Matching parts …* shows only what belongs in a hole.
- The dialog *Save selection as a part* shows one row per dimension with its default and limits.
- On Windows, Solidon's own mouse pointer clicks exactly at its tip again. Until now the click landed a few pixels off.
- Searching the manual no longer stops with an error when one more character finds no match.
- If you undo or delete a step while *Edit this step* is open, the dialog closes and tells you so.
- A rare freeze of the application during the print check is fixed.
- On the Mac, sentences that name a shortcut use the Mac keys ⌘, ⇧ and ⌥.
- On the Mac, the delete key removes bodies, features, history steps and lines in a drawing.
- On Linux, the redo shortcut that the tour and hints name now also brings a step back.

### Printing and slicer handover

- New is Anycubic Slicer Next with all 39 Anycubic printers, on Windows, macOS and Linux.
- On Linux, Solidon finds OrcaSlicer, Bambu Studio and PrusaSlicer installed as Flatpak, with your printers and profiles, also from Solidon's own Flatpak.
- Slicers installed as AppImage on Linux also offer the vendor printers you have set up in them.
- On the Mac, Solidon now also creates the print file with Cura. Until now it only found Cura's window.
- Creality Print 7 brings its own printers and the one you selected last.
- The printer lists name each printer once, without nozzle variants. You choose the nozzle in the print dialog.
- A nozzle chosen in the print dialog is kept when you save the settings afterwards.
- If you change the nozzle for PrusaSlicer or SuperSlicer, the slicer gets the matching printer profile with it.
- Solidon offers more printers, including ones whose profile names neither bed nor nozzle, such as the Creality CR-20 and Anycubic i3 Mega in PrusaSlicer.
- The print dialog shows slicer, printer, nozzle, filaments, quality, infill density and supports up front; the rest is under *More settings*.
- Each reason for a suggestion in the print dialog fits on one line. *Save print file* appears as soon as there is a print file.
- Parts that are wider at the top than at the base no longer get an edge warning when brim and skirt stay on the bed.
- Accepted supports now reach bridges at fine layer heights too. Until now *Keep channels clear* could remove them there entirely.
- If supports are switched on but none arrive in the slicer, Solidon says so after slicing and names the way out.
- OrcaSlicer and ElegooSlicer now produce the print file even when a manufacturer profile contains values they reject themselves. Solidon names every value it replaced.
- When a profile names a tree support tip narrower than the support line, Solidon widens it so the slicer computes with supports.
- If a slicer applies a setting differently, the notice names the field and both values and leads to the print dialog.
- On Linux, Solidon also offers PrusaSlicer and OrcaSlicer from the package manager together with their manufacturer printers.
- On a Mac whose file system is case-sensitive, Solidon finds the manufacturer printers inside the slicer's app bundle.

### Holes, slots and splitting

- A thread or heat-set insert in a selected hole no longer stops with “outside the surface”. If the hole is too wide, Solidon names suitable sizes.
- On a selected hole, the view shows only diameter, depth and two edge distances. References are named after their side, such as “Outer edge left”.
- In inches, the sentence above a hole gives its size in inches.
- The preview strip says in one line what changes, with lengths in your display unit.

### Sculpting, text and sketching

- For holders and plates with holes, countersinks and lettering, *Rebuild model* now builds an outline with pockets cut away. If it finds no structure, it says so.
- If you take the section of a converted body into a sketch, its circles and arcs arrive as circles and arcs.
- If a part cannot be converted to faces and edges, Solidon names the reason and a way out instead of ending with an unexpected error.

### Generating with AI

- The AI notice says in two sentences per destination what is sent. Because the text has changed, you confirm it once more.
- The descriptions of the recommended local models are shorter.

## 0.5.2

### New shapes and parts

- New is the basic shape *Add a tube*: outer diameter and height, plus either wall thickness or inner diameter, in one step.
- New is the part *Tab with hole*: a flat tab on any face, with hole and size matching the screw from M3 to M8.
- New is the *Pipe clamp* for common pipes from 15 to 40 mm or any size of your own up to 110 mm, with an M3 to M6 clamping screw and the clearance from your material.
- New is the *Container with lid* assistant: round or rectangular, with a screw, push-on or hinged lid, plus compartments, an insert and shaker holes if you like. All main dimensions are parameters.
- Four holders are made in one step with true faces and edges: U-shaped, round, fork and shelf, fixed with a keyhole, screw holes, a pegboard hook or a clamp.
- New are the *Bayonet lock* and the *Detent dial*, each as a matching pair, and the *Socket sleeve and rod connector* for two to four rods.
- New are the *Hose barb*, whose passage goes straight through the wall, the *Channel joint* for gutters, and *Room floor*, *Room wall* and *Window pane* for push-fit rooms.
- An empty scene shows how to start: box, cylinder, drawing, parts or a file you drag in.
- New bodies appear on the bed instead of at a selected body, and are selected afterwards. On a selected face they attach at the clicked point or centred, and can join the part in the same step.
- Catalogue parts such as a magnet pocket or a screw hole sit where you click on the face. Their distance to two edges stays when the model changes later.
- The *T-slot tongue for extrusion* fits Motedis 20 × 20 B-type slot 6 and 30 × 30 B-type slot 8, with a head shaped like the slot. The three previous sizes remain available as older dimensions.
- In the report, *Rebuild model* rebuilds an imported part, including brackets, coves and countersinks, compares it with the original within the limit you set and applies it in one step.
- The *Profile clamp with liners* starts with the project material in both material fields. Until now both were empty.
- The part search finds the *T-slot tongue for extrusion* under T-nut as well, and its description says how it differs from a threaded T-nut.
- A lid from *Create lid* can get a hinge, printed in place or with a pin from *Pin for hole*, and its collar is trimmed so it opens freely.
- With *Cut counter-form*, an insert gets pockets for tools that lift straight back out.

### Printing and slicer handover

- Preparing a 3MF export can be cancelled. For jobs with several build plates, Solidon reuses calculated layers and suggestions.
- Unused filaments from older projects are no longer sent to the slicer. Profiles stay linked to the filaments still in use.
- Additional models can find a free spot beyond the twelfth build plate. Imported plates keep their layout.
- Additional models with different filaments are placed on separate build plates when the printer does not have enough nozzles.
- When you switch printers or slicers, the previous build plate choice is no longer carried over to the new profile.
- Slender parts move closer to the centre when arranged. You can set the brim gap; a brim touching the part is suggested for small footprints.
- Damaged profiles in PrusaSlicer and SuperSlicer are reported. Solidon then uses its complete set of print settings.
- Print settings for individual parts reach the slicer more reliably. Settings that apply to the whole plate are explained on the affected part.
- If you accept a brim for one slender part only, the other parts keep your own adhesion choice, and the field names the parts the brim applies to.
- With Orca and Prusa, accepting a speed suggestion for a fitted part now slows only the affected parts.
- Even small changes accepted for print settings are now preserved on export.
- Cura now uses the profile’s jerk limits, including separate values for walls, infill and the first layer.
- If Cura has a different printer selected, the handover names both printers and shows where to adopt Cura’s selection.
- Fixed a crash in ElegooSlicer and OrcaSlicer when slicing multicolour models with grid supports.
- After slicing, Solidon also compares support material and model layers for each plate. The report shows the internal estimate alongside values from the print file.
- The material cross-check compares only the printed model. Purge material is shown separately, with a note when the amount cannot be read in full.
- The print time cross-check counts from the first layer using your printer's speeds, supports included, and no longer reports a large deviation for almost every print.
- Layer analysis is several times faster on hollow models and on models with many ceilings, and preserves fine contours. The layer view reuses what the report has already calculated.
- For overlapping parts, print analysis no longer counts enclosed air as material. This also improves the detection of overhangs and required supports.
- On first start and in the settings you now pick the slicer first and then one of its printers. The list has a search field, and build volume and nozzle come from the slicer's profile.
- If you click *Save and start* on first start while Solidon is still searching for the slicer's printers, the application no longer freezes.
- You choose the nozzle in the print dialog from the sizes your printer knows, and the slicer gets the matching profile with it.
- The print dialog asks in the order in which one thing depends on the other: slicer, printer, nozzle, plate, filaments and quality, then the values.
- You can now create print files directly from Solidon with Creality Print 7.2 and 7.3.
- With Cura, Solidon takes over the printer Cura is currently using if you ask it to, including its own nozzle. A printer renamed in Cura is recognised again.
- Cura now slices with the nozzle you chose, also for printers from Cura's own list, and printers with their origin in the middle of the bed keep it.
- Printers whose origin is not in the bed corner, such as deltas, BIBO or Dremel, get the parts where Solidon puts them. Until now they sat at the edge, or the slicer rearranged them.
- Bambu Studio receives the nozzle variant and the temperatures of your spools, all the way into the 3MF file.
- If you choose brim, skirt, raft or *Automatic* in the print dialog, only the settings your slicer receives for it appear, without fields that would do nothing.
- A number outside its limit stays in the field, the limit is shown next to it, and *Slice* waits until it is right. Until now it was quietly clipped.
- Tall, slender parts on a small footprint get calmer walls suggested, at 60 mm/s and with lower acceleration. Otherwise such rods broke off on the Centauri Carbon 2.
- With Cura, the report names the parts that only get such values along, because Cura takes them for the whole plate only.
- Solidon now suggests *Outer wall first* only for the part that needs it, and never for one with supports.
- In the quick search too, *Orient for printing* checks whether a part stands securely. If one cannot stand securely anywhere, the others are still oriented and the report names it.
- Every part goes onto the first plate with room for it when you use *Arrange on the bed*. The mini golf set now needs four plates instead of six.
- If you drag a body in the view onto another bed, it ends up on that bed's plate.
- When another model joins, whether from a file, a download or generated, the view shows the plate it lies on.
- Another model goes to the free spot closest to the middle of the plate instead of the back left corner.
- After the first *Open in slicer …*, Solidon no longer recalculates the history.
- The cross-check with SuperSlicer no longer reports a skipped start code where none was skipped.
- SuperSlicer no longer crashes on round parts: it no longer receives the scarf seam it does not know.
- SuperSlicer receives grid supports with an explanation when tree supports were chosen. The Nearest seam choice arrives without a false warning.
- TPU now selects the matching filament profile and start settings in PrusaSlicer and SuperSlicer. If no profile is available, Solidon identifies its own material table as the source.
- Cura respects acceleration limits and reports reduced custom values. Solid infill uses the infill speed; only the top surface uses the surface speed.
- Cura takes the minimum fan speed and the layer time threshold from your printer's profile. Until now the fan came on in the first layer, where it should stay off.
- Chamber temperatures reach the correct slicer field. Printer profiles without controlled chamber heating now explain why the setting has no effect.
- The Lines infill pattern reaches Bambu Studio and Creality Print as lines, without being replaced by Grid or Cubic.
- After slicing, Solidon also reports settings discarded by PrusaSlicer or Orca-based slicers. Changes to brim, wall order and support type are detected too.
- The filament preselection takes Generic or your printer's brand instead of a third-party special filament, for example Generic PETG instead of BETA PETG on the Bambu A1.
- On STEP surface models too, for turns of almost 180° and on partly recognised faces, *Orient for printing*, *Rotate* and *Move* now work. The body stays exact.
- A slower outer wall now also applies to small perimeters such as holes and stems in PrusaSlicer and the Orca family.
- PrusaSlicer and the Orca family now use the support density you set. The field starts at 1 %. To print without supports, choose “None”.
- For multicolor prints in OrcaSlicer, ElegooSlicer, Bambu Studio and Creality Print, the prime tower now starts at a position suited to the bed size.
- Oversized parts are reported before the slicer starts. If no arrangement fits all parts on one plate, you can choose to arrange them across several plates.
- Special characters in project or user names no longer prevent slicing. Cura can now read models with Turkish or Chinese names too.
- Solidon arranges overlapping parts on the bed before slicing with PrusaSlicer or Cura and tells you if it cannot find a suitable layout.
- When PrusaSlicer or SuperSlicer reports an empty first layer, Solidon names the part and offers to place it on the bed or open the relevant print settings.
- Warnings from PrusaSlicer and SuperSlicer appear in the report even after successful slicing, an empty layer as an error. The raft gap can be set on its own.
- If the slicer splits one plate into several print files, Solidon now says so and offers to rearrange or export. Until now it quietly took only one of the files.
- The top of the report says whether the handover is ready, needs a decision or is not recommended, and what is still unchecked. A part without findings no longer counts as ready to print by itself.
- A selected finding names its consequence for the print, and every offered action says what else it changes.
- After an export or *Open in slicer …*, Solidon reads the file back in. The record in the report names files, print target, material, print settings and whether the file matches the job.
- Exported as 3MF from the command line, a single-colour body keeps its filament when the file is opened again.
- For print settings on individual parts, the command line names which parts they are and which value they get.
- If you accept supports for a long bridge over the part itself, they now reach it there. Before, “From the bed only” came along, and several slicers printed the bridge without support.
- Small parts lying flat, such as screws, no longer get supports suggested where a cut edge wrongly showed a floating spot.
- If a part runs out at the top into an edge the slicer does not print, Solidon no longer reports a cut-off model after slicing.
- If a part's first layer is narrower than one line, the message after slicing names wall lines and a raft as ways out.
- SuperSlicer keeps Solidon's arrangement and no longer pushes parts to the bed edge; the skirt stays on the bed.
- If a part only fits the bed turned at an angle, it goes turned to OrcaSlicer, Bambu Studio and ElegooSlicer; if Creality Print lacks the margin for it, Solidon says so beforehand.
- Solidon only suggests a brim as wide as the bed leaves room for.
- If the rim around a part reaches into an exclusion area of the bed, the check before export says so.
- If the paths of two parts, or of a part and the wipe tower, cross in the slicer, the message says so and offers ways out.
- If the brim is set to automatic, Solidon warns before export when it could grow past the bed or into an exclusion area, and offers a fixed brim width.
- Supports and skirt at the bed edge count in the check before export, with the first support layer expansion the slicer profile gives.
- STL files exported from STEP parts contain no triangles without area.

### Holes, slots and splitting

- The angle of a slot on an imported hole points in the expected direction and stays that way when you change the fineness.
- A slot in a side wall facing left or right can be shortened, narrowed and turned. Projects from earlier versions keep their slots until you change the step.
- On STEP bodies, a slot in a slanted face no longer counts as sticking out at the side, and a second drag on a slot that runs into a step no longer fills the body up.
- A slot through a slanted or chamfered plate shows its full depth on STEP bodies, and its copy beyond the edge reports the same on STL and STEP parts.
- On a body with true faces and edges, a part placed after a hole sits on the face you chose, and *Create screw lid* also works on the rim of a hollowed-out box.
- Two plates that touch stay one body at a hole and keep their material, whether you pull, change, move or close the hole. A pin above it stays in place.
- Pulling at a hole that passes through two bodies no longer reports the body falling apart where it does not.
- If a hole cuts the body in two, the report says so once, with the number of pieces at the end, and falls silent as soon as the body is one piece again.
- Patterns on cylindrical faces of imported models stay closed when you change them.
- In the history of a STEP body you can reorder steps or insert one before, even when a later step refers to a hole. The reference follows the hole.
- A plain hole or a slot moved or duplicated with a new direction stays exact on a STEP body.
- A detected feature more than a metre from the origin keeps its place when you change it. Until now the field quietly clipped the number, and the hole moved.
- If a step hits a part whose surface crosses itself, it stops and shows the spot. Elsewhere it keeps calculating and warns that the parts could not be joined.
- Even along its mirror seam, *Split the model* cuts a figure cleanly, and the pins sit in place already in the preview.
- If a cut only grazes a wall, *Split the model* names the spot and leads to the cut position instead of failing at the pins.
- Crop now also cuts at an angle: at the top you choose the *Plane* — along an axis with a tilt, parallel to a face, through an edge, or through three points you click in the view.
- A STEP body stays a STEP body when you crop it, with its faces, edges and names.
- A freshly created screw lid is no longer reported as too tight for its neck.
- If a hole cannot be cut cleanly into a STEP body, Solidon drills it into the triangle model instead of passing on a broken body.
- If you chose “Load now”, the pieces from *Split the model* no longer start minutes of recognition either; “Recognise all features” catches up on it.
- Choosing *Split the model* on a summary row of the report for several bodies splits them one after another. Until now only the first was split.
- If a body covers a hole completely or in part during *Unite*, the report says so, with the location and the remaining cavity.
- Circular patterns and *Mirror* take their *Rotation centre* from a body, a feature, a point or the origin. The centre stays fixed even if the body moves later.
- A drag inside the opening of a selected countersunk bore leaves the body where it is, and the status line shows the way to a slot. Until now it moved the whole body.
- When the dimension card of a hole grows tall, the other dimensions stay beside the body, and the handle for moving sits at the mouth instead of deep inside the part.
- When you select a hole you made in Solidon, its diameter appears only in the dimension card in the view. Until now it appeared a second time on the right.
- A direction you enter on the right for a slot also reaches the dimension card in the view, and *Apply* stays available. Until now it fell back to 0° there.
- Solidon recognises cones, including flat and short ones, fillets and narrow faces the same way on more models, whether the model is moved, rotated or scaled.
- A domed top is now a *Curved face* on STEP bodies too instead of a *Fillet*, and STL parts rounded all over show their fillets one by one, like the same part from STEP.
- Letters and curved outlines in imported models no longer show false fillets.
- Solidon recognises each rib, honeycomb or dimple field in an imported file as one pattern, and *Detect features here* combines the cells of a field.
- A small field that Solidon reads only as separate features becomes one pattern with *Combine into a pattern*. Patterns in STEP files are now recognised directly.
- Pieces of an automatic split are numbered in projects from older versions too, and a deleted or disabled cut no longer counts.
- A hole you duplicate, move or repeat along a sloped face stays the same hole on STL and STEP parts, with the same dimensions and messages.
- After *Repeat feature*, a copy on a STEP part no longer drills through to the top, and a coarsely faceted STL hole still counts as going through.
- A thread grows or shrinks with *Change feature* without breaking through the wall, and the mating thread of a thread fit changes with it.
- A printed thread pair passes its fit check: both threads name the size they are built with, and the check expects the clearance of both halves.
- With *Check the assembly path*, parts can also turn, or be inserted first and then turned like a bayonet.
- For a fit, Solidon cuts the same window from both parts as a small sample print and names the clearance.
- A countersunk hole that ends fully inside the material after duplicating, moving or repeating no longer reports that it sticks out over the edge.
- If a copy's countersink reaches past a side, Solidon finds the copy again the same way on STL and STEP parts.
- If you duplicate a hole along its own axis into empty space, the original keeps its name on STL parts, and the copy is called lost as on STEP parts.
- A groove or bead split into two arcs by an opening shows as one ring in the tree on STEP parts, as on STL and 3MF parts.
- Identical features on STEP parts, such as two pieces of one cone surface, keep their names when you drill, duplicate, change a hole or insert a part elsewhere.
- Features that belong together show as a group in the object tree, and chambers and closures change as a whole: inner size, depth, clearance and turning travel.

### Fillets and chamfers

- Rounding a group of edges on a STEP body now rounds the edges that work instead of refusing the whole group. *Show the place* finds every edge that was left out.
- Edges on a wall no thicker than the radius stay sharp, and the report names the radius that fits there. Previously the whole fillet was refused.
- If a STEP body has no edge of its own at a selected location, the report offers *End face editing and try again*. On the triangle model that spot is rounded too.
- If there is no space left for the exchange with the computing process, Solidon still computes the step and says so in the report. Previously it stopped with advice to compute more coarsely.

### Sculpting, text and sketching

- With *On both sides*, *Put text on* also places the lettering on the back, readable from outside. That suits flags, signs and tags.
- Lettering is set more precisely: the letters stand in their place, and curves follow the font instead of losing up to 2 percent of their area at small sizes.
- Symmetry in *Sculpt* mirrors at the centre of the body, also away from the middle of the bed. Older projects keep their shape.
- The sculpting brush only affects the side facing it. Carving on a thin plate no longer pushes the underside along.
- A sculpting stroke on the mirror plane now acts once instead of twice, and just beside it the stroke and its mirror image blend smoothly.
- The skeleton editor shows bones and joint in the view, and a joint sits in the middle of the body instead of on its skin, so the figure bends evenly.
- The sculpting bar now calls the brush value *Strength* instead of *Thickness*, which read like a wall thickness.
- If a sculpting stroke pierces the wall or makes it too thin, the report and the export say so, with *Show the place* and *Undo the stroke*.
- In the window, *Blend together* now computes finely, as long as the body is not very large.
- If a building block such as a keyhole reaches over the edge of its face, even with just its countersink or chamfer, or into a wall behind it, the report says so.
- A typed dimension such as length 40 stretches a sketch only in that direction. The resulting body stays closed and sits on the bed.
- SVG drawings arrive correctly: rotations, shears, rounded corners, ellipses and elliptical arcs are right, and hidden layers stay out.
- The target of *Align to feature* starts out empty, and the first click in the view fills it. *Apply* waits until then instead of quietly putting the body on the wrong side.
- A file in metres that would also fit on the bed read as inches is no longer quietly read wrong. Solidon asks for the unit.
- Another stroke into a freshly dug pit digs deeper, even with a small brush. Until now it had no effect and counted as missed.
- In *Sculpt*, the window shows every stroke just as quickly after many strokes as after the first, and large sessions compute their preview in the background. Until now it got slower with each stroke.
- With *Lock in the state*, Solidon stores a sculpting session as finely as export and printing compute it, and the window stays usable. Until now it stored the coarser view.
- Double-clicking *Sculpt* in the history reopens the session with its strokes. Ctrl+Z takes back a whole stroke, and *Done* changes the same step.
- The menu entry *Create from sketch …* starts drawing straight away, the drawing plane shows its origin, and a double-click in the history reopens a sketch in drawing mode.
- In *Sculpt* and in the skeleton editor, the bar shows wall thickness or overhang as a map with a legend and reports a stroke beyond the build volume. After bending, it says how it will print.
- An applied texture is selected as a whole. The selection panel then offers *Change texture* and *Remove texture*.
- Text follows an arc or wraps around a rounded face, and *Inlay text* sets it flush in its own colour.

### Generating with AI

- Cancelling during *One more attempt* only stops the running attempt. The finished ones remain to choose from.
- Every attempt in the list names its sentence or image and its seed. If your input no longer matches the chosen attempt, the dialog says which one will be applied.
- The image model is now fetched by *Set up image model …* even when the other weights are already there.
- If an error while generating names the setup as the way out, it appears as a button in the dialog.
- While a model is being generated, the window stays usable. The dialog steps aside, and the status bar shows progress, time and *Cancel*.
- The generate dialog states the volume at the size the part will arrive in.
- A generated model is taken back with a single Ctrl+Z. Until now it took three to four.
- If *Apply* is refused while generating, the dialog stays open with all attempts and names the way forward instead of discarding the mesh.

### Operation and system

- On a Mac, Solidon no longer quits shortly after it starts. In version 0.5.1 this happened on every Mac, even without a 3D mouse connected.
- The *Create the dimensions as parameters* tick is set the first time and then remembers your last choice, even across a restart.
- Dialogs open at the size of their content, without empty space, and a size you dragged yourself stays.
- Export, *Slice* and *Open in slicer …* always get the fine calculation, not the coarser view of the window. Fillets and cones reach the file at full resolution.
- An export during a running calculation waits for the new result. Until now the file could still carry the old size.
- When you export only part of the scene, the file dialog and the confirmation name the scope, such as “1 of 2 bodies”.
- The parameter bar rejects a dimension beyond its limit instead of leaving the view empty.
- In the parameter bar every arrow step counts, and the focus stays in the field.
- In the parameter bar the dimensions of two boxes carry their number, and a dimension with its own working range has a slider.
- If a step is waiting for a question, *Apply* stays available and the question appears.
- In the dialog of an operation the labels stand in one column, the fields have the same width, and every switch sits before what it switches.
- Checkmarks in lists are readable in every row, and colours appear as a round dot next to them.
- The command palette explains tools and file actions in a sentence.
- After you switch the parameter, *Generate variants* starts at that parameter's value.
- If saving a calibration fails, the previous values are kept.
- In the example project for the second way, the screw holes follow width and thickness.
- The *What's new* window and the website show emphasis as styled text instead of asterisks.
- All translations use the same words for features, buttons and print terms throughout, and messages use punctuation as each language requires.
- The button that deducts usage from the filament inventory is now called *Deduct*, and hints name actions the way the window does, such as *Even out the triangles*.
- The form of address is consistent: Spanish, Portuguese and French are formal, Italian is informal. Three Spanish and Portuguese messages that said the opposite are corrected.
- While a dialog shows its preview, spaces reach every text field, including the feedback questionnaire and the chat, and ticks and buttons accept the space bar.
- With *Scale*, a body stays standing on the bed instead of sinking below the plate, and the view reframes it when it grows.
- Some findings that refer to a step open it for changing, for example *Change size* after *Fit to size*.
- A summary row in the report such as *Scale down to the build volume* is a single undo step across all bodies.
- Help for an operation jumps straight to its entry in the manual, and the reference names fields and choices as they appear in the dialog.
- When other programs keep the computer busy, *Cancel* stops a long calculation in under a second instead of asking for a restart after several seconds.
- A local language model may take twelve instead of eight steps per request in the chat and so solves more requests made of several parts.
- The selection panel fits its column again, and the size column in the object tree shows the whole size, such as “Ø5.19 mm” instead of “…”.
- On a hole, *Change feature* opens *Change bore* directly with a preview instead of only pointing to it.
- Clicking *Apply* during a running preview calculates the change only once. Until now Solidon calculated it a second time afterwards.
- The difference view hatches what was added and what was removed in two directions, so the two can be told apart without colour.
- When Solidon asks for the unit of a file on opening, the sizes are shown in your display unit and with your language's decimal separator.
- Drop a file Solidon cannot open, say from Blender, and it tells you how to bring it in as 3MF, STEP or STL. G-code goes to *Cross-check G-code*.
- You can open several files in one step. They keep their positions relative to each other, one Ctrl+Z takes them all back, and identical import notes are grouped in the report.
- Above the history, *Before/after* shows every earlier state with a slider. *Continue here* inserts new steps at that point, and your step names stay.
- With *to*, *Move* puts the centre, the bottom centre, a corner or a feature at a fixed position, and *Rotate* turns the body to fixed angles, for several bodies too.
- If you copy the link of a model page, it is already in the field of *Model from the web*, and Solidon shows the way through the browser.
- When a dialog cannot apply, the reason also appears below its fields, not only in the bar above the view.
- After Ctrl+Y, the status line names the step that was redone, as it does after Ctrl+Z.
- Preview images of examples and catalogue parts show height pointing up. Until now tall parts pointed downwards in them.
- Bundled examples open with your printer and material. Until now they were calculated for the generic printer.
- If Solidon cannot save the *Include values* choice, the note appears right at the switch.
- If other programs keep every core busy under Windows, a calculation on a large model no longer stalls for minutes.
- Lengths in messages use the decimal separator of your language.
- After loading a large model, the loading indicator stays until the view shows the model.
- Clicking a line in the report selects its bodies even if the list shifts while you click.
- Fixed numbers can be bound to a project dimension with one click, and the plate picker names the bodies on each plate and shows the chosen one in full.

## 0.5.1

### Printing and slicer handover

- In PrusaSlicer, ElegooSlicer, Bambu Studio, Creality Print and OrcaSlicer the manufacturer's profile applies. Solidon only writes what you change or accept from suggestions.
- The *Standard* quality prints at the manufacturer's speeds and accelerations instead of holding every printer to 40 mm/s. On a Centauri Carbon 2, large parts finish 40 to 50 percent sooner.
- Accepted suggestions apply only to the part that needs them: supports, brim and the values for a fit, in every supported slicer. The print settings name the parts.
- If a part prints standing up without supports, *Orient for printing* leaves it standing instead of laying it on supports. A minigolf set of 16 parts then fits on one plate instead of four.
- If a part does not fit on the bed in any position, the print settings say how much too large it is before slicing and offer *Split the model* and *Scale down to the build volume*.
- Even where parts of a model merely touch, *Split the model* works, and the connectors sit the right way round in their holes at every seam. Before, the report showed collisions there.
- Solidon takes the overhang angle from your printer's manufacturer profile, 60 instead of 45 degrees for Elegoo, Bambu and Creality. Chamfers and gentle slopes no longer get needless supports.
- On round outer walls Solidon suggests a *Scarf seam*, in every supported slicer. The print takes 2 to 4 percent longer as a result.
- If your slicer works out the brim itself, as ElegooSlicer, Bambu Studio, Creality Print and OrcaSlicer do, Solidon suggests none of its own. The slicer's brim gives tall parts more rim.
- The *Fine*, *Draft* and *Strong* qualities now choose your slicer's matching process, for example “0.12mm Fine” for *Fine*.
- The print settings show what will be printed: the manufacturer's profile is the basis, and your own values are marked and can be reset one by one.
- You choose the build plate in the print settings, and the bed temperature follows it. If the manufacturer does not approve the plate for your filament, Solidon says so before printing.
- Without *Apply suggestions*, no part gets a brim unasked any more, neither on export nor when handing over to the slicer.
- New suggestion *Keep channels clear*: once applied, the handover blocks supports in the channels in every supported slicer. The Cura window receives the block and the per-part values too.
- A ceiling over a water channel or tunnel no longer draws supports onto the model. If nothing else needs supports on the model, Solidon suggests them from the bed only.
- The print settings show their suggestions faster, on the drill holder after 4.3 instead of 7.6 seconds.
- Projects from 0.5.0 print at your printer's speed. Whatever you had set yourself in them is kept.
- The first-layer speed now also applies to its infill. Before, the slicer laid the bottom at the manufacturer's speed, 105 mm/s on the Centauri Carbon 2.
- With PrusaSlicer, printing now starts as it does with Prusa itself, with bed levelling, purge line and printer check.
- PETG now goes to PrusaSlicer as PETG, no longer as PLA.
- In OrcaSlicer every printer gets its own machine and that machine's standard process preselected: the Sovol SV06 no longer the High-Speed version, the Ender-3 V3 no longer “0.12mm Fine”.
- New are the Creality Ender-3 V3 SE and V3 KE. Until now an SE got the values of the much faster Ender-3 V3.
- Identical copies are worked out only once by *Orient for printing*, which finishes the same minigolf set in less than a third of the time.
- The quality levels in the print dialog now appear in the language of the interface.
- Travel speed comes from the printer too: the Centauri Carbon 2 travels at 500 instead of 150 mm/s, as in Elegoo's own profile.
- If you have measured your printer's overhang, the slicer too only adds supports from that angle, as long as the layer height and bead width of the measurement apply.
- The report, too, now calculates overhangs with the angle from which your slicer profile adds supports.
- If a brim, skirt or raft reaches beyond the bed, Solidon says so when handing over to the slicer and offers *Arrange on the bed*.
- If the slicer refuses a part that is too tall, Solidon names both heights and offers *Split the model*, *Scale down to the build volume* or another printer.
- If the slicer refuses a part that does not fit its plate, Solidon names the reason and offers *Split the model*, *Scale down to the build volume* and *Arrange on the bed*.
- If Bambu Studio hangs after slicing, Solidon takes the finished print file instead of giving up after five minutes.
- Large models can now be sliced with Cura too. Before, the run ended without a print file, for example on the Eiffel Tower with 313,000 triangles.
- If Creality Print can only slice a 3MF in its own window, Solidon says so and leads to *Open in slicer …*.
- If the first layer has narrow webs, even a few long ones on a large part, Solidon suggests laying it at 50 mm/s. The short lines stick better that way.
- Solidon now only suggests a longer *Minimum layer time* where your profile has none. Before, the suggestion came for almost every part with a chamfer or a tip.
- Where your slicer limits speed by volumetric flow itself, Solidon no longer suggests a speed limit of its own for it.
- If you adopt the values of a filament profile and then change the filament, the values of the new one apply again.
- The first layer now prints lines as wide as your printer's profile, usually 0.5 mm on a 0.4 nozzle. With Cura, the head no longer crawls between them.
- With Cura, printing now begins with your printer's start code, as with the manufacturer. If Cura does not know the printer or the print file lacks the start code, Solidon tells you.
- With Cura, the first layer now uses the acceleration from the manufacturer's profile instead of the full printing acceleration.
- Supports from Cura now follow the factory profiles: connected, with a loose top and moderate speed.
- With Cura, overhanging walls now print more slowly, as with the manufacturer. Prints with many overhangs take up to about 20 percent longer.
- With Cura, infill now prints after the walls, and travel moves avoid supports and retract the filament on long paths.
- The profile for the Cura window now matches the printer set up in Cura. Before, Cura rejected it for some printers or did not show it.
- The print settings no longer offer the volumetric flow for Cura, because Cura does not read it.
- Grid supports arrive at the slicer as a real grid, with the direction changing each layer, instead of loose lines that shift during printing.
- When a part stands on many small feet, Solidon suggests a brim where your slicer does not work one out itself, even if the feet together would have enough area.
- A narrow sloping strip along the outer wall no longer counts in the report as a long bridge.
- Lettering that stands as a separate part close to a wall no longer starts in mid-air in the report, and Solidon no longer suggests supports for it.
- The report now only shows the hint to calibrate your material's tolerances on models with fits. Only there does Solidon use them.
- The handover to Cura transfers the first layers without fan as a ramp-up. A warning only comes when the finished print file really differs.
- After *Scale down to the build volume* the part still stands on the bed. Before, it lifted off, and the report said it was floating.
- If a part only fits on the bed with a narrower margin, *Arrange on the bed* puts it in the middle instead of over the edge, and the report names the narrower margin.
- On large models, *Split the model* finds the seam up to twice as fast, and on multi-colour ones in a fraction of the time. Splitting works as before.
- When Solidon splits a model automatically into three or more pieces, the names are numbered and name the connectors, such as “Wall rail 2 of 3 · Pins and holes”.
- A printed screw, nut or seal from the parts catalogue no longer counts in the report as a fragmented body. It is a part of its own, and that is intended.
- Printed screws and nuts now have play at the head and the seating face too, and stay removable when printed together with the part. Older projects report the change when opened.
- With a countersunk screw from the parts catalogue, a body made of faces and edges stays watertight on export: the part and the screw each go into the file closed.

### Editing holes

- A bore with a countersink on one side and a chamfer on the other can be tilted, moved and duplicated. Before, Solidon declined there.
- A tilted bore or countersink no longer cuts away what stands in front of its mouth, such as a rib or the honeycomb next to it.
- A countersunk bore in a curved face can be moved, including by clicking in the view. After moving, tilting or removing it, the old spot closes flush with the face.
- A countersunk bore with a rounded mouth edge on a flat face can be moved, duplicated and removed together with the rounding. Before, a dip was left behind.
- Blind holes, slots and widenings in a sloping face, and tilted blind bores such as a magnet pocket without a lip, stay fully open at the mouth. Before, a thin skin was left there.
- Moving and duplicating warn when the wall to the neighbouring bore gets too thin or breaks open.
- If a bore runs out of the side of the part after moving, duplicating or tilting, Solidon now says so at stepped places too. A copy that was not created is noticed.
- In thin plates, a moved or duplicated bore from an STL file no longer wrongly reports that it has stopped going through.
- On ribs and in honeycombs, a tilted bore no longer wrongly reports that it runs over the edge.
- After moving, tilting or duplicating, the feature panel shows the dimensions the result really has.
- Drilling, moving, *Change bore* and pulling into a slot leave the model away from the bore just as it was. Recognition afterwards finishes much faster on large models.
- If a bore cut fails unnoticed on a body made of faces and edges, such as one from a STEP file, Solidon notices and computes it again. Before, a broken body could be left behind.
- On bodies made of faces and edges, bore steps are ready in seconds: on a perforated plate from a STEP file, *Change bore* takes 2 instead of about 120 seconds.
- On bodies made of faces and edges, *Cut pocket* no longer returns a faulty body.
- A slot can be pulled shorter. Pulled to its own width, it becomes a round bore again.
- The handle at the end of a slot can be grabbed anywhere in the opening, and it no longer jumps to the pointer on the first drag.
- Slots take their chamfers and their sloped mouth with them when moved or duplicated. Before, the chamfers stayed at the old spot.
- A magnet pocket from the parts catalogue can be moved, duplicated, multiplied and removed, together with the lip that holds the magnet.
- On a magnet pocket, *Change bore* with *Include countersink, steps and narrowing* changes the diameter together with the lip. *Hole diameter only* keeps the opening and warns if it gets too tight.
- Set at an angle to the face, the opening of a magnet pocket, a screw hole or a bearing seat stays clear. Before, a wedge of material stood over it.
- If a magnet pocket or keyhole hanger stands at an angle to the face, Solidon says that its lip only holds on one side and offers *Correct the input*.
- If a part such as a magnet pocket removes nothing at the chosen spot, Solidon says so and suggests clicking the face instead.
- On a magnet pocket with a lip, *Pull into a slot* now declines on bodies made of faces and edges too, instead of cutting through the lip.
- When you put a thread, a heat-set insert or a nut trap on a bore, the dialog names the fitting size at the top and preselects exactly that one.
- On a countersink, *Change feature* cuts the new size as if it had been countersunk that way from the start. Before, Solidon declined or left a thin skin across the bore.
- When parts of a model are stuck into each other, Solidon unites them before computing, as they will be printed. Volume and bores are then right, and the report says so.
- When you widen a bore, the precise preview shows all the removed material, even on large models, with a section view and on bodies with enclosed channels.
- While you type a dimension on a large figure, the coarse preview appears in under a second instead of up to nineteen, and the preview of a bore on it succeeds.
- If a step on an open model can only compute approximately and the volume grows, the report names the deviation and offers *Repair first, then recalculate*.

### Fillets and chamfers

- The edge choice *Horizontal*, *Top* or *Bottom* no longer takes in the rim of a bore in a side wall. If you mean it, pick it on its own; older projects compute as saved.
- On an imported model, the rim of a bore is filleted or chamfered as deep as on a designed part. Before, with large radii the rounding came out up to a fifth too shallow.
- If the size does not fit every edge of an edge choice such as *All* or *Vertical*, Solidon works the edges it fits and shows the others with *Show the place*, instead of refusing.

### Dimensions in the view

- From bore to bore, the dimensions in the view appear in a third of the time. The first click on a feature no longer freezes the window, even on large models.
- Clicking a bore shows no intermediate pictures any more: the selection panel and the dimension card appear in place straight away, without jumping.
- Clicking the arrows on a selected bore no longer keeps the selection stuck: the next bore can be clicked as usual.
- Escape at the dimensions in the view discards the draft and clears the selection, like *Cancel*.
- A click on *Apply* is no longer silently lost, and dimensions you did not type stay exactly as they were measured.
- A bore draft you have started is no longer lost along the way: a click in the report, a tool change or Ctrl+Z first asks you to apply or cancel it.
- Typing a coordinate no longer makes the dimension fields vanish after the second digit.
- On large models, *Measure wall thickness* responds about four times as fast.
- A click in the middle of a countersunk bore selects the bore rather than its countersink, and the dimensions name its edge by side, such as “Outer edge left” instead of “Outer edge 4”.
- With an edge or a distance selected, the selection panel no longer says “No feature selected …”.

### Recognition

- Features are recognised automatically up to 1.5 million triangles. Up to five million, Solidon asks first and names the memory needed and the time on your computer.
- If you decline full recognition, *Recognise all features* in the report or on the command line catches up later. If it takes too long, *Load without feature recognition* loads the model without it.
- On large models, *Detect features at a spot* finds faces where it used to report too many triangles. The spot can also be chosen with the keyboard.
- On large models, *Detect features at a spot* starts searching straight away. Before, it first recomputed the whole model, 40 seconds per attempt on the mausoleum dragon.
- Large models and lattices are recognised much faster: a generated doll's house bed with 1.2 million triangles in 27 seconds instead of 174. Cancel takes effect within a few seconds.
- Copies and rotated or moved parts inherit the features of their original instead of searching for them again. A project with many identical parts is then computed in less than half the time.
- After a bore, a face of a designed body names its current area, and a new bore is no longer missing from the tree when another one was changed before.
- Lettering and struts appear in the tree as rounded sides instead of dozens of fillets with changing radii.
- Outlines made of arcs and lines are recognised arc by arc with their radius. *Convert to faces and edges* is many times faster as a result.
- A stepped pin no longer counts as a thread. Cylinders and bores that this mix-up had swallowed are back.
- The lip of a magnet pocket is called a narrowing in the tree and names its opening. No action turns it into a countersink any more.
- After *Refine edges*, Solidon recognises fillets, bores and lettering just as on the original, even after another bore. Equal roundings keep their names, even after *Move*.
- A pattern around a round grip, such as knurling on a lid, keeps its centre and direction as you keep editing.
- After *Split* and *Cut away*, a divided face keeps its name on the largest piece, and fits on it stay valid.
- Click the rim edge of a bore lying on its side, and it is named “Vertical”, matching how it really stands.
- If a model has more than 5,000 features, Solidon keeps the largest instead of showing none at all. Scaling does not shuffle their names.
- A part with a single feature has the same name in the tree as in the history, such as “Magnet pocket” instead of “Blind hole 1”.

### Importing and repairing

- A large model appears in the view right after import, and its features follow. Before, it only appeared once recognition was finished.
- A 3MF with several plates from Bambu Studio, OrcaSlicer or ElegooSlicer puts every part on its own plate, in its position there. Before, they all landed on one plate, many of them beside the bed.
- A 3MF with several plates that is added to a project keeps its plates and places them after the existing ones.
- A further model goes to the first free spot on the plates, or onto a new plate, and stays there. Before, it kept the coordinates of its file, usually beside the bed.
- A model from *Generate model* is also set down on the bed at the first free spot on the plates.
- A model without colours of its own keeps the body's colour after its holes are closed. Before, it turned grey, and *Convert texture to filaments* made a grey filament from it.
- If a model is missing a piece of bore wall or part of a countersink cone, Solidon closes the gap as a wall, not as a lid across the bore.
- Open seams are closed on import and repair without joining parts that merely touch. An intact model stays unchanged.
- Overlaps are now resolved by *Repair* itself. When the parts of an imported model are stuck into each other, the report offers *Resolve overlaps*.
- A surface without thickness stays open and offers *Give it thickness*. A large opening names its place with *Show the place*, and *Leave open* leaves only that one open.
- After an opening has been closed on import, *Show the place* outlines the whole new face in a colour of its own.
- A part turned inside out next to a hollow body is set right without losing the cavity. A part inside another part's material is reported instead of guessed.
- The report after importing is shorter: findings the result disproves drop out, and where something can be done there is a button instead of advice.
- The mesh defects map shows intact areas in the body's colour so that single defects stand out, and carries *Repair* right in the legend. If there is only one body, the map selects it on its own.
- The search for overlaps now reaches the end on models with fans of narrow triangles too. The mesh defects map and repair then see the whole model.
- A 3MF from PrusaSlicer no longer loads modifiers, support blockers and support enforcers as solid material. A negative volume is subtracted from the part.
- With *Refine edges*, all features stay and up to four times fewer triangles are created: a drill holder at 1 mm edge length in five seconds instead of fourteen minutes.
- A closed model stays free of holes and keeps its filament colours. With too many triangles, Solidon names an edge length that really works.
- The preview of *Refine edges* and *Reduce triangles* is ready in seconds instead of freezing the window, and a length that is too fine is declined right away.
- If a model is too fine for *Refine edges*, the report offers *Reduce triangles and try again* with a number that really works.
- If *Smooth* would turn a body inside out, Solidon says so and offers *Refine edges and try again* with an edge length that works.
- Large assemblies import faster: the repair while importing a pirate ship with 1.2 million triangles takes about 30 percent less time.
- While a large 3MF file opens, the window stays responsive, even while the model is being read.
- If you import a renamed copy of a file you opened before, the body carries the new name. Before, it was named like the first file.
- On large meshes, *Close open surface* computes in seconds: 1.8 instead of 24 seconds at 122,752 triangles.

### Manual and website

- Fifteen guides show step by step, in pictures from the application, how to check, print and repair a model, build, split and label a part, or print in two colours.
- The manual begins at “Where do I start?” and leads from there to every guide. F1 in an operation's dialog opens its guide or its entry.
- An overview picture explains the window: each number in the picture marks one area.
- The search in the manual finds the right page even with everyday words, lists it first and opens it where the word appears.
- The reference names, for every operation, where to find it in the menu or in the selection panel.
- The explanatory pages are a third shorter. Where a picture guide covers their topic, a link to it follows at the end of the page.
- On the website and in the PDF, the manual is organised as in the application, from the first steps to the reference. In the PDF, bookmarks lead to every chapter.

### Operation and system

- Large calculations such as previews and *Refine edges* run in a separate process: the window stays responsive, and *Cancel* works at once. A second Solidon process runs alongside for this.
- While loading and during long calculations, a clock counts the elapsed time even when progress stands still, and the remaining time no longer jumps when a new part of the calculation begins.
- The automatic backup runs in the background and no longer stalls the window, even with large models. If it cannot be written, Solidon says so.
- A model on a slow or unresponsive drive no longer freezes the window when you open it.
- If a file in *Recently opened* has been moved, Solidon says so and offers *Choose another file*.
- A file that could not be read no longer ends up in *Recently opened*, and the next file no longer reports its name while loading.
- A file without a readable model no longer stays behind as the first step, where every further file failed with “The chain stops”.
- Recently opened projects on the start page open with one click.
- With nothing selected, the selection panel offers what applies to all bodies: *Orient for printing*, *Arrange on the bed* and *Check overlaps*.
- After *Split the model*, all parts stand fully in view.
- Every halted step in the report has a button: *Correct the input* opens it with the cursor in the affected field.
- After *Split the model*, the report says in one sentence that the pieces still touch, instead of in over twenty lines, and lines about the old body no longer carry empty buttons.
- A freely drawn sketch without dimensions no longer generates a notice in the report.
- If the report holds only notes, it says “Ready to print” at the top, and a setup note is no longer preselected like a warning.
- Warnings in the report carry a button: *Show the feature* on a fit that does not fit, *Open print settings* on findings about bed, supports, nozzle and brim.
- An error report names folders under your user directory without your username, even when Solidon itself is installed there.
- In *First steps*, your slicer's printer is there as soon as it opens. Before, the suggestion came only after seconds, and *Done* took the generic printer until then.
- After import, the title bar carries the model's name instead of “Untitled”, and *First steps* names slicers by their name instead of their file name.
- You choose the slicer in the print settings above the profiles, even when that section is collapsed.
- A printer you choose in the print settings is also used for the next new project. If your slicer is set to a different printer, the settings offer it with one click.
- If you choose a different printer or slicer, the remembered machine profile of the previous one no longer applies.
- In the parameter bar and in an operation's dialog, a typed number outside the limits is refused instead of being silently cut short, and Solidon names the limit.
- The question before deleting a step names the dependent steps that go with it.
- The history names a changed parameter by its label and shows the value before and after.
- The handle on a selected face now shows only the arrow you move it with.
- Without text, *Put text on* says that the text is missing instead of declaring the preview unavailable.
- After drawing, the previous tab, such as the report, is back on the right. Until now the chat was shown there, and *Hand over to the slicer …* was hidden.
- The *Command palette …* finds operations in every language through everyday words too, such as “copy” or “calamita”. Until now it knew such words only in German.
- When saving with *Save selection as a part …*, Solidon checks the wall thickness of the part many times faster.
- In every translation, *Cut* and *Split* now have different names, keys are named as on the keyboard, and the Italian interface addresses you informally throughout.

### Assistant with a local model

- The model choice also recommends a smaller model for cards from 10 GB of graphics memory and names for each the memory it takes and how well it handles multi-part requests.
- The assistant gets full detail only for the actions that fit the request. That leaves room for history and answer, and requests succeed much more often.
- The local model stays loaded for three minutes after an answer, and the next question no longer waits for the model to start.
- An answer that finds no end stops after a fixed length and is reported as cut off, instead of occupying the graphics card until the ten-minute time limit.

## 0.5.0

### Recognition

- Recognition on imported models is many times faster: a plate with 200,000 triangles and its holes is ready in one second, where a smooth free-form shape used to take minutes.
- Small faces such as the tip of a cam, cut-off holes and mouth chamfers are recognised the same way on a mesh and on an exact body.
- Closed cavities and nested air chambers are recognised as a whole. A hole leading into a cavity no longer appears as a phantom.
- Imported threads are measured: pitch, number of starts, right- or left-hand and nominal diameter. Mirrored parts keep the correct handedness.
- Cones, spheres and rings keep their true dimensions, and the feature panel says where a value comes from: measured, fitted or from the step.
- A mirrored, scaled or patterned part carries its features along. Stale features no longer remain next to new ones.
- STEP files with free-form faces keep their holes editable, even after saving, reopening and undoing.
- After a change, every feature that still exists keeps its name. When two candidates come into question, Solidon asks instead of guessing.
- Clicking a bore on a model with 360,000 triangles responds in a quarter of the time.
- A countersink touching two slots equally stays a cone face instead of vanishing into one of them.
- If a model consists of several shells and it cannot be read reliably whether one of them traps air, the report says so as a warning.
- A closed model releases its memory; before, a few hundred megabytes per model stayed behind.
- A model with many small faces, such as a honeycomb pattern, keeps its bores and fillets. Before, it showed no feature at all.
- A field of 1,400 knobs is recognised in four seconds instead of twelve.

### Patterns

- A honeycomb, a knurl, ribs, waves or dimples appear in the tree as one pattern with pitch, cell width and depth — around a handle too. Before, they were hundreds of faces.
- A pattern can be removed with one click or set again with a new pitch, cell width and depth. The cells stay where they were.
- A texture around a cylinder follows the curve: grooves are equally deep everywhere, and a pattern around the full circumference closes without a seam. The pitch moves to the value that fits.

### Drawing

- Drawing on a chosen part shows only that part in the view; the others stay hidden until *Show neighbours* brings them back.
- Extruding on a chosen face now attaches the new body instead of stopping — before, it never got past the sketch.
- A pocket cuts where you drew it, even when the face is not centred on the part.
- Rounding and chamfering a dimensioned rectangle leaves its dimensions unchanged.
- Drawing with several parts selected asks which one you mean; the target can be switched at any time in the bar.
- Escape no longer discards a sketch you have started.
- An already extruded sketch can be reused for the next pocket, without drawing it again.
- Clicking a face offers *Draw here* and *Draw hole or cutout* directly.

### Editing on the exact model

- Primitives are always created with true faces and edges. The checkbox “Edit faces and edges later” is gone; old projects compute unchanged.
- Hole, slot, counterbore, boss, dome and truncated cone stay exact on an exact body when you move, duplicate, rotate or remove them.
- Beads and grooves can be moved, duplicated, rotated, changed and removed. A thread can be changed and closed.
- A thread gets its counterpart on the other part at the press of a button, in the table size and as one fit.
- Every part in the library builds exactly on an exact body, from the screw joint to the seal groove.
- After a radius change, Solidon rounds the right edge, even when two roundings lie close together.
- When two edges lie at the same place, Solidon asks which one you mean instead of taking one.
- Apply waits until the preview shows the current result. A click on an outdated picture writes nothing wrong.
- Filament colours stay on exact bodies and follow every new meshing.
- Volume and area of an exact body come in milliseconds instead of seconds.
- Inserting a thread took 0.38 to 0.41 seconds in the measured run instead of 8 to 13 seconds. A complete operation created an M6 × 1 threaded rod, 12 mm long, in 0.55 seconds.
- Unite, Subtract and Place on the bed no longer ask whether to convert exact bodies. They stay exact.
- When a bore is moved, no surplus triangles remain at the old place, and a hidden countersink loses none of its volume.
- Repair leaves a clean model unchanged, also on an exact body.
- The counterpart of a thread is built in the background. The window stays usable meanwhile.

### Drilling and dimensions in the view

- A clicked hole shows its dimensions in the view at once: distances to the edges, centre and diameter, with number fields for typing.
- The dimension fields stand next to the part instead of on it, and their lines do not cross.
- The reference of a dimension, edge, centre or axis, can be changed by right-clicking the dimension or by clicking in the model.
- What stands in the view is not repeated on the right in the selection panel.
- After pulling a hole into a slot, the dimensions stay, even when you rotate the view. The knobs for pulling always stand at the chosen hole.
- Choosing a hole could make the 3D view fail on some graphics cards. That is fixed.
- A drag on the handle survives a redraw in the middle of the drag, and a wheel click over a dimension field zooms the view instead of changing the dimension.
- The first Escape while picking a reference only takes back the pick; the typed values stay.
- With “Take countersink and steps along”, the bore can also be moved via the dimensions. Shaft and countersink move together, in one step.
- If Solidon refuses a dimension, the reason stands above the preview instead of just “could not be computed”.
- The dimension fields stay where they were when you change a value. The dimension whose field you type in lights up in the view.
- The slot knobs also work while the bore’s dimensions stand in the view: Apply then pulls the slot — with a new diameter beside it in one step, at the new width.

### History

- A new step can now be inserted before an existing one in the history, not only appended at the end.
- A step in the history can be dragged to another place with the mouse, or moved line by line.
- A step can be switched off and later on again without deleting it; dependent steps rest with it.
- If a later step refers to a feature that the rearrangement has renamed, Solidon follows it and reports so.
- If rearranging the history would stop a later step, Solidon declines and changes nothing.

### Checking and printing

- Resin printers have arrived: two generic devices by build volume are in the printer list, and your own can be added with pixel size and minimum wall.
- A resin project no longer gets advice about nozzle, brim or bridges, and the minimum wall comes from the printer profile.
- The file can be opened in any program, including a resin manufacturer's slicer whose settings Solidon does not know.
- Exact bodies are meshed as finely as a resin printer's pixels demand; the report names the figure.
- Fits check the real bodies in their assembled position. The export can be cancelled beforehand.
- The shape deviation shows which faces of a meshing lie how far from the original.
- When a wall thickness tapers off like a wedge, Solidon says so and advises printing the outer wall first.
- The orientation search stands a grid with a narrow rim on its rim, and a grid of short struts needs no supports.
- The profile for the assistant says the same about the chosen spot as the feature panel.
- The shape deviation of a box with lid computes in a tenth of a second instead of twelve.
- Parts lying apart for printing no longer get a warning about their assembled position. The fit reports only what it has measured.
- The orientation search on a model with over a million triangles takes five seconds instead of half a minute.
- Very small distances appear in the analysis map as decimals, not as powers of ten.
- Shape deviation on fillets and rings is now as precise as on planes and cylinders — and the map computes faster than before.
- The part cooling fan again follows the curve from the printer profile, instead of running at full speed on every layer.

### Importing

- An imported assembly can be placed on the bed as a whole with one click. The parts keep their position relative to each other.
- A glTF without a plausible size is no longer believed to be in metres. Solidon asks for the unit and shows the dimensions for each reading.
- A model with open areas is closed while it is read instead of merely reported: holes in the mesh, reversed faces, edges with three faces. Large openings are named separately in the check report.
- An imported hollowed part can be filled with a lattice: Solidon finds the cavity through the vent hole and says that this is how it found it.
- Reducing triangles no longer tears closed models apart. Where the shape allows nothing else, the report names the number of parts the model fell into.
- Reducing triangles now reaches its target on sleeves, rings and housings with openings as well.
- An imported STEP assembly arrives as separate bodies with their own names and face colours, not merged into one shape.
- Before taking over a STEP assembly, you choose which bodies you need; a mirrored part stays a mirror image.
- STEP export writes names and face colours into the file; a part read back in keeps its name unchanged.

### Operation and system

- Every action briefly confirms its result where you clicked, in addition to the status line.
- A program error leaves a local log that is attached to the support report. Nothing is sent on its own.
- The setup for “Model from text” fetches the missing image model itself instead of pointing you to a folder.
- Solidon starts in half the time.
- With a feature selected, the tooltip remains, and a hint about the handle no longer wipes the last receipt.
- If a step of the assistant halts the evaluation, the proposal takes it back entirely and shows the state before.
- Moving or rotating a model with 200,000 triangles answers in half a second instead of eight.
- Undo answers immediately instead of after two and a half seconds.
- When changing the bore diameter on the perforated plate, the first preview appeared after 0.57 seconds in the measured run, each further one after 0.13 seconds.
- Hollowing out was 7 to 25 percent faster on the three measured models.
- A menu entry and a quiet note in the view lead to voluntarily supporting Solidon via PayPal or GoFundMe.
- The survey card now shows the right colours in the light theme too.

- The Windows application and installer are digitally signed. The signature confirms the publisher and makes later changes detectable.

## 0.4.4

### Editing

- Draft angles now reach every upright side, including the narrow ones, and work on imported models.
- Soft merging leaves smooth side faces instead of frayed edges.

### Selecting and operating

- A spool in the filament inventory can have up to four colours. Bambu Studio, OrcaSlicer and ElegooSlicer receive all colours, other slicers the first.
- A picked edge now shows only the actions that do something to an edge.
- With nothing selected, the way to the building blocks stays visible.
- The search box only appears where there is something to find.
- A divider in an organizer leads to its compartment editor instead of to the actions of its face.
- The dialogue for placing a hole says that you pick the spot in the view.
- In the “Generate model” dialogue the description field keeps its height even when the note about the missing add-on program appears.

### Moving and checking

- Print suggestions arrive much faster: a figure with 2.3 million triangles in seconds instead of minutes, and opening the print dialogue a second time does not measure again.
- An imported spool of another material type that no part used made the slicer abort without a word. Now every spool on a plate gets a complete profile.
- If the slicer has no vendor profile for your material type, the print dialogue says so and uses Solidon’s values — instead of a profile for another material.
- Two bodies can be pushed into each other to unite or softly merge them. Only what ends up beside the build area is brought back.
- When a fit points at a feature that no longer exists, a button leads into the history.
- Orient for printing and Arrange on the bed put parts of different filaments on their own plates so one nozzle does not keep purging. Enter several nozzles in the print dialogue.

### Filament inventory

- A reversal in the consumption history can be undone again — with the same button.
- Changing only a spool’s name or location no longer counts as a new stock count; its records stay reversible.
- After a reversal, “Record without asking” really records a repeated print instead of merely saying “recorded”.
- Purchase and opening dates have a calendar in your language. A rejected spool returns to the dialogue instead of vanishing.
- Importing from the slicer adds a same-named spool of another colour instead of recolouring your hand-entered one.
- If the inventory file cannot be read, one button brings back the last state — Solidon saves it itself on every write.
- The detail page names remaining amount, purchase date and price; the eight-character ID only appears where two spools share a name.

## 0.4.3

### Recognition and editing

- Shallow blind holes, small functional faces and short threads are recognised more reliably. Magnet-pocket floors belong to their bores.
- Resize bores together with their countersinks and entrances while preserving the intended dimensions. Blind-hole floors stay associated even after larger diameter changes.
- Recognise features at a chosen spot on large meshes and edit them immediately. Recognition and editing can be undone together.
- Selection and preview show the complete body. Outlines and labels identify the selected area; unchanged lettering stays free of orange patches.
- Edges can be picked on any body and rounded or chamfered — on imported models too.
- Bores, cylinders and roundings are built from the same points on Windows, macOS and Linux. A project is recognised and edited the same way on every machine.

### Construction

- Organisers gain linked compartment dimensions, individually editable dividers and repeated cells. Tray, rim, floor and foot parts extend the library.
- Hole, slot and honeycomb fields follow a drawn region. Keep-out areas, edge margins and minimum webs are respected.
- Profile clamps comprise two shells and two fitted liners. Round, oval and drawn mating profiles are supported; liners can be replaced later.
- A closed drawing or selected opening creates a seal groove and a separate gasket. Choose materials, cross-section and protrusion; remaining walls are checked.
- Surface patterns reach the face boundary and leave bores clear. Existing patterns can be edited directly through the selection panel.
- Cut away keeps one side of a plane and closes the cut face — for flat back walls and walls at one height. Fillets next to slightly slanted walls can be edited again.

### Import and use

- Select SVG and DXF contours visually before creating a body. GLB and GLTF files retain their correct dimensions and orientation.
- Project dimensions remain effective in part sketches and placement previews. Fit to view includes every visible build plate.
- Filaments can be removed from the shelf. First steps start with the slicer; feedback opens quickly and prepares attachments in the background.
- Delete on a face removes the body and says so; Ctrl+Z brings it back. In a flat view a dragged body follows the pointer, and the chosen face survives the first click of a sketch.
- The local chat gets a larger window and no longer truncates your request.
- The nozzle diameter can be set on the printer. The handover then picks the matching machine in the slicer, even if a different nozzle is selected there.
- Repair closes models that touch themselves along an edge instead of tearing them open further.

## 0.4.2

### Drawing

- Two clicks set a regular polygon: first the centre, then a corner. You choose the number of corners beforehand — three to twelve. A typed diameter stays on as a dimension.
- A slot comes from two clicks on the centres of its round ends; the width sits next to them in the bar. Both ends stay the same size, the flanks stay straight.
- Four new constraints: an angle in degrees between two lines, equal length or size, a point at the middle of a line, concentric for two circles or arcs.
- A dragged point stays at the pointer, and its neighbours follow: a corner of the rectangle takes both sides along, a line stretches the shape. Before, the corner only moved part of the way.
- A clicked rectangle is free: no fixed point, no dimensions unless you type them. A typed width or height stays as a dimension — as in Fusion.
- Shapes from the menu can be moved; the dimensions from the menu entry stay. To change a dimension in the view, double-click its card.
- Fillet and chamfer in the sketch editor: point at a corner, type a radius or a size, click. The rounding stays at its corner when you drag, the chamfer makes a slanted edge.
- When a constraint holds a point in place, the line says which one — and that a right-click on the point releases it. Before, the point just stood still.
- Fixed means fixed: a fixed point no longer follows a drag. Lines that lie exactly level or upright stay that way, even when you drag a corner later.

### Building and editing

- Turning a slot turns it — instead of cutting a second one across it. And editing a slot you pulled yourself changes that step; the history gets no second one.
- An STL you export after “Change bore”, “Move feature” or “Add a chamfer” on an imported model arrives closed in the slicer. Before, the seam tore open when the slicer welded it.
- Name just one axis in the chat — “bore to x = 20” — and the hole moves only there. Before, it jumped to zero on the other two axes.
- Fillet says up front that an exact body allows a smaller radius than a mesh, and what helps then: a smaller radius, or carrying on with the mesh.
- Opening the same file twice gives two names you can tell apart: “holder” and “holder 2”. Before, both bodies were called the same, in the tree as in the check report.
- Messages pointing to the values on the right now name the window the way it is named: Selection. Before they said “feature panel”, and no window is called that.
- The step “Reduce triangles” says so when a part already has fewer triangles than the number you entered — there is nothing to reduce then. Before, it simply stayed as it was.
- The step “Set a pose” without an armature says that the bones are made in the skeleton editor — two clicks per bone. Before, the step silently moved nothing.
- A hole you move, rotate, duplicate or change says so when it runs over the edge of the part — as drilling does. Before, only the result showed in the picture.
- Moving and duplicating a hole with a countersink leave the part’s volume unchanged. Before, up to a cubic millimetre went missing.
- If a step breaks a part into loose pieces, the report says so — with the way back via Ctrl+Z.

### Recognition

- A curved wall — the end of a tab, the floor of a groove — is now called that. Before, it said “Fillet” with an edge that does not exist. Its radius can be changed.
- A bore with lugs in its wall, such as the ring of a bayonet mount, is a bore. Before, it appeared as a slot as long as it was wide, and every action would have removed the lugs.
- A slot with a chamfered rim is a slot; the chamfer belongs to it. Before, one frame listed 126 separate countersinks in the tree.
- A notch or the round end of a tab is no longer a hole, and two pieces of the same round wall appear as one in the tree.
- A piece of cone without a rim of its own is called a conical face. It can be inspected but not edited alone — and every row says so.
- The inner wall of a wheel with spokes is not a hole, and a cup with a hole in its floor is not a through passage. Before, “Move” cut the spokes away there.
- Large models are recognised up to thirty times faster: a clockwork part with 500 arcs took two minutes, now four seconds.

### View and operation

- A checkbox in a dialog now toggles across its whole row — clicking its label works too. Before, only the small box itself responded, and “Open top” in Hollow seemed not to react.
- When a preview cannot show anything, the view says why — for instance “This plane does not divide the object”. If the volume does not change, the banner says so; if it takes longer, that too.
- The step “Split” starts in the middle of the part instead of at its underside. The number stays editable.
- A tool that cannot do anything to this part is greyed out in the menu and says why — “Close open surface” on a closed part, “Split into parts” on one piece, “Fill lattice” without a cavity.
- Assigning a filament shows the colour in the preview already; remeshing and subdividing show the new mesh with its edges. The space bar brings back the before.
- Hollowing a part with holes in its hull now says that the hull is the problem and offers “Repair and retry” — instead of reporting that no computation path worked.
- At the selected feature, what could only fail there is greyed out — “Turn feature” on a countersunk bore, say — with the reason. And the preview says when a question will come on apply.
- A field that does nothing for the chosen base shape is no longer greyed out in the dialog — it appears with the shape that needs it. A rectangle shows four fields up front instead of eight.
- At 150 or 200 per cent screen scaling, snapping, handles and marks reach as far as at 100 per cent again. The pull handle is full size, and a slightly wobbly click stays a click.
- On a large model the preview arrives in under a second instead of several: Solidon computes it more coarsely and writes “Coarse preview” into the picture. Applying is still exact.
- The step “Split along a drawn line” starts in the middle of the part instead of at its underside — like “Split”. Before, the preview only showed that the plane cuts nothing.
- The step “Align to feature” now asks you to pick the second feature instead of explaining a notation to you.
- Startup no longer waits for the graphics card: it is looked up while the window is being built. On machines that took a long time over it, the program stood still for seconds.
- What cannot be done at a feature appears greyed with the reason — the same sentence the operation would have said after the click. The sentences have become shorter.

### Files and export

- A 3MF from the slicer now opens even when its colours cannot be read unambiguously: the model arrives in one colour, and the report says why. Before, the file stayed closed.
- Painted faces from Bambu Studio, Orca and Elegoo arrive exactly as painted — even where a colour runs through the middle of a triangle. Before, that counted as “ambiguous”.
- A text relief from the Elegoo slicer or Bambu Studio in the file stopped the import. The file now opens.
- Modifiers and support blockers from the slicer no longer appear as bodies, and a cut-out (“negative part”) is subtracted — as in the slicer.

### Building blocks and fits

- A block meant for a hole — heat-set insert, nut trap, bearing seat, thread, screw — now sits straight in the hole you selected instead of at the centre of the face.
- Drag a block by its handle in the view and the whole block moves — even from an edge of the keyhole. Before, only that one feature travelled and the rest stayed put.
- Hooks and holes of a block appear on the right as a count — no longer as “2.00 mm”. And after “Change dimensions” the block stays selected, even when it ends up with different features.

## 0.4.1

### Building and editing

- Filleting and chamfering now work on an imported model too: pick an edge in the view, enter a radius or a width. Before, they only worked on a body you drew yourself.
- Offset face and draft angle also work on an imported model, and a recognised rounding can be changed or taken away there as well.
- Offset face moves the face you clicked on. On a stair the other steps stay where they are instead of all moving at once.
- Bolt circle and hole grid are shapes of their own when drawing, with their own sizes — count, pitch circle, diameter. Before, six holes were six circles by hand.
- New is “Add bead”: a round strip along the selected edges — on the outside as a bead, in an inside corner as a fillet weld. An exact body becomes a mesh in the process; Undo brings it back.
- You now pick an edge in the view: first click the body, then the edge. Its length and the Fillet and Chamfer buttons stand on the right. Before, you had to recognise it in a list.
- On a pipe, the inner and the outer rim can be filleted or chamfered separately. Before, both had the same name, and the edit hit one of the two.
- The draft angle leaves the footprint standing even when the part does not sit at zero height. Before, a raised part was tapered at the bottom as well.
- Sweep along a path starts with the right cross-section and keeps openings in the outline — a ring stays a pipe instead of starting out distorted and turning solid inside.
- An inserted pair of counterparts counts as a change: it is saved along and asked about when closing. Before, it could be lost in silence.
- The padlock next to a fixed dimension in the sketch editor is now a drawn symbol with an explanation. On some computers a box stood there.

### Drilling and placing

- When you place a hole, one tick turns it into a slot: you enter length and direction, and the preview shows both.
- A hole that is already in the model can be pulled out into a slot afterwards — the diameter stays as it was measured.
- The slot is widened by the material tolerance over its whole length. The travel a screw has inside stays the one you entered.
- If a slot hangs over the edge at one end, Solidon says so — even when its centre sits deep in the material.
- A slot stands in the object tree as a slot, with its width and its length — also in a model you opened that somebody else drew.
- An existing slot can be pulled longer afterwards, and its direction stays where it was.
- A selected hole or slot is set right in the view with “Set in the view”: a handle to move and turn it, knobs to pull it, dimension lines to edges and centres.
- Only “Apply” on the right makes a step of it; Escape discards. A pulled slot shows its length meanwhile and keeps its shape when you move it at the handle.
- An empty coordinate field now means “leave the hole where it is”. That lets you put one in the middle of the part — until now the one place it could not reach.
- You now move a hole with “Change bore” on an exact body too — and on a mesh it really moves. If it moves past the edge, Solidon says it is no longer a hole.
- You change the width of a slot with “Change bore”. The travel a screw has inside stays.
- If a hole or a slot cuts right through the part so that it falls into pieces, the report says so — instead of only that the hole reaches past the edge.

### Recognition

- A countersink above a hole is now kept even on a part with round, sweeping surfaces — previously it was dropped there, and the hole and its countersink could no longer be moved together.
- A cavity entirely inside the material, with no way out, appears in the object tree as an air pocket — with its volume. Previously it appeared as a hole that was not there.
- On a strongly curved model Solidon now says what was measured instead of calling it a scan — and which features are left out on such a surface.
- Feature recognition on large, organically shaped models has become about a quarter faster. What it finds is the same as before.
- If less material is left between a hole and the wall around it than your material carries, the report says so — measured on the finished part.
- The mesh defect map now also marks faces that run through each other. Before it saw only open and branching edges and called such a model sound.
- The layer analysis of a finely knurled part now takes half the time; the places it reports are the same as before.
- Whether a bridge counts as too long now depends on your nozzle: two lines from a 0.4 mm nozzle are 0.84 mm, not a round millimetre. Smaller changes are no longer reported by the chat as “+0.00 cm³”.
- Thread recognition needs only a fraction of the memory and can be cancelled.
- If a body cannot be split because of an open mesh, the repair stands as a button on the finding.
- If a cut cannot be capped, Solidon says that the model is not closed — and how to go on — instead of pointing at the cut.

### Labelling

- A label can now use eight fonts instead of three, plus bold and italic. Bold carries thicker strokes at the same height and stays legible where the regular style smears.
- Beside the upright faces there is now a round one and a handwritten one — those two come in a single style. All eight travel with the program, so a project looks the same everywhere.
- If a font is too fine for your nozzle, Solidon says from which height it carries — instead of printing it and letting the letters run together.
- The curved sides of a letter — the bow of a D, the mantle of an o — now appear in the object tree like the straight ones and take a filament of their own. Before, they were missing there entirely.

### Building blocks and fits

- A part from the catalogue appears in the view at once: on the selected face or on top of the body, with dimension lines and a handle. A click places it elsewhere, “Apply” inserts it.
- If you split a body with a fit into separate parts, Solidon asks which part the fit now means — instead of sending you off to undo the steps.
- The M2.5 press-fit insert gets its mounting hole as the data sheet says: 4.0 mm instead of 3.6. An older project with this insert says on opening that the size has changed.
- The warning about a snap arm that breaks reckons with the unfavourable print direction: an arm that bends across the layers carries less, and that now stands in the sentence.
- The variant generator engraves each part's value on its top face. If a part is too small for a legible number, the report says so and names the order on the plate.

### View and operation

- The actions for a selected body or feature live in one place on the right, in groups you can fold, with a search box. The Object, Modify and Prepare menus are gone for that; shortcuts still work.
- A right-click on a body or face shows only what exists there alone: the step behind it, the sketch on the face, hiding. The “Parts” button stands in accent colour.
- When the chain stops at a step, the actions are locked and say why; trying anyway shows the report's ways out right away. Before, the step landed silently behind the halt, never computed.
- The plate selector in the header sits beside the printer name instead of on top of it — even when the plates only arrive with the opened project.
- The report folds identical messages into one line, with the count in brackets in front. Clicking it selects every affected part; an action asks which of them it should apply to.
- The right-hand column with the report, chat and tour has become a little narrower; the space goes to the model.
- While measuring, the view switches to straight projection and back again afterwards. In perspective you aim beside the point, the further a line lies from the centre.
- If you only look at a model, you are no longer asked about saving when you close it. Imported files now appear under “Recently opened” instead.
- If you push a body past the edge of the print bed with the handle, Solidon brings it back to a free spot. A typed value is carried out as you entered it.
- The language choice in the settings dialogue takes effect at once; your other entries stay, Cancel restores the language. That also holds in the first setup, which a change no longer ends.
- After a quarter of an hour of work Solidon asks once per version for your feedback. Answer it or click it away — in this version the question does not come back.
- If the 3D mouse is blocked, Solidon names the way to release it instead of passing over it in silence.
- The way to the printer is called “Prepare printing …” in the menu instead of “Print settings …”. The dialogue behind it is the same.
- The Enter key in a dimension field on the right applies the step, and the Tab key walks through the fields from top to bottom.
- The command palette preselects the best match, not the first one that can run. “Fille” and Enter used to create a box.
- If you drag a body with the mouse, it stays at the pointer even over the empty background, instead of stopping and jumping as soon as something lies beneath it again.
- After opening a project, too, the first click into the model no longer stutters; the preparation for it runs as soon as the bodies are in place.
- Fine wheel movements — touchpad, high-resolution mouse — now zoom instead of being lost.
- Flying with the Ctrl key held stops as soon as you release the key. Before, the view flew on.
- At high display scaling you hit the handles as easily as at 100 %.
- After a change of finding, buttons of the report briefly appeared as small windows of their own. That is over.
- The layer outline of a part on the second plate lies on that part, not beside the first.
- The start screen shows only the menus that do something there.
- A second building block of the same kind — a second screw lid, say — gets a number instead of being named like the first.

### Files and export

- Before writing, the export shows what the report found — a thin wall, a violated fit. You decide whether the file is written anyway.
- Solidon remembers folder, format and naming scheme per project. If several files are written, the name pattern stands in the field and can be changed.
- While a model is being read, the progress stays until the model is really there, and the display says “Reading model” instead of “Loading project”. Cancel stays reachable all that time.
- An answered question about which feature a step means stays answered — even after closing and reopening the project.
- If a project's linked file is not reachable, the project can still be saved and opened; the report names the source. If permissions are missing, Solidon says so instead of calling it damaged.

### Print bed and handover

- If a body made of loose parts — lettering, say — fits no bed as a whole, the report offers to split it and orient it right away: one click, and the parts lie on the plates.
- Open in slicer hands ElegooSlicer, Orca and Bambu Studio all plates in one file — one window instead of one per plate.
- For splitting, lettering and texture the report states the number in the sentence, where a placeholder in braces stood before.
- Lettering you assigned a filament to keeps it when split into letters. Before, it arrived in the slicer on a second, grey filament, with the assigned one sitting unused beside it.
- With several plates, the parts now land where the slicer keeps its plates: in the grid it lays out itself. Before, the letters of the third and fourth plate stood beside everything.
- If a spool is left unused while slicing, Solidon says so by name. Before, the slicer reported success and a filament was missing in the print.
- If a slicer crashes, Solidon says so. Before it said the slicer had written no print file.
- Creality Print is recognised as a slicer and can be chosen in the print dialogue, with its printers, processes and filaments.
- The print dialogue opens at once with the slicer chosen last; the search for others runs in the background. Before, a click on Print could show nothing for ten seconds.
- The slicer selection shows every installed program — a second Flatpak or a second AppImage too. Before, the second one at each location was missing.
- A filament from a PrusaSlicer vendor bundle arrives in the handover with its own values, not with those of the first filament in the file.
- When handing over as STL — to Cura, say — Solidon says that settings per part do not travel along, and names the suggestion for the whole plate, instead of claiming they are set.

### Filaments and stock

- The filament stock can also be saved on a FAT32 stick, an exFAT drive or a network share. Before, every save failed there.
- If the stock cannot be read, Solidon says so in the filament picker too, with the button “Try again” — instead of an empty list.
- The consumption measured from the print file also counts material fed without a line, and does not count retractions twice. If the slicer writes the amount itself, its number holds.
- If you choose “Do not record” when booking, you are not asked again for this output; it stays reachable under “Not booked”.
- If you create a new spool in the booking dialogue, the selected spools, the entered amounts and the splits stay as they are.
- The object tree shows on a body and a face only the filaments that really lie there — a face with its own filament carries its own, not the list of the whole body.
- Cancel during the search for filament profiles takes effect at once.

### Chat and AI

- Before the first request to a model generator, Solidon says which data goes there.
- If another job occupies the graphics card, the chat waits visibly instead of standing still.

### Update, installation and system

- The Mac packages are signed and notarised. The detour via “Privacy & Security” → “Open Anyway” is gone.
- Under “Support Solidon”, GoFundMe is now on offer beside PayPal; only your click opens the browser, and without a browser the address can be copied.
- If your purchase code lies on a drive whose file permissions cannot be set — FAT, network share — it stays readable. Before, it counted as not present there.

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
