"""Die bestehende, begrenzte Bézier-Zerlegung für mehrere Trägerprüfungen teilen."""
from pathlib import Path

path = Path('app/core/brep/canonical.py')
text = path.read_text(encoding='utf-8')
start = text.index('    from OCP.GeomAbs import GeomAbs_BezierSurface\n', text.index('def _matches('))
end = text.index('    origin = np.asarray(candidate.Location().Coord()', start)
block = text[start:end].replace('return False', 'return None')
helper = ('def _bezier_patches(adaptor: Any, cancelled: CancelToken | None) -> list[Any] | None:\n'
          '    """Private rationale Teilflächen mit periodischen Trimmungen und gemeinsamer Arbeitsgrenze."""\n'
          + block + '    return patches\n\n\n')
text = text[:start] + ('    patches = _bezier_patches(adaptor, cancelled)\n'
                       '    if patches is None:\n        return False\n') + text[end:]
position = text.index('def _matches(')
text = text[:position] + helper + text[position:]
path.write_text(text, encoding='utf-8')
