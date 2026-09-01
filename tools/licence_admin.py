"""Lokale, nicht ausgelieferte Support-Oberfläche für Solidon-Lizenzen.

Das vollständige Schlüsselarchiv bleibt auf Roberts Rechner. Zum Server geht
ausschließlich der SHA-256-Digest der signierten Lizenznutzlast. Der Server
liefert Aktivierungszustand und -verlauf und nimmt vier eng benannte
Support-Handlungen an; das Werkzeug kann keine Lizenz signieren.

Start::

    python tools/licence_admin.py \
        --token D:\\Geheim\\operator.token \
        --archive D:\\Geheim\\solidon-licences.jsonl

Die Oberfläche benutzt Tk statt Qt, weil ``tools/`` nicht mit dem Produkt
ausgeliefert wird und Qt nach Regel 1 ausschließlich unter ``app/ui/`` stehen
darf. Netzwerkzugriffe laufen in einem kurzen Arbeiterfaden, damit ein
langsamer Server das Fenster nicht festhält.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import stat
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any, Final, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from app.core.activation import certificate, key
from app.core.http import (
    HttpBoundaryError,
    RejectRedirects,
    ResponseDeadlineError,
    ResponseTooLargeError,
    deadline_after,
    read_limited,
    response_url,
    same_origin,
    validate_http_url,
)
from app.core.json_boundary import loads as load_json
from app.core.log import redact_external
from app.i18n import tr
from tools.licence_archive import ArchiveBusyError, archive_lock

if os.name == "nt":
    import ctypes
    import msvcrt

DEFAULT_ENDPOINT: Final = "https://solidon3d.de/api/operator.php"
TOKEN_PATTERN: Final = re.compile(r"[0-9a-f]{64}")
ARCHIVE_FORMAT: Final = 1
OPERATOR_TIMEOUT_SECONDS: Final = 10.0
MAX_OPERATOR_RESPONSE_BYTES: Final = 256 * 1024
MAX_TOKEN_FILE_BYTES: Final = 256

_OPERATOR_OPENER = build_opener(RejectRedirects())


def _open_operator(request: Request, *, timeout: float) -> Any:
    """Öffnet den Betreiber-Endpunkt ohne Weiterleitung des Zugriffstokens."""
    return _OPERATOR_OPENER.open(request, timeout=timeout)


_DEFAULT_OPEN_OPERATOR = _open_operator

ACTION_LABELS: Final = {
    "block": "Neue Aktivierungen sperren",
    "unblock": "Aktivierungen wieder erlauben",
    "release": "Gerätewechsel ermöglichen",
    "reset_attempts": "Tageslimit zurücksetzen",
}
REASON_LABELS: Final = {
    "Gerätewechsel im Support": "support_device_change",
    "Erstattung": "refund",
    "Verdacht auf Weitergabe": "suspected_abuse",
    "Korrektur": "correction",
    "Datenauskunft": "data_request",
    "Sonstiger Vorgang": "other",
}


def _owned_by_current_user(descriptor: int) -> bool:
    """Ob Eigentümer und Leserechte der geöffneten Datei privat sind."""
    if os.name != "nt":
        getuid = cast(Callable[[], int], vars(os)["getuid"])
        return os.fstat(descriptor).st_uid == getuid()

    class TokenOwner(ctypes.Structure):
        _fields_ = (("sid", ctypes.c_void_p),)

    class SidAndAttributes(ctypes.Structure):
        _fields_ = (("sid", ctypes.c_void_p), ("attributes", ctypes.c_uint32))

    class AclSizeInformation(ctypes.Structure):
        _fields_ = (
            ("ace_count", ctypes.c_uint32),
            ("bytes_in_use", ctypes.c_uint32),
            ("bytes_free", ctypes.c_uint32),
        )

    class AceHeader(ctypes.Structure):
        _fields_ = (
            ("kind", ctypes.c_ubyte),
            ("flags", ctypes.c_ubyte),
            ("size", ctypes.c_uint16),
        )

    class AllowedAce(ctypes.Structure):
        _fields_ = (
            ("header", AceHeader),
            ("mask", ctypes.c_uint32),
            ("sid_start", ctypes.c_uint32),
        )

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel32.LocalFree.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int
    advapi32.GetSecurityInfo.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    )
    advapi32.GetSecurityInfo.restype = ctypes.c_uint32
    advapi32.OpenProcessToken.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    )
    advapi32.OpenProcessToken.restype = ctypes.c_int
    advapi32.GetTokenInformation.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    )
    advapi32.GetTokenInformation.restype = ctypes.c_int
    advapi32.EqualSid.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    advapi32.EqualSid.restype = ctypes.c_int
    advapi32.GetAclInformation.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
    )
    advapi32.GetAclInformation.restype = ctypes.c_int
    advapi32.GetAce.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    )
    advapi32.GetAce.restype = ctypes.c_int
    advapi32.CreateWellKnownSid.argtypes = (
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    )
    advapi32.CreateWellKnownSid.restype = ctypes.c_int
    handle = ctypes.c_void_p(msvcrt.get_osfhandle(descriptor))
    owner = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    security_descriptor = ctypes.c_void_p()
    result = advapi32.GetSecurityInfo(
        handle,
        1,  # SE_FILE_OBJECT
        1 | 4,  # OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(security_descriptor),
    )
    if result != 0:
        return False
    token = ctypes.c_void_p()
    try:
        if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
            return False

        def token_sid(kind: int, structure: type[ctypes.Structure]) -> tuple[Any, int] | None:
            needed = ctypes.c_uint32()
            advapi32.GetTokenInformation(token, kind, None, 0, ctypes.byref(needed))
            if not needed.value:
                return None
            buffer = ctypes.create_string_buffer(needed.value)
            if not advapi32.GetTokenInformation(
                token,
                kind,
                buffer,
                needed.value,
                ctypes.byref(needed),
            ):
                return None
            sid = int(ctypes.cast(buffer, ctypes.POINTER(structure)).contents.sid)
            return buffer, sid

        owner_data = token_sid(4, TokenOwner)
        user_data = token_sid(1, SidAndAttributes)
        if owner_data is None or user_data is None:
            return False
        _owner_buffer, token_owner = owner_data
        _user_buffer, token_user = user_data
        if not advapi32.EqualSid(owner, ctypes.c_void_p(token_owner)):
            return False
        if not dacl:
            return False

        def well_known_sid(kind: int) -> tuple[Any, int] | None:
            size = ctypes.c_uint32(68)
            buffer = ctypes.create_string_buffer(size.value)
            if not advapi32.CreateWellKnownSid(
                kind,
                None,
                buffer,
                ctypes.byref(size),
            ):
                return None
            return buffer, ctypes.addressof(buffer)

        system_data = well_known_sid(22)  # WinLocalSystemSid
        administrators_data = well_known_sid(26)  # WinBuiltinAdministratorsSid
        if system_data is None or administrators_data is None:
            return False
        _system_buffer, system_sid = system_data
        _administrators_buffer, administrators_sid = administrators_data
        trusted_sids = (token_user, token_owner, system_sid, administrators_sid)

        acl = AclSizeInformation()
        if not advapi32.GetAclInformation(
            dacl,
            ctypes.byref(acl),
            ctypes.sizeof(acl),
            2,  # AclSizeInformation
        ):
            return False
        for index in range(acl.ace_count):
            pointer = ctypes.c_void_p()
            if not advapi32.GetAce(dacl, index, ctypes.byref(pointer)) or pointer.value is None:
                return False
            header = ctypes.cast(pointer, ctypes.POINTER(AceHeader)).contents
            if header.kind != 0:  # Nur ein gewöhnlicher ACCESS_ALLOWED_ACE ist eindeutig.
                if header.kind in {5, 9, 11}:
                    return False
                continue
            ace = ctypes.cast(pointer, ctypes.POINTER(AllowedAce)).contents
            content_read = ace.mask & (0x00000001 | 0x80000000 | 0x10000000)
            if not content_read:
                continue
            sid = ctypes.c_void_p(pointer.value + AllowedAce.sid_start.offset)
            if not any(
                advapi32.EqualSid(sid, ctypes.c_void_p(trusted)) for trusted in trusted_sids
            ):
                return False

        return True
    finally:
        if token:
            kernel32.CloseHandle(token)
        kernel32.LocalFree(security_descriptor)


class OperatorError(RuntimeError):
    """Ein Fehler mit einem nächsten, ausführbaren Support-Schritt."""


@dataclass(frozen=True, slots=True)
class SupportLicence:
    """Lokale Käuferzuordnung zu der pseudonymen Serverkennung."""

    digest: str
    licence_key: str
    major: int | None
    purchased_on: date | None
    order: str
    holder: str
    transaction: str = ""

    @property
    def masked_key(self) -> str:
        """Nur Anfang und Ende für die Oberfläche; Kopieren bleibt bewusst."""
        if len(self.licence_key) <= 28:
            return self.licence_key
        return f"{self.licence_key[:18]}…{self.licence_key[-9:]}"


def _record_from_key(
    licence_text: str,
    expected_major: int | None = None,
    transaction: str = "",
) -> SupportLicence:
    """Prüft einen vollständigen Schlüssel und bildet seine Serverkennung."""
    licence = key.parse(licence_text, major=expected_major)
    return SupportLicence(
        digest=certificate.licence_digest(licence),
        licence_key=licence_text.strip(),
        major=licence.major,
        purchased_on=licence.purchased_on,
        order=licence.order,
        holder=licence.holder,
        transaction=transaction,
    )


def load_archive(path: Path) -> list[SupportLicence]:
    """Liest und verifiziert jeden Eintrag des privaten JSONL-Archivs."""
    try:
        lines = path.expanduser().read_text(encoding="utf-8").splitlines()
    except OSError as problem:
        raise OperatorError(
            tr("Das private Schlüsselarchiv ließ sich nicht lesen. Anderen Ort wählen.")
        ) from problem
    records: list[SupportLicence] = []
    seen: set[str] = set()
    transactions: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        try:
            raw = json.loads(line)
            if not isinstance(raw, dict) or raw.get("format") != ARCHIVE_FORMAT:
                raise ValueError("format")
            licence_text = raw["key"]
            major = raw["major"]
            transaction_text = raw.get("transaction", "")
            if (
                not isinstance(licence_text, str)
                or not isinstance(major, int)
                or isinstance(major, bool)
                or not isinstance(transaction_text, str)
            ):
                raise ValueError("metadata")
            transaction = " ".join(transaction_text.split()).strip()
            if transaction != transaction_text or len(transaction) > 128:
                raise ValueError("transaction")
            record = _record_from_key(
                licence_text,
                expected_major=major,
                transaction=transaction,
            )
            if record.digest != str(raw["digest"]):
                raise ValueError("digest")
            if record.order != str(raw.get("order", "")):
                raise ValueError("order")
            if record.holder != str(raw.get("holder", "")):
                raise ValueError("holder")
            if record.purchased_on is None or record.purchased_on.isoformat() != raw.get(
                "purchased_on"
            ):
                raise ValueError("purchased_on")
        except (KeyError, TypeError, ValueError, key.LicenceKeyError) as problem:
            raise OperatorError(
                tr(
                    "Das private Schlüsselarchiv ist in Zeile {line} beschädigt. "
                    "Sicherung wiederherstellen."
                ).format(line=number)
            ) from problem
        if record.digest in seen:
            raise OperatorError(
                tr(
                    "Das private Schlüsselarchiv enthält die Lizenz {digest} doppelt. "
                    "Archiv bereinigen."
                ).format(digest=record.digest[:12])
            )
        seen.add(record.digest)
        if record.transaction:
            transaction_key = record.transaction.casefold()
            previous = transactions.get(transaction_key)
            if previous is not None and previous != record.digest:
                raise OperatorError(
                    tr(
                        "Das private Schlüsselarchiv ordnet die Transaktion {transaction} "
                        "mehreren Lizenzen zu. Zuordnung korrigieren."
                    ).format(transaction=record.transaction)
                )
            transactions[transaction_key] = record.digest
        records.append(record)
    return records


def find_licences(query: str, records: list[SupportLicence]) -> list[SupportLicence]:
    """Findet nach Schlüssel, Digest, Bestellung, Käufer oder Teilschlüssel."""
    wanted = query.strip()
    if not wanted:
        return []
    if wanted.upper().startswith(f"{key.PREFIX}-{key.FORMAT_VERSION}-"):
        majors = {record.major for record in records if record.major is not None} | {
            key.current_major()
        }
        last_problem: key.LicenceKeyError | None = None
        for major in sorted(majors):
            try:
                direct = _record_from_key(wanted, expected_major=major)
            except key.LicenceKeyError as problem:
                last_problem = problem
                continue
            return [next((record for record in records if record.digest == direct.digest), direct)]
        if last_problem is not None:
            raise last_problem
        return []
    lowered = wanted.casefold()
    exact_digest = wanted.lower() if TOKEN_PATTERN.fullmatch(wanted.lower()) else ""
    if exact_digest:
        return [
            next(
                (record for record in records if record.digest == exact_digest),
                SupportLicence(exact_digest, "", None, None, "", "", ""),
            )
        ]
    return [
        record
        for record in records
        if any(
            lowered in value.casefold()
            for value in (
                record.order,
                record.holder,
                record.transaction,
                record.digest,
                record.licence_key,
            )
        )
    ]


def assign_transaction(path: Path, digest: str, transaction: str) -> None:
    """Ordnet einen Vorrat lokal einer MoR-Transaktion zu, atomar und prüfbar."""
    wanted = " ".join(transaction.split()).strip()
    if not wanted or len(wanted) > 128:
        raise OperatorError(
            tr("Die Transaktionskennung muss zwischen 1 und 128 Zeichen lang sein.")
        )
    target = path.expanduser()
    try:
        with archive_lock(target):
            # Erst das ganze Archiv verifizieren. Eine Zuordnung darf keinen
            # beschädigten Bestand überschreiben und den Fund verdecken.
            load_archive(target)
            raw_records = [
                json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()
            ]
            matches = [record for record in raw_records if record.get("digest") == digest]
            if len(matches) != 1:
                raise OperatorError(
                    tr("Die Lizenz steht nicht genau einmal im privaten Archiv. Archiv prüfen.")
                )
            duplicate = next(
                (
                    record
                    for record in raw_records
                    if str(record.get("transaction", "")).casefold() == wanted.casefold()
                    and record.get("digest") != digest
                ),
                None,
            )
            if duplicate is not None:
                raise OperatorError(
                    tr(
                        "Diese MoR-Transaktion ist bereits einer anderen Lizenz "
                        "zugeordnet. Bestehende Zuordnung prüfen."
                    )
                )
            matches[0]["transaction"] = wanted
            payload = "".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                for record in raw_records
            )
            temporary_name = ""
            try:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=target.parent,
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary:
                    temporary.write(payload)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                    temporary_name = temporary.name
                Path(temporary_name).replace(target)
            finally:
                if temporary_name:
                    Path(temporary_name).unlink(missing_ok=True)
    except OperatorError:
        raise
    except ArchiveBusyError as problem:
        raise OperatorError(str(problem)) from problem
    except (OSError, ValueError) as problem:
        raise OperatorError(
            tr("Die Transaktionszuordnung ließ sich nicht speichern. Anderen Ort prüfen.")
        ) from problem
    with contextlib.suppress(OSError):
        target.chmod(0o600)


def read_token(path: Path) -> str:
    """Liest genau einen 256-Bit-Token aus der externen Datei."""
    target = path.expanduser()
    try:
        metadata = target.lstat()
        junction = getattr(target, "is_junction", None)
        if (
            target.is_symlink()
            or (callable(junction) and junction())
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
        ):
            raise OSError("Tokendatei ist keine einzelne gewöhnliche Datei")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags)
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino)
            ):
                raise OSError("Tokendatei wechselte beim Öffnen")
            if not _owned_by_current_user(descriptor):
                raise OSError("Tokendatei gehört nicht dem aktuellen Nutzer")
            if os.name != "nt" and stat.S_IMODE(opened.st_mode) & 0o077:
                raise OSError("Tokendatei ist für andere Nutzer zugänglich")
            raw = os.read(descriptor, MAX_TOKEN_FILE_BYTES + 1)
        finally:
            os.close(descriptor)
        if len(raw) > MAX_TOKEN_FILE_BYTES:
            raise OSError("Tokendatei ist ungewöhnlich groß")
        token = raw.decode("ascii").strip()
    except (OSError, UnicodeError) as problem:
        raise OperatorError(
            tr("Der Betreiberzugang ließ sich nicht lesen. Tokendatei auswählen.")
        ) from problem
    if TOKEN_PATTERN.fullmatch(token) is None:
        raise OperatorError(
            tr("Der Betreiberzugang ist beschädigt. Er muss 32 zufällige Bytes enthalten.")
        )
    return token


class OperatorClient:
    """Kleine HTTPS-Gegenstelle des privaten Betreiber-Endpunkts."""

    def __init__(self, endpoint: str, token: str) -> None:
        try:
            checked = validate_http_url(
                endpoint,
                allow_http=True,
                allow_query=False,
                allow_fragment=False,
            )
        except ValueError as problem:
            raise OperatorError(
                tr("Die Support-Verwaltung braucht HTTPS. Serveradresse korrigieren.")
            ) from problem
        parsed = urlparse(checked)
        local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
            raise OperatorError(
                tr("Die Support-Verwaltung braucht HTTPS. Serveradresse korrigieren.")
            )
        if TOKEN_PATTERN.fullmatch(token) is None:
            raise OperatorError(tr("Der Betreiberzugang ist nicht verwendbar. Tokendatei prüfen."))
        self.endpoint = checked
        self.token = token

    def call(self, action: str, digest: str, reason: str = "") -> dict[str, Any]:
        """Ruft genau eine Abfrage oder Änderung mit kurzer Zeitgrenze auf."""
        payload = {"action": action, "digest": digest}
        if action != "lookup":
            payload["reason"] = reason
        request = Request(
            self.endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                # FastCGI reicht Authorization je Hosting-Konfiguration nicht
                # durch. Derselbe Token in einem zweiten, nicht geloggten
                # Header hält den Weg auf dem gemessenen Shared Hosting offen.
                "X-Solidon-Operator-Token": self.token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        status = 0
        answer = b""
        deadline = deadline_after(OPERATOR_TIMEOUT_SECONDS)
        strict_timeout = _open_operator is _DEFAULT_OPEN_OPERATOR
        try:
            with _open_operator(request, timeout=OPERATOR_TIMEOUT_SECONDS) as response:
                if not same_origin(
                    self.endpoint,
                    validate_http_url(response_url(response, self.endpoint), allow_http=True),
                ):
                    raise OperatorError(
                        tr("Die Serverantwort war nicht lesbar. Serverprotokoll prüfen.")
                    )
                status = response.status
                answer = read_limited(
                    response,
                    limit=MAX_OPERATOR_RESPONSE_BYTES,
                    deadline=deadline,
                    require_timeout=strict_timeout,
                )
        except HTTPError as problem:
            try:
                status = problem.code
                try:
                    answer = read_limited(
                        problem,
                        limit=MAX_OPERATOR_RESPONSE_BYTES,
                        deadline=deadline,
                        require_timeout=strict_timeout,
                    )
                except HttpBoundaryError as boundary:
                    raise OperatorError(
                        tr(
                            "Die Support-Verwaltung ist nicht erreichbar. Verbindung prüfen "
                            "und erneut versuchen."
                        )
                    ) from boundary
            finally:
                problem.close()
        except (OSError, URLError, ResponseDeadlineError, ResponseTooLargeError) as problem:
            raise OperatorError(
                tr(
                    "Die Support-Verwaltung ist nicht erreichbar. Verbindung prüfen und "
                    "erneut versuchen."
                )
            ) from problem
        try:
            result = load_json(answer, max_bytes=MAX_OPERATOR_RESPONSE_BYTES)
        except (UnicodeError, ValueError) as problem:
            raise OperatorError(
                tr("Die Serverantwort war nicht lesbar. Serverprotokoll prüfen.")
            ) from problem
        if not isinstance(result, dict) or status >= 400 or result.get("ok") is not True:
            code = result.get("code") if isinstance(result, dict) else ""
            if code == "operator_forbidden":
                help_text = tr("Tokendatei und Servereinrichtung abgleichen.")
            elif code == "service_unavailable":
                help_text = tr("Aktivierungsdatenbank und Betreiberzugang auf dem Server prüfen.")
            else:
                help_text = tr("Eingabe prüfen und erneut versuchen.")
            detail = (
                redact_external(result.get("error", ""), limit=300)
                if isinstance(result, dict)
                else ""
            )
            raise OperatorError(
                f"{detail or tr('Die Support-Handlung wurde abgelehnt.')} {help_text}"
            )
        return result


class SupportWindow:
    """Tk-Fenster: lokale Zuordnung links, Serverzustand und Handlungen rechts."""

    def __init__(
        self,
        root: Any,
        *,
        endpoint: str,
        token_path: Path | None,
        archive_path: Path | None,
    ) -> None:
        # Der Import bleibt hier: Prüfläufe und Serverwerkzeuge brauchen kein
        # installiertes Tk. Die Betreiberoberfläche meldet sein Fehlen im
        # Einstiegspunkt mit einem ausführbaren nächsten Schritt.
        import tkinter as tk
        from tkinter import filedialog, simpledialog, ttk

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.simpledialog = simpledialog
        self.root = root
        self.records: list[SupportLicence] = []
        self.found: list[SupportLicence] = []
        self.current: SupportLicence | None = None
        self.busy = False
        self.server_loaded_digest: str | None = None
        self.pending_notice = ""

        root.title(tr("Solidon · private Support-Verwaltung"))
        root.minsize(1200, 760)
        root.geometry("1280x800")
        self._configure_style(root)
        frame = ttk.Frame(root, style="App.TFrame", padding=(18, 14))
        frame.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        self.endpoint = tk.StringVar(value=endpoint)
        self.token_path = tk.StringVar(value=str(token_path or ""))
        self.archive_path = tk.StringVar(value=str(archive_path or ""))
        self.query = tk.StringVar()
        self.summary = tk.StringVar(
            value=tr("Eine Lizenz auswählen — danach erscheint hier der vollständige Supportfall.")
        )
        self.message = tk.StringVar(
            value=tr("Bereit · Mit Schlüssel, Bestellung, Transaktion, E-Mail oder Digest suchen.")
        )
        self.reason = tk.StringVar(value=next(iter(REASON_LABELS)))

        hero = ttk.Frame(frame, style="Hero.TFrame", padding=(20, 13))
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        hero.columnconfigure(0, weight=1)
        ttk.Label(
            hero,
            text=tr("Kundenlizenz finden und Supportfall lösen"),
            style="HeroTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            hero,
            text=tr(
                "Keine CAD-Kenntnisse nötig: Kundenangabe suchen, Zustand lesen, "
                "passende Supportaktion wählen."
            ),
            style="HeroText.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Label(
            hero,
            text=tr("✓ PRIVAT · Nur die anonyme Lizenzkennung geht zum Server"),
            style="Privacy.TLabel",
            padding=(12, 7),
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(24, 0))

        settings = ttk.LabelFrame(
            frame,
            text=tr("Sichere Verbindung und lokale Daten"),
            style="Card.TLabelframe",
            padding=(12, 7),
        )
        settings.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(4, weight=1)
        ttk.Label(settings, text=tr("Server")).grid(row=0, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.endpoint).grid(
            row=0, column=1, columnspan=5, sticky="ew", padx=(8, 0), pady=(0, 8)
        )
        ttk.Label(settings, text=tr("Betreiberzugang")).grid(row=1, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.token_path).grid(
            row=1, column=1, sticky="ew", padx=(8, 6)
        )
        ttk.Button(settings, text=tr("Datei wählen …"), command=self._choose_token).grid(
            row=1, column=2, sticky="ew", padx=(0, 18)
        )
        ttk.Label(settings, text=tr("Schlüsselarchiv")).grid(row=1, column=3, sticky="w")
        ttk.Entry(settings, textvariable=self.archive_path).grid(
            row=1, column=4, sticky="ew", padx=(8, 6)
        )
        ttk.Button(settings, text=tr("Datei wählen …"), command=self._choose_archive).grid(
            row=1, column=5, sticky="ew"
        )

        workspace = ttk.Panedwindow(frame, orient=tk.HORIZONTAL)
        workspace.grid(row=2, column=0, sticky="nsew")
        left = ttk.Frame(workspace, style="App.TFrame", padding=(0, 0, 8, 0))
        right = ttk.Frame(workspace, style="App.TFrame", padding=(8, 0, 0, 0))
        workspace.add(left, weight=5)
        workspace.add(right, weight=7)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        search_card = ttk.LabelFrame(
            left,
            text=tr("1 · Kundenlizenz finden"),
            style="Card.TLabelframe",
            padding=12,
        )
        search_card.grid(row=0, column=0, sticky="nsew")
        search_card.columnconfigure(0, weight=1)
        search_card.rowconfigure(3, weight=1)
        ttk.Label(
            search_card,
            text=tr(
                "Einfach die Angabe des Kunden einfügen. Teilstücke reichen bei "
                "Bestellung, E-Mail, Transaktion und Lizenzkennung."
            ),
            style="Muted.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        search = ttk.Frame(search_card, style="Card.TFrame")
        search.grid(row=1, column=0, columnspan=2, sticky="ew")
        search.columnconfigure(0, weight=1)
        entry = ttk.Entry(search, textvariable=self.query)
        entry.grid(row=0, column=0, sticky="ew", ipady=5)
        entry.bind("<Return>", lambda _event: self.search())
        ttk.Button(
            search,
            text=tr("Lizenz suchen"),
            command=self.search,
            style="Primary.TButton",
        ).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(
            search_card,
            text=tr("Suchergebnisse"),
            style="Section.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(14, 7))

        result_frame = ttk.Frame(search_card, style="Card.TFrame")
        result_frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        self.results = ttk.Treeview(
            result_frame,
            columns=("transaction", "order", "holder", "date", "digest"),
            show="headings",
            height=4,
            selectmode="browse",
        )
        for column, title, width in (
            ("transaction", tr("Transaktion"), 100),
            ("order", tr("Bestellung"), 90),
            ("holder", tr("Käuferkennung"), 125),
            ("date", tr("Datum"), 70),
            ("digest", tr("Lizenzkennung"), 125),
        ):
            self.results.heading(column, text=title)
            self.results.column(column, width=width, minwidth=80)
        self.results.grid(row=0, column=0, sticky="nsew")
        result_scrollbar = ttk.Scrollbar(
            result_frame,
            orient="vertical",
            command=self.results.yview,
        )
        result_scrollbar.grid(row=0, column=1, sticky="ns")
        self.results.configure(yscrollcommand=result_scrollbar.set)
        self.results.bind("<<TreeviewSelect>>", self._selection_changed)
        local_actions = ttk.Frame(search_card, style="Card.TFrame")
        local_actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.copy_button = ttk.Button(
            local_actions,
            text=tr("Schlüssel kopieren"),
            command=self.copy_key,
            state="disabled",
        )
        self.copy_button.grid(row=0, column=0, sticky="w")
        self.assign_button = ttk.Button(
            local_actions,
            text=tr("MoR-Transaktion zuordnen"),
            command=self.assign_current_transaction,
            state="disabled",
        )
        self.assign_button.grid(row=0, column=1, sticky="w", padx=(8, 0))

        state_card = ttk.LabelFrame(
            right,
            text=tr("2 · Supportfall verstehen"),
            style="Card.TLabelframe",
            padding=12,
        )
        state_card.grid(row=0, column=0, sticky="nsew")
        state_card.columnconfigure(0, weight=1)
        state_card.rowconfigure(3, weight=1)
        state_header = ttk.Frame(state_card, style="Card.TFrame")
        state_header.grid(row=0, column=0, sticky="ew")
        state_header.columnconfigure(0, weight=1)
        self.status_badge = ttk.Label(
            state_header,
            text=tr("○ Noch nicht geprüft"),
            style="NeutralStatus.TLabel",
            padding=(12, 7),
        )
        self.status_badge.grid(row=0, column=0, sticky="w")
        self.lookup_button = ttk.Button(
            state_header,
            text=tr("Serverzustand aktualisieren"),
            command=self.lookup,
            state="disabled",
        )
        self.lookup_button.grid(row=0, column=1, sticky="e")
        ttk.Label(
            state_card,
            textvariable=self.summary,
            wraplength=570,
            justify="left",
            style="Summary.TLabel",
        ).grid(row=1, column=0, sticky="ew", pady=(12, 8))
        warning = ttk.Label(
            state_card,
            text=tr(
                "Hinweis: Eine Sperre verhindert neue Aktivierungen. Bereits ausgestellte "
                "Offline-Freischaltungen bleiben auf dem vorhandenen Rechner gültig."
            ),
            style="Warning.TLabel",
            wraplength=570,
            justify="left",
            padding=(12, 9),
        )
        warning.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        notebook = ttk.Notebook(state_card)
        notebook.grid(row=3, column=0, sticky="nsew")
        self.activations = self._tree_tab(
            notebook,
            tr("Geräte und Plätze"),
            (
                ("state", tr("Zustand"), 80),
                ("device", tr("Gerätename"), 110),
                ("from", tr("Aktiviert"), 95),
                ("to", tr("Freigegeben"), 105),
                ("id", tr("Aktivierungskennung"), 130),
            ),
        )
        self.attempts = self._tree_tab(
            notebook,
            tr("Tageslimit"),
            (("day", tr("Tag"), 180), ("count", tr("Gültige Versuche"), 180)),
        )
        self.events = self._tree_tab(
            notebook,
            tr("Änderungsprotokoll"),
            (
                ("at", tr("Zeitpunkt"), 140),
                ("action", tr("Handlung"), 150),
                ("reason", tr("Anlass"), 140),
                ("changed", tr("Wirkung"), 90),
            ),
        )

        actions = ttk.LabelFrame(
            frame,
            text=tr("3 · Passende Supportaktion"),
            style="Card.TLabelframe",
            padding=(12, 8),
        )
        actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure(1, weight=1)
        ttk.Label(
            actions,
            text=tr("Anlass für das Änderungsprotokoll"),
            style="Section.TLabel",
        ).grid(row=0, column=0, sticky="w")
        reasons = ttk.Combobox(
            actions,
            state="readonly",
            values=[tr(label) for label in REASON_LABELS],
            textvariable=self.reason,
            width=32,
        )
        reasons.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(
            actions,
            text=tr("Jede Änderung wird ohne Namen oder E-Mail protokolliert."),
            style="Muted.TLabel",
        ).grid(row=0, column=2, sticky="e", padx=(20, 0))
        action_row = ttk.Frame(actions, style="Card.TFrame")
        action_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        for action_column in range(4):
            action_row.columnconfigure(action_column, weight=1)
        self.action_buttons: list[Any] = []
        for grid_column, action in enumerate(ACTION_LABELS):
            button = ttk.Button(
                action_row,
                text=tr(ACTION_LABELS[action]),
                command=partial(self.change, action),
                state="disabled",
                style="Danger.TButton" if action == "block" else "Support.TButton",
            )
            button.grid(
                row=0,
                column=grid_column,
                sticky="ew",
                padx=(0 if grid_column == 0 else 5, 0),
            )
            self.action_buttons.append(button)

        ttk.Label(
            frame,
            textvariable=self.message,
            style="Message.TLabel",
            wraplength=1200,
            justify="left",
            padding=(12, 9),
        ).grid(row=4, column=0, sticky="ew", pady=(8, 0))
        root.bind("<F5>", lambda _event: self.lookup())
        root.bind("<Control-f>", lambda _event: entry.focus_set())
        if archive_path is not None:
            self._reload_archive()
        entry.focus_set()

    def _configure_style(self, root: Any) -> None:
        """Gibt dem privaten Werkzeug eine ruhige, klar geführte Oberfläche."""
        style = self.ttk.Style(root)
        for candidate in ("clam", "vista", "xpnative"):
            if candidate in style.theme_names():
                style.theme_use(candidate)
                break
        root.configure(background="#f3f5f8")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("App.TFrame", background="#f3f5f8")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Hero.TFrame", background="#17223b")
        style.configure(
            "HeroTitle.TLabel",
            background="#17223b",
            foreground="#ffffff",
            font=("Segoe UI Semibold", 19),
        )
        style.configure(
            "HeroText.TLabel",
            background="#17223b",
            foreground="#d8e1f0",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Privacy.TLabel",
            background="#233453",
            foreground="#c9f7dc",
            font=("Segoe UI Semibold", 9),
        )
        style.configure("Card.TLabelframe", background="#ffffff", borderwidth=1, relief="solid")
        style.configure(
            "Card.TLabelframe.Label",
            background="#ffffff",
            foreground="#17223b",
            font=("Segoe UI Semibold", 11),
        )
        style.configure("Muted.TLabel", background="#ffffff", foreground="#627087")
        style.configure(
            "Section.TLabel",
            background="#ffffff",
            foreground="#26354d",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Summary.TLabel",
            background="#ffffff",
            foreground="#26354d",
            font=("Segoe UI", 10),
        )
        style.configure("Warning.TLabel", background="#fff6db", foreground="#6b4d00")
        style.configure(
            "Message.TLabel",
            background="#e8edf5",
            foreground="#26354d",
            font=("Segoe UI Semibold", 9),
        )
        style.configure(
            "NeutralStatus.TLabel",
            background="#e8edf5",
            foreground="#42526b",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "ActiveStatus.TLabel",
            background="#dcf7e8",
            foreground="#17623b",
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "BlockedStatus.TLabel",
            background="#ffe3e3",
            foreground="#922d2d",
            font=("Segoe UI Semibold", 10),
        )
        style.configure("Primary.TButton", padding=(15, 8), font=("Segoe UI Semibold", 10))
        style.configure("Support.TButton", padding=(10, 8), font=("Segoe UI Semibold", 9))
        style.configure("Danger.TButton", padding=(10, 8), font=("Segoe UI Semibold", 9))
        style.configure("Primary.TButton", background="#2f6fed", foreground="#ffffff")
        style.map(
            "Primary.TButton",
            background=[("active", "#245ec2"), ("disabled", "#aebbd0")],
            foreground=[("disabled", "#eef2f7")],
        )
        style.configure("Support.TButton", background="#e7edf6", foreground="#26354d")
        style.map("Support.TButton", background=[("active", "#d7e2f1")])
        style.configure("Danger.TButton", background="#fff0f0", foreground="#8d2e2e")
        style.map("Danger.TButton", background=[("active", "#ffdddd")])
        style.configure("Treeview", rowheight=29, background="#ffffff", fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9), padding=(6, 7))

    def _tree_tab(
        self, notebook: Any, title: str, columns: tuple[tuple[str, str, int], ...]
    ) -> Any:
        frame = self.ttk.Frame(notebook, padding=6)
        notebook.add(frame, text=title)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree = self.ttk.Treeview(
            frame,
            columns=tuple(column for column, _title, _width in columns),
            show="headings",
            height=4,
        )
        for column, heading, width in columns:
            tree.heading(column, text=heading)
            tree.column(column, width=width, minwidth=80)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = self.ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def _set_server_controls(self, loaded: bool) -> None:
        """Schaltet Änderungen nur für einen frisch gelesenen Kundenfall frei."""
        current = getattr(self, "current", None)
        self.server_loaded_digest = current.digest if loaded and current is not None else None
        for button in getattr(self, "action_buttons", []):
            button.configure(state="normal" if loaded else "disabled")
        lookup_button = getattr(self, "lookup_button", None)
        if lookup_button is not None:
            lookup_button.configure(
                state="normal" if current is not None and not self.busy else "disabled"
            )

    def _choose_token(self) -> None:
        chosen = self.filedialog.askopenfilename(title=tr("Betreiberzugang auswählen"))
        if chosen:
            self.token_path.set(chosen)
            if self.current is not None:
                self.lookup()

    def _choose_archive(self) -> None:
        chosen = self.filedialog.askopenfilename(title=tr("Schlüsselarchiv auswählen"))
        if chosen:
            self.archive_path.set(chosen)
            self._reload_archive()

    def _reload_archive(self) -> None:
        path = self.archive_path.get().strip()
        if not path:
            self.records = []
            return
        try:
            self.records = load_archive(Path(path))
        except OperatorError as problem:
            self.records = []
            self.message.set(str(problem))
            return
        self.message.set(
            tr("{count} Lizenz(en) aus dem privaten Archiv geladen.").format(
                count=len(self.records)
            )
        )

    def search(self) -> None:
        self._reload_archive()
        self.current = None
        self._set_server_controls(False)
        self.status_badge.configure(
            text=tr("○ Noch nicht geprüft"),
            style="NeutralStatus.TLabel",
        )
        self.summary.set(
            tr("Eine Lizenz auswählen — danach erscheint hier der vollständige Supportfall.")
        )
        for item in self.results.get_children():
            self.results.delete(item)
        try:
            self.found = find_licences(self.query.get(), self.records)
        except (OperatorError, key.LicenceKeyError):
            self.found = []
            self.message.set(
                tr("Die Suche war nicht verwendbar. Lizenzschlüssel oder Suchtext prüfen.")
            )
            return
        for index, record in enumerate(self.found):
            self.results.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    record.transaction or tr("noch nicht zugeordnet"),
                    record.order or tr("nicht im Archiv"),
                    record.holder or tr("unpersonalisiert"),
                    record.purchased_on.isoformat() if record.purchased_on else "—",
                    record.digest,
                ),
            )
        if not self.found:
            self.message.set(
                tr("Keine passende Lizenz gefunden. Vollständigen Schlüssel oder Digest anfordern.")
            )
            return
        self.message.set(tr("{count} passende Lizenz(en) gefunden.").format(count=len(self.found)))
        if len(self.found) == 1:
            self.results.selection_set("0")
            self.results.focus("0")

    def _selection_changed(self, _event: object) -> None:
        selected = self.results.selection()
        if not selected:
            return
        self.current = self.found[int(selected[0])]
        self._set_server_controls(False)
        self.copy_button.configure(state="normal" if self.current.licence_key else "disabled")
        self.assign_button.configure(
            state="normal"
            if self.current.licence_key and self.archive_path.get().strip()
            else "disabled"
        )
        self.lookup()

    def _client(self) -> OperatorClient:
        token_name = self.token_path.get().strip()
        if not token_name:
            raise OperatorError(tr("Betreiberzugang auswählen und erneut versuchen."))
        return OperatorClient(self.endpoint.get().strip(), read_token(Path(token_name)))

    def _run(self, work: Any, done: Any, context_digest: str) -> None:
        """Zeigt eine Serverantwort nur noch bei derselben ausgewählten Lizenz."""
        if self.busy:
            self.message.set(tr("Auswahl geändert; der aktuelle Zustand wird gleich geladen."))
            return
        self.busy = True
        self._set_server_controls(False)
        status_badge = getattr(self, "status_badge", None)
        if status_badge is not None:
            status_badge.configure(
                text=tr("… Serverzustand wird geprüft"),
                style="NeutralStatus.TLabel",
            )
        self.message.set(tr("Serverzustand wird sicher geladen …"))

        def execute() -> None:
            try:
                result: tuple[dict[str, Any] | None, Exception | None] = (work(), None)
            except Exception as problem:  # Das Fenster muss jeden Serverfehler erklären.
                result = (None, problem)

            def finish() -> None:
                self.busy = False
                answer, problem = result
                if self.current is None or self.current.digest != context_digest:
                    # Die Serverantwort gehört zur alten Zeile. Sie darf weder
                    # Überschrift noch Verlauf der neuen Auswahl füllen; deren
                    # Abfrage wurde während ``busy`` bewusst zurückgestellt.
                    self.message.set(tr("Auswahl geändert; aktueller Zustand wird geladen …"))
                    self.lookup()
                    return
                if problem is not None:
                    self._set_server_controls(False)
                    if status_badge is not None:
                        status_badge.configure(
                            text=tr("! Serverzustand nicht verfügbar"),
                            style="BlockedStatus.TLabel",
                        )
                    self.message.set(str(problem))
                    return
                done(answer)

            with contextlib.suppress(self.tk.TclError):
                self.root.after(0, finish)

        threading.Thread(target=execute, name="solidon-licence-admin", daemon=True).start()

    def lookup(self) -> None:
        if self.current is None:
            return
        digest = self.current.digest
        self._run(
            lambda: self._client().call("lookup", digest),
            self._show_state,
            digest,
        )

    def change(self, action: str) -> None:
        if self.current is None:
            return
        if self.server_loaded_digest != self.current.digest:
            self.message.set(
                tr("Zuerst den aktuellen Serverzustand laden; danach ist die Handlung verfügbar.")
            )
            self.lookup()
            return
        selected_reason = self.reason.get()
        reason = REASON_LABELS.get(selected_reason)
        if reason is None:
            self.message.set(tr("Einen festen Anlass auswählen und erneut versuchen."))
            return
        digest = self.current.digest
        self._run(
            lambda: self._client().call(action, digest, reason),
            lambda answer: self._show_state(answer, action),
            digest,
        )

    def _show_state(self, answer: dict[str, Any] | None, action: str = "") -> None:
        if answer is None or self.current is None:
            return
        licence = answer.get("licence", {})
        status = str(licence.get("status", "unknown"))
        self.server_loaded_digest = self.current.digest
        badge = {
            "active": (tr("✓ Aktivierungen erlaubt"), "ActiveStatus.TLabel"),
            "blocked": (tr("⛔ Neue Aktivierungen gesperrt"), "BlockedStatus.TLabel"),
            "unknown": (tr("○ Noch nie aktiviert"), "NeutralStatus.TLabel"),
        }.get(status, (tr("? Unbekannter Serverzustand"), "NeutralStatus.TLabel"))
        self.status_badge.configure(text=badge[0], style=badge[1])
        holder = self.current.holder or tr("unpersonalisiert")
        order = self.current.order or tr("nicht im Archiv")
        transaction = self.current.transaction or tr("noch nicht zugeordnet")
        created = licence.get("created_at") or tr("noch nie aktiviert")
        self.summary.set(
            tr(
                "Kunde: {holder}\nKauf: MoR {transaction} · Bestellung {order}\n"
                "Lizenz: {key}\nErster Serverkontakt: {created}"
            ).format(
                transaction=transaction,
                order=order,
                holder=holder,
                created=created,
                key=self.current.masked_key or tr("nur Digest vorhanden"),
            )
        )
        self._fill_tree(
            self.activations,
            [
                (
                    tr("aktiv") if row.get("active") else tr("deaktiviert"),
                    row.get("device_name", ""),
                    row.get("activated_on", ""),
                    row.get("deactivated_at") or "—",
                    row.get("id", ""),
                )
                for row in answer.get("activations", [])
            ],
        )
        self._fill_tree(
            self.attempts,
            [(row.get("day", ""), row.get("attempts", 0)) for row in answer.get("attempts", [])],
        )
        reason_by_code = {code: label for label, code in REASON_LABELS.items()}
        self._fill_tree(
            self.events,
            [
                (
                    row.get("occurred_at", ""),
                    tr(ACTION_LABELS.get(str(row.get("action", "")), str(row.get("action", "")))),
                    tr(reason_by_code.get(str(row.get("reason", "")), str(row.get("reason", "")))),
                    tr("geändert") if row.get("changed") else tr("ohne Zustandswechsel"),
                )
                for row in answer.get("events", [])
            ],
        )
        self._set_server_controls(True)
        if action:
            changed = bool(answer.get("changed"))
            self.message.set(
                tr("{action}: {result}.").format(
                    action=tr(ACTION_LABELS.get(action, action)),
                    result=tr("Zustand geändert") if changed else tr("war bereits so"),
                )
            )
        elif self.pending_notice:
            self.message.set(self.pending_notice)
            self.pending_notice = ""
        else:
            self.message.set(tr("Serverzustand wurde aktualisiert."))

    @staticmethod
    def _fill_tree(tree: Any, rows: list[tuple[object, ...]]) -> None:
        for item in tree.get_children():
            tree.delete(item)
        for row in rows:
            tree.insert("", "end", values=row)

    def copy_key(self) -> None:
        if self.current is None or not self.current.licence_key:
            self.message.set(tr("Für diese Lizenz liegt lokal kein vollständiger Schlüssel vor."))
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.current.licence_key)
        self.message.set(tr("Der vollständige Lizenzschlüssel liegt in der Zwischenablage."))

    def assign_current_transaction(self) -> None:
        """Verknüpft einen Pool-Schlüssel lokal mit dem Kauf im MoR-Dashboard."""
        if self.current is None or not self.archive_path.get().strip():
            self.message.set(tr("Zuerst eine Lizenz aus dem privaten Archiv auswählen."))
            return
        transaction = self.simpledialog.askstring(
            tr("Transaktion zuordnen"),
            tr("Transaktionskennung aus dem Merchant-of-Record-Dashboard:"),
            initialvalue=self.current.transaction,
            parent=self.root,
        )
        if transaction is None:
            return
        try:
            assign_transaction(Path(self.archive_path.get()), self.current.digest, transaction)
        except OperatorError as problem:
            self.message.set(str(problem))
            return
        digest = self.current.digest
        self.query.set(digest)
        self.pending_notice = tr(
            "Die MoR-Transaktion wurde eindeutig im privaten Archiv zugeordnet."
        )
        self.search()


def _default_token() -> Path | None:
    """Findet nur die dokumentierte lokale Vorgabe; geraten wird kein anderer Ort."""
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    candidate = Path(local) / "Solidon3D" / "server" / "operator.token"
    return candidate if candidate.is_file() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="privater JSON-Endpunkt")
    parser.add_argument("--token", type=Path, default=_default_token(), help="Betreiberzugang")
    parser.add_argument("--archive", type=Path, help="privates JSONL-Schlüsselarchiv")
    arguments = parser.parse_args(argv)
    try:
        import tkinter as tk
    except ImportError:
        print(
            "Tk fehlt in dieser Python-Installation. Das Werkzeug mit der "
            "vollständigen Desktop-Python-Installation starten."
        )
        return 1
    root = tk.Tk()
    SupportWindow(
        root,
        endpoint=arguments.endpoint,
        token_path=arguments.token,
        archive_path=arguments.archive,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
