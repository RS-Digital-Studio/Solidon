"""Way 3 from the window: describe or drop a picture, get a body (§2.2, §27).

The dialog is deliberately thin. Everything it does lives in
:mod:`app.core.generate`; what happens here is asking for a sentence, showing
whether a generator is running at all, and keeping the window responsive while
a graphics card thinks for a minute.

When nothing is running the dialog says so and offers no button to press —
greyed out, like the chat without a key (§27). It does not try to start
anything, and it does not hide the entry either: an action that disappears
looks like a bug, an action that explains itself does not.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.backends.mesh import ComfyBackend, GeneratedMesh, MeshBackend
from app.core.errors import AppError
from app.core.log import get_logger
from app.i18n import tr

_log = get_logger(__name__)

#: What can be dropped in as a starting picture.
IMAGE_FILTER = "Bilder (*.png *.jpg *.jpeg *.webp)"

#: Upper end of the seed the dialog offers. The same value gives the same run,
#: as far as the model on the other side allows (§11.3).
MAX_SEED = 2**31 - 1

#: How long closing waits for the worker before it lets go.
WAIT_MILLISECONDS = 50


class _Worker(QThread):
    """One generation, off the interface thread.

    A diffusion model takes minutes; doing that in the event loop would freeze
    the window and every progress line it is supposed to be showing (§31).
    """

    done = Signal(object)
    failed = Signal(object)
    step = Signal(float, str)

    def __init__(self, backend: MeshBackend, prompt: str, image: bytes | None, seed: int) -> None:
        super().__init__()
        self._backend = backend
        self._prompt = prompt
        self._image = image
        self._seed = seed

    def run(self) -> None:
        try:
            if self._image is not None:
                result = self._backend.image_to_mesh(
                    self._image, seed=self._seed, progress=self._progress
                )
            else:
                result = self._backend.text_to_mesh(
                    self._prompt, seed=self._seed, progress=self._progress
                )
        except AppError as problem:
            self.failed.emit(problem)
            return
        self.done.emit(result)

    def _progress(self, fraction: float, text: str) -> None:
        self.step.emit(fraction, text)


class GenerateDialog(QDialog):
    """Ask for a description or a picture, then hand back a generated body."""

    def __init__(self, backend: MeshBackend | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.backend: MeshBackend = backend or ComfyBackend()
        self.result_mesh: GeneratedMesh | None = None
        self._image: bytes | None = None
        self._worker: _Worker | None = None

        self.setWindowTitle(tr("Modell erzeugen"))
        self.setMinimumWidth(480)

        self.prompt = QLineEdit(self)
        self.prompt.setPlaceholderText(tr("Was soll entstehen?"))

        self.seed = QSpinBox(self)
        self.seed.setRange(0, MAX_SEED)
        self.seed.setToolTip(
            tr("Derselbe Startwert liefert dasselbe Modell, solange das Modell dasselbe bleibt.")
        )

        self.picture = QPushButton(tr("Bild wählen …"), self)
        self.picture.clicked.connect(self._choose_image)
        self.picture_label = QLabel(tr("Kein Bild gewählt"), self)

        form = QFormLayout()
        form.addRow(tr("Beschreibung"), self.prompt)
        form.addRow(tr("Bild"), self.picture)
        form.addRow("", self.picture_label)
        form.addRow(tr("Startwert"), self.seed)

        self.state = QLabel(self)
        self.state.setWordWrap(True)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Erzeugen"))
        self.buttons.accepted.connect(self._start)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.state)
        layout.addWidget(self.progress)
        layout.addWidget(self.buttons)

        self.prompt.textChanged.connect(self._update_state)
        self._update_state()

    # --- state ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return bool(self.backend.available)

    def _update_state(self) -> None:
        if not self.available:
            self.state.setText(
                tr(
                    "Es läuft kein Generator. Formwerk spricht lokal mit ComfyUI — "
                    "ohne das bleibt dieser Weg zu, alles andere funktioniert weiter."
                )
            )
        else:
            self.state.setText(tr("Bereit. Das kann einige Minuten dauern."))
        ready = self.available and bool(self.prompt.text().strip() or self._image)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ready)

    def _choose_image(self) -> None:
        name, _filter = QFileDialog.getOpenFileName(self, tr("Bild wählen"), "", IMAGE_FILTER)
        if not name:
            return
        self._image = Path(name).read_bytes()
        self.picture_label.setText(Path(name).name)
        self._update_state()

    # --- running ----------------------------------------------------------------

    def _start(self) -> None:
        if not self.available:
            return
        self.buttons.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        worker = _Worker(self.backend, self.prompt.text().strip(), self._image, self.seed.value())
        worker.done.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.step.connect(self._on_step)
        worker.finished.connect(self._on_thread_done)
        self._worker = worker
        worker.start()

    def _on_step(self, fraction: float, text: str) -> None:
        self.progress.setValue(int(max(0.0, min(1.0, fraction)) * 100))
        if text:
            self.state.setText(text)

    def _on_done(self, result: object) -> None:
        assert isinstance(result, GeneratedMesh)
        self.result_mesh = result
        _log.info("generated %d triangles", result.mesh.triangle_count)
        self.accept()

    def _on_failed(self, problem: object) -> None:
        self.progress.setVisible(False)
        self.buttons.setEnabled(True)
        text = str(problem.title) if isinstance(problem, AppError) else str(problem)
        self.state.setText(text)

    def _on_thread_done(self) -> None:
        self._worker = None

    def reject(self) -> None:
        """Cancelling waits for the thread instead of leaving it running.

        The request itself keeps going on the other side — there is no call in
        the interface of §27 to take it back, and inventing one that lies would
        be worse than saying nothing.
        """
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(WAIT_MILLISECONDS)
        super().reject()
