"""TripoSG für ComfyUI — die Knoten, die Solidon für Weg 3 braucht.

TripoSG steht unter MIT, Code wie Gewichte. Das ist der Grund, warum es
diesen Knoten gibt und nicht der vorhandene Hunyuan3D-Weg benutzt wird: dessen
Lizenz nimmt die Europäische Union ausdrücklich aus.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
