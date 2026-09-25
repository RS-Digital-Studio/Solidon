import sys, json, time
sys.path.insert(0, r"F:\3D Druck")
from app.core.bootstrap import load_operations
load_operations()
from app.core.registry import REGISTRY
from app.core.agent.offer import ToolOffer
from app.core.agent.prompt import system_prompt
from app.core.agent.tools import tool_schemas
def chars(tools):
    return len(json.dumps([{"type":"function","function":{"name":t["name"],"description":t.get("description",""),"parameters":t.get("input_schema",{})}} for t in tools], ensure_ascii=False))
full = tool_schemas(compact=True)
print("all compact chars", chars(full))
for text, kind, empty in [("Hallo.", None, True), ("Hallo.", None, False), ("Bohr ein Loch mit 5 mm Durchmesser in die Oberseite, mittig.", "face", False), ("Ein Deckel mit vier Magnettaschen für 8x3-Magnete.", None, True), ("Mach das Loch größer.", "hole", False)]:
    started = time.perf_counter()
    offer = ToolOffer.for_turn(REGISTRY, [text], selected_kind=kind, empty_scene=empty)
    s = offer.schemas()
    print(f"{text[:40]:40} kind={kind} empty={empty} detailed={sorted(offer.detailed)} chars={chars(s)} tools={len(s)} {time.perf_counter()-started:.2f}s")
print(len(system_prompt(compact=True)))
print([t for t in offer.schemas() if t["name"]=="create_box"])
print([t["description"] for t in offer.schemas() if t["name"]=="drill_hole"])
