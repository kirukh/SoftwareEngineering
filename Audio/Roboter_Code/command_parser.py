"""
Parser fuer deutsche Sprachbefehle.

Wird von beiden Seiten benutzt:
- Microphone_Code/audio_gui.py : lokale Anzeige des erkannten Befehls
- Roboter_Code/audio_controller.py : Weiterleitung an das Roboter-Interface

Die beiden Mapping-Tabellen unten uebersetzen deutsche Schluesselwoerter in
die englischen Bezeichner, die der Roboter erwartet (COCO-Objektklassen).
Die ID-Kommentare (z.B. "# 0 - person") entsprechen den COCO-Klassen-IDs.
"""

# Bekannte Befehle und Gegenstände, die der Roboter versteht
COMMANDS = {
    "suche":   "search",
    "such":    "search",
    "finde":   "search",
    "erkenne": "search",
    "drehe":   "drehen",
    "dreh":    "drehen",
    "drehen":  "drehen",
    "rotiere": "drehen",
}

DIRECTIONS = {
    "links":  "links",
    "rechts": "rechts",
}
# hier nur die häufigen Winkel eingetragen
NUMBER_WORDS = {
    "fünfzehn":           15,
    "dreißig":            30,
    "fünfundvierzig":     45,
    "neunzig":            90,
    "hundertachtzig":     180,
    "zweihundertsiebzig": 270,
    "dreihundertsechzig": 360,
}

ITEMS = {
    # 0 - person
    "person":           "person",
    "mensch":           "person",

    # 1 - bicycle
    "fahrrad":          "bicycle",
    "rad":              "bicycle",

    # 2 - car
    "auto":             "car",
    "wagen":            "car",
    "pkw":              "car",

    # 3 - motorcycle
    "motorrad":         "motorcycle",

    # 4 - airplane
    "flugzeug":         "airplane",

    # 5 - bus
    "bus":              "bus",

    # 6 - train
    "zug":              "train",
    "bahn":             "train",

    # 7 - truck
    "lkw":              "truck",
    "lastwagen":        "truck",

    # 8 - boat
    "boot":             "boat",
    "schiff":           "boat",

    # 9 - traffic light
    "ampel":            "traffic light",

    # 10 - fire hydrant
    "hydrant":          "fire hydrant",

    # 11 - stop sign
    "stoppschild":      "stop sign",

    # 12 - parking meter
    "parkuhr":          "parking meter",

    # 13 - bench
    "bank":             "bench",
    "sitzbank":         "bench",

    # 14 - bird
    "vogel":            "bird",

    # 15 - cat
    "katze":            "cat",

    # 16 - dog
    "hund":             "dog",

    # 17 - horse
    "pferd":            "horse",

    # 18 - sheep
    "schaf":            "sheep",

    # 19 - cow
    "kuh":              "cow",

    # 20 - elephant
    "elefant":          "elephant",

    # 21 - bear
    "bär":              "bear",

    # 22 - zebra
    "zebra":            "zebra",

    # 23 - giraffe
    "giraffe":          "giraffe",

    # 24 - backpack
    "rucksack":         "backpack",

    # 25 - umbrella
    "regenschirm":      "umbrella",
    "schirm":           "umbrella",

    # 26 - handbag
    "handtasche":       "handbag",
    "tasche":           "handbag",

    # 27 - tie
    "krawatte":         "tie",

    # 28 - suitcase
    "koffer":           "suitcase",

    # 29 - frisbee
    "frisbee":          "frisbee",

    # 30 - skis
    "ski":              "skis",
    "skier":            "skis",

    # 31 - snowboard
    "snowboard":        "snowboard",

    # 32 - sports ball
    "ball":             "sports ball",
    "sportball":        "sports ball",

    # 33 - kite
    "drachen":          "kite",

    # 34 - baseball bat
    "baseballschläger": "baseball bat",
    "schläger":         "baseball bat",

    # 35 - baseball glove
    "baseballhandschuh": "baseball glove",
    "handschuh":        "baseball glove",

    # 36 - skateboard
    "skateboard":       "skateboard",

    # 37 - surfboard
    "surfbrett":        "surfboard",

    # 38 - tennis racket
    "tennisschläger":   "tennis racket",

    # 39 - bottle
    "flasche":          "bottle",

    # 40 - wine glass
    "weinglas":         "wine glass",
    "glas":             "wine glass",

    # 41 - cup
    "tasse":            "cup",
    "becher":           "cup",

    # 42 - fork
    "gabel":            "fork",

    # 43 - knife
    "messer":           "knife",

    # 44 - spoon
    "löffel":           "spoon",

    # 45 - bowl
    "schüssel":         "bowl",
    "schale":           "bowl",

    # 46 - banana
    "banane":           "banana",

    # 47 - apple
    "apfel":            "apple",

    # 48 - sandwich
    "sandwich":         "sandwich",
    "brot":             "sandwich",

    # 49 - orange
    "orange":           "orange",
    "apfelsine":        "orange",

    # 50 - broccoli
    "brokkoli":         "broccoli",

    # 51 - carrot
    "karotte":          "carrot",
    "möhre":            "carrot",

    # 52 - hot dog
    "hotdog":           "hot dog",

    # 53 - pizza
    "pizza":            "pizza",

    # 54 - donut
    "donut":            "donut",
    "krapfen":          "donut",

    # 55 - cake
    "kuchen":           "cake",
    "torte":            "cake",

    # 56 - chair
    "stuhl":            "chair",

    # 57 - couch
    "sofa":             "couch",
    "couch":            "couch",

    # 58 - potted plant
    "pflanze":          "potted plant",
    "topfpflanze":      "potted plant",
    "blume":            "potted plant",

    # 59 - bed
    "bett":             "bed",

    # 60 - dining table
    "tisch":            "dining table",
    "esstisch":         "dining table",

    # 61 - toilet
    "toilette":         "toilet",
    "wc":               "toilet",
    "klo":              "toilet",

    # 62 - tv
    "fernseher":        "tv",
    "tv":               "tv",
    "bildschirm":       "tv",

    # 63 - laptop
    "laptop":           "laptop",
    "notebook":         "laptop",

    # 64 - mouse
    "maus":             "mouse",

    # 65 - remote
    "fernbedienung":    "remote",

    # 66 - keyboard
    "tastatur":         "keyboard",

    # 67 - cell phone
    "handy":            "smartphone",
    "smartphone":       "smartphone",
    "telefon":          "smartphone",

    # 68 - microwave
    "mikrowelle":       "microwave",

    # 69 - oven
    "ofen":             "oven",
    "backofen":         "oven",
    "herd":             "oven",

    # 70 - toaster
    "toaster":          "toaster",

    # 71 - sink
    "waschbecken":      "sink",
    "spüle":            "sink",

    # 72 - refrigerator
    "kühlschrank":      "refrigerator",

    # 73 - book
    "buch":             "book",

    # 74 - clock
    "uhr":              "clock",
    "wecker":           "clock",

    # 75 - vase
    "vase":             "vase",

    # 76 - scissors
    "schere":           "scissors",

    # 77 - teddy bear
    "teddybär":         "teddy bear",
    "teddy":            "teddy bear",

    # 78 - hair drier
    "haartrockner":     "hair drier",
    "fön":              "hair drier",

    # 79 - toothbrush
    "zahnbürste":       "toothbrush",
}


def parse_command(raw_text: str) -> dict:
    """
    Durchsucht den erkannten Text nach bekannten Befehlen und Gegenständen
    und gibt ein strukturiertes Befehls-Dictionary zurück.

    Args:
        raw_text: Der vom Spracherkenner gelieferte Rohtext

    Returns:
        dict mit command_build (bool), command (str), item (str)
    """
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
        return {
            "command_build": True,
            "command": command,
            "item": item,
        }

    return {"command_build": False}


def _find_command(words: list[str]) -> str | None:
    """Sucht nach dem ersten bekannten Befehlswort in der Wortliste."""
    for word in words:
        if word in COMMANDS:
            return COMMANDS[word]
    return None


def _find_item(words: list[str]) -> str | None:
    """Sucht nach dem ersten bekannten Gegenstand in der Wortliste."""
    for word in words:
        if word in ITEMS:
            return ITEMS[word]
    return None


def _find_angle(words: list[str]) -> int | None:
    """Sucht nach einem Winkelwert — als Ziffernstring oder deutsches Zahlwort."""
    for word in words:
        if word.isdigit():
            return int(word)
        if word in NUMBER_WORDS:
            return NUMBER_WORDS[word]
    return None


def _find_direction(words: list[str]) -> str | None:
    """Sucht nach 'links' oder 'rechts'."""
    for word in words:
        if word in DIRECTIONS:
            return DIRECTIONS[word]
    return None
