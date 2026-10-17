"""Die Agentenschicht: Kontextaufbau, Werkzeuge, Transaktionskopplung (§26).

Der Agent ist kein Chatbot mit angehängtem 3D-Programm. Er arbeitet mit genau
den Operationen, die der Nutzer hat, sieht genau, was der Nutzer sieht, und
alles, was er tut, kommt als eine Transaktion an, die ein einziges Undo
zurücknimmt.

Das Paket exportiert nichts: Jeder Aufrufer importiert aus dem Untermodul.
Ohne Namen lädt dieses ``__init__`` auch nichts und kann sich mit keinem
Untermodul verklemmen (:mod:`app.core.lazy`).
"""
