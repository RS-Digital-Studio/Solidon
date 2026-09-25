import sys, time
sys.path.insert(0, r"F:\3D Druck")
from app.core.bootstrap import load_operations
load_operations()
from app.core.registry import REGISTRY
from app.core.registry.search import rank_operations
sys.path.insert(0, r"F:\3D Druck")
from tests.agent_cases import ALL_CASES
extra = ["Mach die Bohrung größer", "Rund die Kanten oben ab, 2 mm", "Schreib SOLIDON auf die Oberseite", "Mach ein Loch für eine M3 Schraube", "Drill a 5 mm hole in the top", "Wie teile ich das Teil in zwei Hälften?", "Hohl das Teil aus mit 2 mm Wand", "Färbe die Oberseite rot", "Ein Kasten mit Deckel zum Schrauben"]
t = time.perf_counter()
for text in [c.request for c in ALL_CASES] + extra:
    r = rank_operations([text], REGISTRY)
    top = ", ".join(f"{n}:{s:.1f}" for n, s in r[:8])
    print(f"{text[:60]:60} | {top}")
print("time per", (time.perf_counter()-t)/ (len(ALL_CASES)+len(extra)))
