# Gesture Presenter — Reveal.js-Präsentation

Die kurze Produktpräsentation erklärt Problem, Lösung, Bedienung und Architektur
und leitet am Ende direkt zur separaten Forschungsarbeit über.

## Starten

Im Projektverzeichnis:

```bash
python3 -m http.server 8000
```

Danach <http://localhost:8000/presentation/> öffnen.

## Steuerung

- Pfeiltasten oder Leertaste: weiter
- Umschalt+Leertaste: zurück
- `F`: Vollbild
- `S`: Referentenansicht mit Notizen
- `O`: Folienübersicht

Elemente innerhalb einer Folie werden nach dem Folienwechsel automatisch und
mit kurzem Abstand eingeblendet. Zusätzliche Klicks für jede einzelne Animation
sind nicht notwendig.

Reveal.js wird über jsDelivr geladen. Ohne bereits zwischengespeicherte Dateien
benötigt die Präsentation daher eine Internetverbindung.
