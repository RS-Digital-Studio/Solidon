"""TripoSG für ComfyUI — die Knoten, die Solidon für Weg 3 braucht.

TripoSG weist im Wurzel-``LICENSE`` und in der Modellkarte MIT aus; deshalb
gibt es diesen Knoten statt des vorhandenen Hunyuan3D-Wegs, dessen Lizenz die
Europäische Union ausdrücklich ausnimmt. Ein Teil des TripoSG-Quelltexts trägt
allerdings selbst Tencent-Lizenzen mit derselben Ausnahme — siehe ``nodes.py``
und RM-003.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
