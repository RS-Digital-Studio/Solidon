"""Audit-Hilfe: Curas Einstellungsstapel nachrechnen (nur Prüfwerkzeug, kein Solidon-Code).

Reihenfolge (oben gewinnt): Nutzer > Qualität je Material > Material-XML > Düsenvariante >
Extruderdefinition > globale Qualität > Druckerdefinition (Erbkette).
Formeln werden mit eingeschränktem Namensraum ausgewertet.
"""

import configparser
import math
import pathlib
import xml.etree.ElementTree as ET

from curadef import chain

R = pathlib.Path(r"C:\Program Files\UltiMaker Cura 5.13.0\share\cura\resources")
MATMAP = {
    "print temperature": "default_material_print_temperature",
    "heated bed temperature": "default_material_bed_temperature",
    "standby temperature": "material_standby_temperature",
    "print cooling": "cool_fan_speed",
    "retraction amount": "retraction_amount",
    "retraction speed": "retraction_speed",
    "build volume temperature": "build_volume_temperature",
    "adhesion tendency": "material_adhesion_tendency",
    "surface energy": "material_surface_energy",
}


def ini_values(path):
    p = configparser.ConfigParser(interpolation=None)
    p.read(path, encoding="utf-8")
    out = {}
    if p.has_section("values"):
        for k, v in p["values"].items():
            out[k] = {"formula": v[1:]} if v.startswith("=") else {"literal": v}
    return out


def material_values(name, machine_id):
    t = ET.parse(R / "materials" / f"{name}.xml.fdm_material").getroot()
    ns = {"m": "http://www.ultimaker.com/material"}
    out = {}
    s = t.find("m:settings", ns)
    for st in s.findall("m:setting", ns):
        k = MATMAP.get(st.get("key"))
        if k:
            out[k] = {"literal": st.text.strip()}
    for mach in s.findall("m:machine", ns):
        ids = [mi.get("product") for mi in mach.findall("m:machine_identifier", ns)]
        if machine_id in ids:
            for st in mach.findall("m:setting", ns):
                k = MATMAP.get(st.get("key"))
                if k:
                    out[k] = {"literal": st.text.strip()}
    d = t.findtext("m:properties/m:diameter", "", ns)
    if d:
        out["material_diameter"] = {"literal": d}
    return out


def definition_layer(name, folder=None):
    levels = chain(name) if folder is None else chain(name, folder)
    merged = {}
    for _lvl, own, _meta in levels:
        for k, d in own.items():
            e = merged.setdefault(k, {})
            if "type" in d:
                e["type"] = d["type"]
            if "default_value" in d:
                e["dv"] = d["default_value"]
            if "value" in d:
                if isinstance(d["value"], str):
                    e["formula"] = d["value"]
                    e.pop("literal", None)
                else:
                    e["literal"] = d["value"]
                    e.pop("formula", None)
    return merged, levels


def _from_def(e):
    if e.get("formula"):
        return {"formula": e["formula"]}
    if "literal" in e:
        return {"literal": e["literal"]}
    if "dv" in e:
        return {"literal": e["dv"]}
    return None


class Stack:
    def __init__(
        self, machine, extruder, variant=None, gquality=None, material=None, mquality=None, user=None
    ):
        self.defs, self.levels = definition_layer(machine)
        ext = {}
        if extruder:
            ed, _ = definition_layer(extruder, R / "extruders")
            ext = {k: e for k, e in ed.items() if k != "extruder_nr"}
        self.layers = []
        if user:
            self.layers.append(("user", {k: {"literal": v} for k, v in user.items()}))
        if mquality:
            self.layers.append(("quality_mat", ini_values(mquality)))
        if material:
            self.layers.append(("material", material_values(material, machine)))
        if variant:
            self.layers.append(("variant", ini_values(variant)))
        self.layers.append(("extruder_def", {k: _from_def(e) for k, e in ext.items() if _from_def(e)}))
        if gquality:
            self.layers.append(("quality_global", ini_values(gquality)))
        self.layers.append(
            ("definition", {k: _from_def(e) for k, e in self.defs.items() if _from_def(e)})
        )
        self.cache = {}
        self.src = {}

    def typ(self, k):
        return self.defs.get(k, {}).get("type")

    def conv(self, k, v):
        t = self.typ(k)
        if not isinstance(v, str):
            return v
        s = v.strip()
        try:
            if t == "float":
                return float(s)
            if t in ("int", "extruder", "optional_extruder"):
                return int(float(s))
            if t == "bool":
                return s.lower() in ("true", "1")
        except ValueError:
            pass
        return s

    def get(self, k, depth=0):
        if k in self.cache:
            return self.cache[k]
        if depth > 80:
            raise RecursionError(k)
        for name, layer in self.layers:
            if k in layer:
                e = layer[k]
                if e.get("formula") is not None:
                    v = self.evalf(e["formula"], depth)
                    self.src[k] = f"{name}: ={e['formula']}"
                else:
                    v = self.conv(k, e["literal"])
                    self.src[k] = f"{name}: {e['literal']!r}"
                self.cache[k] = v
                return v
        raise KeyError(k)

    def evalf(self, f, depth):
        st = self

        class NS(dict):
            def __missing__(self, key):
                return st.get(key, depth + 1)

        ns = NS(
            extruderValue=lambda nr, key: st.get(key, depth + 1),
            extruderValues=lambda key: [st.get(key, depth + 1)],
            resolveOrValue=lambda key: st.get(key, depth + 1),
            defaultExtruderPosition=lambda: "0",
            anyExtruderWithMaterial=lambda key: 0,
            anyExtruderNrWithOrDefault=lambda key: 0,
            valueFromContainer=lambda *a: None,
            extruderValueFromContainer=lambda *a: None,
            math=math,
            max=max,
            min=min,
            round=round,
            int=int,
            float=float,
            any=any,
            all=all,
            sum=sum,
            len=len,
            abs=abs,
            str=str,
            bool=bool,
            map=map,
            list=list,
        )
        try:
            return eval(f, {"__builtins__": {}}, ns)  # noqa: S307 — Prüfwerkzeug im Scratchpad
        except Exception as ex:  # noqa: BLE001
            return f"<nicht auswertbar: {ex}>"


def stack_for(machine, extruder, variant, gquality, material, mquality, user=None):
    Q = R / "quality"
    V = R / "variants"
    return Stack(
        machine,
        extruder,
        variant=V / variant if variant else None,
        gquality=Q / gquality if gquality else None,
        material=material,
        mquality=Q / mquality if mquality else None,
        user=user,
    )
