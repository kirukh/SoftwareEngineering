# Änderungsprotokoll — 27.06.2026

**Bearbeiter:** Audio-Team  
**Betroffene Dateien:**
- `Audio/Microphone_Code/command_parser.py`
- `Audio/Roboter_Code/command_parser.py`

---

## Hintergrund: Aufgabe aus der letzten Vorlesung

Es soll ein neuer Befehl eingeführt werden, der den Roboter um einen gewissen Winkel drehen lässt. 
Das Controller-Team erhält einen neuen Befehlstyp, der den Roboter um einen frei wählbaren Winkel dreht. 

Bisher kannte der Parser nur den `"search"`-Befehl (Objekt suchen + anfahren). 
Für Dreh-Befehle wurde mit dem Controller-Team das folgendes JSON-Format besprochen:

```json
{"command_build": true, "command": "drehen", "item": "45 links"}
```

Der Wert `item` kodiert dabei Winkel und Richtung als zusammengesetzten String, z.B. `"30 rechts"` oder `"90 links"`.

---

## Geänderte Dateien

Beide Dateien sind inhaltlich identisch. 
Der Parser wird auf beiden Seiten (Mikrofon-Laptop und Roboter) verwendet, weshalb beide synchron gehalten werden müssen.

---

## Änderung 1 — Neue Befehls-Schlüsselwörter in `COMMANDS`

```python
COMMANDS = {
    "suche":   "search",
    "such":    "search",
    "finde":   "search",
    "erkenne": "search",
    "drehe":   "drehen",   # NEU
    "dreh":    "drehen",   # NEU
    "drehen":  "drehen",   # NEU
    "rotiere": "drehen",   # NEU
}
```

### Erklärung

Vosk erkennt gesprochene Sprache und liefert den Text wortwörtlich zurück. Wenn wir sagen "drehe dich", "dreh nach links" oder "rotiere nach links um x Grad" 
werden alle diese Varianten nun auf den internen Bezeichner `"drehen"` gemappt und an das Controller-Team übergeben.

---

## Änderung 2 — Neues `DIRECTIONS`-Dict

```python
DIRECTIONS = {
    "links":  "links",
    "rechts": "rechts",
}
```

### Erklärung

Richtungswörter werden separat vom `ITEMS`-Dict gehalten, das ausschließlich COCO-Objektklassen enthält. "links" und "rechts" passen dort nicht hinein und könnten künftige Suchanfragen stören. 
Das separate `DIRECTIONS`-Dict bringt eine klare Zuständigkeit und lässt sich unabhängig erweitern.

---

## Änderung 3 — Neues `NUMBER_WORDS`-Dict

Es können wur die folgenden Winkel per Sprachbefehl eingesprochen werden. 
Aus Gründen der Übersicht haben wir nur eine Auswahl an Winkeln aufgenommen.

```python
NUMBER_WORDS = {
    
    "fünfzehn":           15,
    "dreißig":            30,
    "fünfundvierzig":     45,
    "neunzig":            90,
    "hundertachtzig":     180,
    "zweihundertsiebzig": 270,
    "dreihundertsechzig": 360,
}
```

### Erklärung

Der Vosk-Spracherkenner (German-Modell) gibt Zahlen als ausgeschriebene Wörter aus, nicht als Ziffern — also `"dreißig"` statt `"30"`. 
Um Winkel aus der Spracheingabe zu lesen, braucht der Parser eine Übersetzungstabelle von Zahlwörtern zu Integer-Werten.

Das Dict enthält die gängigen Rotationswinkel von 15 bis 360 Grad. Als Fallback prüft `_find_angle()` zusätzlich, ob ein Wort ein reiner Ziffernstring ist (`"30".isdigit()`), 
da zukünftige Vosk-Versionen oder andere Erkennungsmodelle Zahlen eventuell doch als Ziffern ausgeben könnten.

---

## Änderung 4 — `parse_command()` erweitert


```python
def parse_command(raw_text: str) -> dict:
    if not raw_text:
        return {"command_build": False}

    words = raw_text.lower().split()
    command = _find_command(words)

    if command == "drehen":
        angle = _find_angle(words)
        direction = _find_direction(words)
        item = f"{angle or 30} {direction or 'rechts'}"
        return {"command_build": True, "command": "drehen", "item": item}

    item = _find_item(words)

    if command and item:
        return {"command_build": True, "command": command, "item": item}

    return {"command_build": False}
```

### Erklärung

Der ursprüngliche Parser erforderte zwingend **sowohl** ein Befehlswort **als auch** ein Gegenstandswort (z.B. "suche Hund"). 
Ein reiner Dreh-Befehl wie "drehe dich" hätte daher immer `command_build: false` ergeben, weil kein Gegenstand aus dem `ITEMS`-Dict vorkommt.

Damit auch dies funktioniert, haben wir den Parser mit einem Default-Wert von 30 Grad nach rechts ausgestattet.

Die neue Logik behandelt `"drehen"` als Sonderfall, der nicht zwingend ein Item benötigt:
- Winkel und Richtung werden separat gesucht.
- Fehlt der Winkel → Default **30 Grad**.
- Fehlt die Richtung → Default **rechts**.
- Das `item`-Feld wird als zusammengesetzter String aufgebaut: `f"{winkel} {richtung}"`.

Die bestehende `"search"`-Logik ist vollständig unverändert.

---

## Änderung 5 — Zwei neue Hilfsfunktionen

### `_find_angle()`

```python
def _find_angle(words: list[str]) -> int | None:
    """Sucht nach einem Winkelwert — als Ziffernstring oder deutsches Zahlwort."""
    for word in words:
        if word.isdigit():
            return int(word)
        if word in NUMBER_WORDS:
            return NUMBER_WORDS[word]
    return None
```

Durchsucht die Wortliste nach dem ersten Treffer, zuerst auf reine Ziffern-Strings und anschließens dann auf bekannte Zahlwörter. 
Gibt `None` zurück wenn nichts gefunden (→ Default-Logik in `parse_command`).

### `_find_direction()`

```python
def _find_direction(words: list[str]) -> str | None:
    """Sucht nach 'links' oder 'rechts'."""
    for word in words:
        if word in DIRECTIONS:
            return DIRECTIONS[word]
    return None
```

Durchsucht die Wortliste nach einem Richtungswort. 
Gibt `None` zurück wenn keines gefunden (→ Default `"rechts"`).

---

## Verhalten nach den Änderungen

| Gesprochener Satz | Ergebnis `item` |
|---|---|
| "drehe dich um dreißig Grad" | `"30 rechts"` (Default-Richtung) |
| "drehe dich um dreißig Grad links" | `"30 links"` |
| "dreh nach links" | `"30 links"` (Default-Winkel) |
| "rotiere neunzig rechts" | `"90 rechts"` |
| "dreh fünfundvierzig links" | `"45 links"` |
| "dreh dich" | `"30 rechts"` (beide Defaults) |
| "suche Hund" | `"dog"` (unverändert) |
| "hallo Welt" | `command_build: false` (unverändert) |

---

## Schnittstelle zum Controller-Team

Der Parser liefert ab sofort folgendes JSON für Dreh-Befehle:

```json
{
    "command_build": true,
    "command": "drehen",
    "item": "<winkel> <richtung>"
}
```

Beispiele: `"30 rechts"`, `"45 links"`, `"90 rechts"`.

---


