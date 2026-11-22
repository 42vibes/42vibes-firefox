# 42vibes Firefox-Themes

**Deutsch** · [English](README.md)

Zwei eigenständige Firefox-Themes — **42vibes Dark** und **42vibes Light** — aus
der gemeinsamen [42vibes-Palette](vendor/palette.json).

Firefox kann die Farben eines Themes automatisch umschalten: Ein einzelnes Theme
darf sowohl `dark_theme` als auch `light_theme` setzen, und Firefox verwendet die
Variante, die zum Farbschema von Betriebssystem oder Browsereinstellung passt.
Zwei getrennte Add-ons sind deshalb eine bewusste Designentscheidung — jede
Variante hat eine eigene Identität, lässt sich unabhängig installieren und
aktualisieren — und keine technische Notwendigkeit.

## Themes

| Ordner | `color_scheme` | Gecko-ID | Rahmen | Akzent |
| --- | --- | --- | --- | --- |
| `firefox/42vibes-dark` | `dark` | `42vibes-dark@42vibes.local` | `#050f18` | `#2fb59d` |
| `firefox/42vibes-light` | `light` | `42vibes-light@42vibes.local` | `#f7fafc` | `#177a69` |

Beide Themes färben Browser-Rahmen, Toolbars, Tabs, Adressleiste, Menüs, Sidebar
und die Neuer-Tab-Seite. Alle Werte stammen aus `semantic.*` und `ansi.*` in
`vendor/palette.json`. Jedes Manifest setzt
`browser_specific_settings.gecko.id` und `strict_min_version` („115.0“).

## Screenshots

**Sichtbare Evidenz.** Die beiden Aufnahmen unten zeigen Rahmen, Toolbars, Tabs
und Adressleiste des dunklen und des hellen Themes mit den Palettenfarben als
tatsächliche Pixel. Neuer-Tab-Seite, Popups (Menüs) und Sidebar sind **nicht**
visuell getestet: dafür gibt es keine Aufnahme, ihre Farben sind nur als
Manifest-Werte geprüft.

**Aufnahmeprotokoll.** Echte Aufnahmen aus Firefox 153.7 (Linux, Xvfb), Theme
über `about:debugging` als temporäres Add-on geladen. Keine
Automatisierungssitzung aktiv, daher ist die Adressleiste nicht markiert.

![42vibes Dark in Firefox](docs/firefox-dark.png)

![42vibes Light in Firefox](docs/firefox-light.png)

## Installation

1. `about:debugging#/runtime/this-firefox` in Firefox öffnen.
2. **Temporäres Add-on laden…** anklicken.
3. `firefox/42vibes-dark/manifest.json` auswählen (oder die helle Variante).

Temporäre Add-ons verschwinden beim Neustart von Firefox. Die Themes lokal zu
bauen und zu laden ist der primäre Weg; eine Listung auf AMO ist optional.

Für eine dauerhafte Installation gibt es zwei Wege:

* **Signierter Build (Release und Beta).** Signieren ist Pflicht: Release- und
  Beta-Firefox installieren nur signierte Add-ons. AMO signiert sowohl gelistete
  als auch selbst vertriebene Builds.
* **Unsignierte Selbstinstallation auf ESR (optional).** Firefox ESR akzeptiert
  ein unsigniertes Theme, wenn `xpinstall.signatures.required=false` gesetzt ist
  und das Manifest eine explizite `browser_specific_settings.gecko.id` trägt;
  `strict_min_version` ist hier „115.0“. Beide Varianten haben eine solche ID
  (`42vibes-dark@42vibes.local`, `42vibes-light@42vibes.local`) und behalten
  damit über Updates hinweg eine stabile Identität. Dieser Weg hebt eine
  Sicherheitssperre auf: Er ist als Option dokumentiert, nicht als Empfehlung.

## Kontraste

Die Review hat zwei interaktive Flächen als zu schwach gemessen. Sie werden jetzt
in `build.py` aus Palettenrollen abgeleitet: `border_strong` als Mischung aus
`border` und `interactive`, `surface_selected` aus `surface_high` und
`interactive`). Gemessene Kontraste, Dark und Light getrennt geprüft:

| Paar | Dark | Light | Minimum |
| --- | --- | --- | --- |
| `toolbar_field_border` auf `toolbar` | 3.36:1 | 3.30:1 | 3:1 |
| `popup_highlight` auf `popup` | 3.12:1 | 3.32:1 | 3:1 |
| `popup_highlight_text` auf `popup_highlight` | 4.71:1 | 4.78:1 | 4,5:1 |

`validate.py` prüft genau diese Paare; inaktive Tabs gegen die Toolbar tragen
die Affordanz nicht und sind nicht Teil dieser Prüfung.

## Grenzen

Firefox-Themes sind kein vollständiger UI-Skin. Sie setzen Farben für Rahmen,
Toolbars, Tabs, Adressleiste, Popups, Sidebar und die Neuer-Tab-Seite und liefern
Icons für den Add-on-Manager. Interne Seiten wie `about:preferences` lassen sich
nicht umgestalten, Toolbar- und Tab-Layout nicht umsortieren und die Form von
Tabs und Buttons nicht ändern.

`userChrome.css` kann mehr, wird von Mozilla aber nicht unterstützt, gehört nicht
zu diesem Repository und bricht bei UI-Änderungen. Diese Themes sind reine
WebExtensions und brauchen es nicht.

Chromium/Chrome wird bewusst nicht abgedeckt.

## Veröffentlichung

Die Veröffentlichung auf [addons.mozilla.org](https://addons.mozilla.org) (AMO)
ist optional: Der primäre Weg ist, die Themes aus diesem Repository zu bauen und
lokal zu laden. Wer eine Listung möchte, zahlt bei AMO nichts; AMO signiert
sowohl gelistete als auch selbst vertriebene Themes. `make package` erzeugt die
beiden ZIP-Dateien für den Upload — `web-ext` wird nicht benötigt.

## Generierte Dateien

Jede `manifest.json` und jedes Icon wird von `build.py` erzeugt; bitte nicht von
Hand bearbeiten. Farben in `vendor/palette.json` und die Rollenzuordnung in
`build.py` ändern, dann neu bauen.

`python3 build.py --out DIR` schreibt denselben Baum unterhalb von `DIR` statt
nach `firefox/`. `validate.py` baut damit zweimal in Wegwerf-Verzeichnisse und
vergleicht beide Läufe mit den eingecheckten Dateien; die Validierung
überschreibt also nie ein Artefakt.

Icons werden aus einem kleinen SVG gerendert: die „42“ besteht aus Blöcken, es
ist keine Schrift beteiligt. Fehlt ImageMagick (`magick` oder `convert`), wird
das Icon-Rendering übersprungen und als übersprungen gemeldet — nicht als
bestanden — und die eingecheckten PNGs bleiben unverändert.

## Entwicklung

```sh
make build      # Manifeste und Icons neu erzeugen
make validate   # Layout, Paletten-Zuordnung, Icons, Doku, Kontraste, Determinismus
make package    # dist/42vibes-firefox-{dark,light}.zip
make check      # build + validate
```

`validate.py` endet nur mit Exit 0, wenn beide temporären Builds byte-identisch
sind und mit den eingecheckten Artefakten übereinstimmen. Es schreibt nie ins
Repository. Benötigt Python 3.9+. ImageMagick und `zip` sind optional.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
