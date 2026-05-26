# Team Visual — Sprint README

> Sprint-Länge: **1 Woche** | Hardware: **Raspberry Pi 5 + Hailo-8 AI Kit**
> Zentrale Schnittstelle: **HTTP-API** (`/track/start`, `/track/latest`, `/track/stop`)
> Default-Port: **7995** (Visual-Range 7991–8000)

---

## Rückblick auf alle Sprints

| Sprint | Zeitraum | Ziel | Status |
|--------|----------|------|--------|
| Sprint 1 | KW 17 – KW 18 | `search()` mit Hailo + YOLO-Fallback | ✅ Done |
| Sprint 2 | KW 18 – KW 19 | Tracking-Server mit Sliding-Window-Aggregation | ✅ Done |
| Sprint 3 | KW 19 – KW 20 | Full Rollout auf dem Pi + End-to-End mit allen Teams | ✅ Done |
| Sprint 4 | KW 20 – KW 21 | MJPEG-Live-Stream mit eingezeichneten Boxen | 🔄 In Progress |

---

## Sprint 4 (aktuell)

**Zeitraum:** KW 20 – KW 21 (12.05.2026 – 18.05.2026)

### Sprint Goal
**Bildübertragung ans Audio-Team**: Der Visual-Server stellt einen
MJPEG-Live-Stream (`GET /stream`) bereit, der das Kamerabild mit
eingezeichneten Bounding-Boxen, Labels und Confidence-Werten zeigt.
Das Audio-Team kann diesen Stream in seine Oberfläche einbetten — eine
gesuchte Person, die durchs Bild läuft, bekommt im Live-Video eine Box,
die ihr folgt.

### Architektur-Entscheidungen im Sprint

1. **Ein Detector, zwei Ausgänge.** Der laufende Detector produziert pro
   Frame weiterhin das `VisionResult` fürs Tracking — und legt zusätzlich
   das annotierte Kamerabild (JPEG) in einen thread-sicheren `FrameBuffer`.
   `/track/latest` und `/stream` lesen beide aus derselben Quelle. Kein
   zweiter Detector, keine zweite Kamera.
2. **`FrameBuffer` als Entkopplung.** Kamera und Detector greifen exklusiv
   auf die Hardware zu — `/stream` darf deshalb keine eigene Kamera öffnen.
   Der Detector schreibt in den Puffer, der HTTP-Endpoint liest nur. Der
   Puffer hält immer nur den neuesten Frame (für einen Live-View reicht das).
3. **MJPEG statt SSE/WebSocket.** MJPEG (`multipart/x-mixed-replace`) ist im
   Browser nativ einbettbar (`<img src>`) und bleibt konsistent mit der
   HTTP-Linie der anderen Endpoints. Für Tkinter (Audio-Team) ist kein
   natives Rendering möglich — dafür liefern wir `tkinter_stream_example.py`
   als fertige Vorlage mit.
4. **Boxen-Annotation pro Detector unterschiedlich.** YOLO: `result.plot()`
   liefert das annotierte Bild direkt. Hailo: das Overlay-Element der
   GStreamer-Pipeline brennt die Boxen ein, der annotierte Frame muss per
   Pad-Probe abgegriffen werden. Der Hailo-Pfad ist code-complete, aber
   noch nicht am Pi verifiziert (siehe offene Punkte).
5. **Stream-Parameter in `config.py`.** `stream_jpeg_quality` (Default 80)
   und `stream_fps` (Default 15) als neue Felder, per Env-Variable
   überschreibbar — konsistent mit der bestehenden Config-Logik aus T-22.

### User Stories

| ID | Story | Akzeptanzkriterium | SP |
|----|-------|--------------------|----|
| US-14 | Visual stellt einen Live-Stream des Kamerabilds bereit. | `GET /stream` liefert einen MJPEG-Multipart-Stream. | 2 |
| US-15 | Der Stream zeigt die erkannten Objekte mit Box. | Bei aktivem Tracking sind Bounding-Boxen, Label und Confidence im Bild eingezeichnet. | 3 |
| US-16 | Das Audio-Team kann den Stream einbinden. | Browser-Embed dokumentiert; Tkinter-Vorlage (`tkinter_stream_example.py`) liegt im Repo und läuft. | 2 |
| US-17 | Der Stream funktioniert mit beiden Detector-Backends. | Stream liefert annotierte Frames mit YOLO **und** Hailo. | 3 |

**Gesamt: 10 Story Points**

### Sprint Backlog

| ID | Task | Story | SP | Status |
|----|------|-------|----|--------|
| T-23 | `FrameBuffer` (thread-sicherer JPEG-Puffer) | US-14 | 1 | ✅ Done |
| T-24 | `GET /stream`-Endpoint in `server.py` (MJPEG-Generator) | US-14 | 1 | ✅ Done |
| T-25 | `YoloDetector`: annotierten Frame via `result.plot()` in den Puffer | US-15/17 | 1 | ✅ Done |
| T-26 | `HailoDetector`: Frame-Abgriff aus der GStreamer-Pipeline (Code) | US-15/17 | 2 | ✅ Code Done — Pi-Verifikation offen |
| T-27 | Stream-Parameter in `config.py` (`stream_jpeg_quality`, `stream_fps`) | US-14 | 0.5 | ✅ Done |
| T-28 | `tkinter_stream_example.py` als Vorlage fürs Audio-Team | US-16 | 1 | ✅ Done |
| T-29 | Doku: `README.md`, `Anleitung.md`, neue `TESTING.md`, `changes.md` | US-16 | 1 | ✅ Done |
| T-30 | Hailo-Stream am echten Pi verifizieren | US-17 | 2 | ⏳ Open |
| T-31 | Integrationstest mit Audio- + Controller-Team (Stream im Audio-GUI) | US-16 | 1.5 | ⏳ Open |

**Hinweis zu T-30:** Die Hailo-Verifikation des `/stream`-Endpoints hängt eng
am Pi-Live-Test T-20 aus Sprint 3 (Hailo allgemein am Pi). Ob T-30 als
Nachzug zu T-20 läuft oder ein eigenständiger Task bleibt, wird in der
nächsten Planung entschieden — abhängig auch von der offenen Abstimmung
mit Prof. Jehle (siehe offene Punkte).

### Definition of Ready

- Anforderung "Bildübertragung" vom Audio-Team gemeldet ✓
- Audio-Team-UI-Stack bekannt (Tkinter, kein Browser) ✓
- Detector-Abstraktion erlaubt Frame-Abgriff ohne zweite Kamera ✓

### Definition of Done

- `GET /stream` liefert einen MJPEG-Stream, im Browser einbettbar ✓
- Stream zeigt bei aktivem Tracking eingezeichnete Boxen (YOLO getestet) ✓
- Tkinter-Vorlage liegt im Repo und ist dokumentiert ✓
- Doku aktualisiert (`README`, `Anleitung`, `TESTING`, `changes`) ✓
- **Offen:** Hailo-Stream am Pi verifiziert (T-30)
- **Offen:** Integrationstest mit Audio- + Controller-Team bestanden (T-31)

### Offene Punkte / Risiken

- **Hailo-Stream am Pi noch nicht verifiziert (T-30).** Der Frame-Abgriff
  aus der GStreamer-Pipeline ist code-complete, aber ungetestet — Element-Name,
  Pixelformat und Pad müssen am Gerät geprüft werden. Solange das offen ist,
  funktioniert `/stream` nur mit YOLO sicher; unter Hailo *kann* der Stream
  leer bleiben. Das **Tracking** ist davon nicht betroffen.
- **Abstimmung mit Prof. Jehle ausstehend:** Ob der Stream zwingend über
  Hailo laufen muss oder ob die Aufteilung "Tracking auf Hailo, Stream-Boxen
  via YOLO" akzeptabel ist. Die Antwort entscheidet, wie dringend T-30 ist
  und ob daraus ein eigener Task wird. Anfrage ist raus, Antwort steht aus.
- **Integrationstest mit den anderen Teams offen (T-31).** Der Stream ist
  bisher nur isoliert (Laptop, YOLO, Browser + Tkinter-Vorlage) getestet.
  Der Test im echten Audio-GUI, zusammen mit Controller und Audio-Team,
  steht noch aus — synchroner Termin nötig.
- **Kamera-Exklusivität:** Hailo und YOLO greifen beide exklusiv auf die
  Kamera zu. Für eine Stream-Demo auf YOLO läuft der gesamte Visual-Server
  auf YOLO (Tracking inklusive) — Hailo und YOLO können nicht parallel
  dieselbe Kamera nutzen. Beim Joint-Test einplanen.

---

## Sprint 3 — abgeschlossen

**Zeitraum:** KW 19 – KW 20 (05.05.2026 – 11.05.2026)

### Sprint Goal
**End-to-End-Rollout auf dem Pi**: Audio-Team sendet COCO-Label → Controller
ruft Visual auf → Visual findet das Objekt und liefert die Koordinaten zurück.
Egal ob Hailo oder YOLO unter der Haube läuft, der Rollout muss
funktionieren.

### Architektur-Entscheidungen im Sprint

1. **Port-Festlegung 7995** in der Visual-Range 7991–8000 (Prof. Jehle hat
   die Ranges in KW 19 verteilt). Mittlerer Wert in der Range, damit später
   noch Platz für einen Video-Stream-Endpoint o.ä. ist.
2. **Auto-Fallback Hailo → YOLO** als hartes Sprint-Requirement: wenn das
   Hailo-Kit zur Laufzeit nicht initialisieren kann, fällt der Server
   stillschweigend (mit Log) auf YOLO zurück. Begründung: der Rollout darf
   nicht an einer wackeligen Hailo-Init scheitern. Wer explizit Hailo *will*
   (für Performance-Tests), setzt `VISUAL_DETECTOR=hailo` und kriegt einen
   harten Fehler.
3. **GET /health liefert aktiven Detector zurück** — kleine Erweiterung,
   damit das Controller-Team auf einen Blick sieht, ob im Auto-Modus
   Hailo oder Fallback aktiv ist.
4. **`VISUAL_HOST` konfigurierbar** (Default `127.0.0.1`). Für Single-Pi-
   Rollout reicht der Default; wenn der Audio-Laptop später extern zugreifen
   soll, `VISUAL_HOST=0.0.0.0`.
5. **Zentrale Konfiguration in `config.py`** — alle Tuning-Parameter in einer
   `VisualConfig`-Dataclass, überschreibbar per Env-Variable. Ersetzt die
   verstreute Env-Var-Logik aus Sprint 1/2 und schafft eine klare Quelle
   der Wahrheit, die bei `python config.py` sichtbar ist.

### User Stories

| ID | Story | Akzeptanzkriterium | SP |
|----|-------|--------------------|----|
| US-09 | Visual-Port liegt in der zugewiesenen Range (7991–8000). | Default-Port = 7995 in allen Files konsistent. | 1 |
| US-10 | Server läuft auch ohne funktionierendes Hailo-Kit. | Auto-Modus fällt bei Hailo-Fehler auf YOLO zurück, Server startet, `/health` zeigt aktiven Detector. | 2 |
| US-11 | Hailo-Path auf dem Pi getestet (T-10 aus Sprint 2 nachgezogen). | `live_e2e_test.py` läuft mit Hailo auf dem Pi, Treffer für mind. ein COCO-Label. | 3 |
| US-12 | Controller-Team kann uns ohne Rückfragen einbinden. | `Anleitung.md` ist vorhanden, deckt Start, API und Polling-Pattern ab. | 1 |
| US-13 | End-to-End: Audio → Controller → Visual → Controller → Aktion. | Joint-Test-Session: gesprochenes Objekt löst Detection aus, Controller bekommt sinnvolle Koordinaten. | 3 |

**Gesamt: 10 Story Points**

### Sprint Backlog

| ID | Task | Story | SP | Status |
|----|------|-------|----|--------|
| T-14 | Port-Migration 8000 → 7995 in allen Files | US-09 | 0.5 | ✅ Done |
| T-15 | Auto-Fallback in `_get_detector()` härten | US-10 | 1 | ✅ Done |
| T-16 | `/health` um `detector`-Feld erweitern, `VisualClient.health_info()` | US-10 | 0.5 | ✅ Done |
| T-17 | Hailo-Detector: robustes `_shutdown_pipeline()` mit Fallback-Pfaden | US-11 | 1 | ✅ Done |
| T-18 | `Anleitung.md` für Controller-Team schreiben | US-12 | 1 | ✅ Done |
| T-19 | `VISUAL_HOST` konfigurierbar (Default 127.0.0.1) | US-13 | 0.5 | ✅ Done |
| T-22 | Zentrale `config.py` (VisualConfig + Env-Override) | US-09/10 | 1 | ✅ Done |
| T-20 | Pi-Live-Session: Hailo-Stream zum Laufen bringen | US-11 | 3 | ⏳ Open |
| T-21 | Joint-Test mit Audio + Controller-Team | US-13 | 2.5 | ⏳ Open |

> **Hinweis:** T-20 und T-21 wurden im Sprint nicht abgeschlossen und in
> Sprint 4 weitergetragen. Der Sprint gilt als Done, weil das Sprint Goal
> (Rollout läuft, Auto-Fallback abgesichert) erreicht war; die zwei
> hardware-/teamabhängigen Tasks blieben als bekanntes Risiko offen.

### Definition of Ready

- Port-Ranges sind vom Prof verteilt ✓
- Audio-Team hat ihre Endpoints gemeldet (Port 8011 `/speech`) ✓
- COCO-Label-Mapping liegt beim Audio-Team ✓
- Hardware (Pi + Hailo-Kit) ist verfügbar oder ein Fallback ist definiert ✓

### Definition of Done

- Tests grün auf dem Laptop (Fake + Server + Live-E2E mit YOLO) ✓
- Server startet auf dem Pi (Hailo *oder* YOLO-Fallback)
- Controller-Team hat `Anleitung.md` gelesen, kann ohne Rückfragen integrieren
- Joint-End-to-End-Test bestanden: gesprochener Befehl löst Detection aus,
  Koordinaten kommen sinnvoll beim Controller an
- `/health` zeigt den tatsächlichen aktiven Detector, nicht den gewünschten
- Port 7995 konsistent in allen Files

### Offene Punkte / Risiken

- **Hailo-Live-Test auf dem Pi** noch nicht durchgeführt (T-20). Höchstes
  Risiko im Sprint. Geplante Joint-Session: tbd.
  → Abgesichert durch Auto-Fallback auf YOLO: der Rollout selbst läuft
  unabhängig davon ob Hailo zur Laufzeit funktioniert.
- **`app.shutdown()` bei Hailo:** unsicher, ob das so existiert. Fallback
  über `pipeline.set_state(Gst.State.NULL)` ist eingebaut — muss am
  echten Hailo verifiziert werden.
- **Joint-Test mit Audio:** synchroner Termin nötig. Audio kann
  unabhängig getestet werden (POST `/speech`), aber den Loop schließt erst
  der Controller, sobald alle drei Teams parallel laufen.
- **Latenz im Auto-Fallback-Pfad:** wenn Hailo *fast* funktioniert (z.B.
  hängt beim ersten Stream-Versuch), könnte der Fallback erst nach
  Timeout greifen. Im Worst Case Server beim ersten `/track/start` 30s+
  blockiert. Sollte beim Pi-Test geprüft werden.

---

## Sprint 2 — abgeschlossen

**Zeitraum:** KW 18 – KW 19 (28.04.2026 – 04.05.2026)

### Sprint Goal
Umstellung von einmaligem `search()` auf kontinuierliches **Tracking**:
Detector läuft im Hintergrund, schiebt jeden Frame in ein Sliding Window,
Controller pollt das aktuelle aggregierte Ergebnis per HTTP. Das Ergebnis
enthält zusätzlich zur Position (`x`, `y`) jetzt auch die Größe (`w`, `h`),
damit der Laserpointer das Ziel besser ansteuern kann.

### Architektur-Entscheidungen im Sprint

1. **HTTP-Server statt In-Process-Aufruf.** In Sprint 1 hatten wir REST
   abgelehnt. Mit der neuen Anforderung "Dauerfeuer" macht ein Server jetzt
   Sinn: Polling ist einheitlich mit den anderen Teams und einfach zu
   debuggen (`curl`).
2. **Polling statt SSE/WebSocket.** Polling alle 100ms ist für den Laser
   ausreichend, deutlich einfacher zu implementieren, und der Controller
   kann sein Pattern für alle Teams wiederverwenden.
3. **Sliding Window über die letzten 8 Frames** statt jedes Frame einzeln
   rauszugeben. Glättet Jitter, reduziert HTTP-Last, der Laser bleibt ruhiger.

### User Stories

| ID | Story | Akzeptanzkriterium | SP |
|----|-------|--------------------|----|
| US-05 | Detector im Streaming-Modus statt blockierend. | `stream(name, on_frame, stop_event)` läuft bis zum Stop. | 3 |
| US-06 | Sliding-Window-Aggregation über N Frames. | Mind. M Treffer im Fenster → `found=True` mit Mittelwerten. | 2 |
| US-07 | HTTP-API für den Controller. | `POST /track/start`, `GET /track/latest`, `POST /track/stop`. | 3 |
| US-08 | Bounding-Box-Größe (`w`, `h`) im Ergebnis. | Zusätzlich zu `x`, `y` normiert auf 0.0–1.0. | 1 |

**Gesamt: 9 Story Points** — alle abgeschlossen.

### Sprint Backlog (final)

| ID | Task | Story | SP | Status |
|----|------|-------|----|--------|
| T-08 | `DetectorProtocol.stream()` + `w`/`h` in `VisionResult` | US-05/08 | 1 | ✅ Done |
| T-09 | `YoloDetector.stream()` umbauen, w/h liefern | US-05/08 | 2 | ✅ Done |
| T-10 | `HailoDetector.stream()` umbauen, w/h liefern | US-05/08 | 2 | ✅ Code Done — Live-Test nach Sprint 3 T-20 verschoben |
| T-11 | `visual.py`: Tracking-API + Sliding-Window-Aggregation | US-06 | 2 | ✅ Done |
| T-12 | `server.py`: FastAPI mit `/track/*` Endpoints | US-07 | 1 | ✅ Done |
| T-13 | `test_visual.py`: Fake- und Server-Tests, `live_e2e_test.py` | US-05/06/07 | 1 | ✅ Done |

### Sprint-2-Retro (kurz)

- ✅ Tests grün auf dem Laptop
- ✅ Controller-Team konnte gegen Server pollen (in Sync-Meeting bestätigt)
- ✅ Alte API entfernt, keine Legacy-Pfade mehr
- ⏳ Hailo-Stream-Live-Test → übernommen in Sprint 3 als T-20
- 💡 Learning: Hardware-abhängige Tasks früher einplanen, nicht ans Sprint-Ende

---

## Sprint 1 — abgeschlossen

**Zeitraum:** KW 17 – KW 18 (21.04.2026 – 27.04.2026)

### Sprint Goal
Funktionierendes `search(object_name) -> dict` mit Hailo auf dem Pi und
YOLO als Laptop-Fallback. Detector-Abstraktion über `DetectorProtocol`,
damit das Visual-Modul ohne Hardware entwickelt werden kann.

### Wichtigste Outcomes

- `DetectorProtocol` etabliert; `HailoDetector`, `YoloDetector`,
  `MockDetector` als Implementierungen
- Einmalige `search()`-Funktion mit Timeout und Stable-Frame-Check
- COCO-Label-Mapping zwischen Audio und Visual abgestimmt: Audio mappt,
  Visual nimmt unverändert (Single Source: `coco.yaml`)
- Sprint-1-Retro: Architektur-Entscheidungen früher mit Controller-Team
  abstimmen → in Sprint 2 umgesetzt