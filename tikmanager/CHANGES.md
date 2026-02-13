# CHANGES.md -- CoffeeVein-modifierad TIK Manager 4

Dokumentation av alla skillnader mellan original TIK Manager 4 (`tik_manager4-dev/tik_manager4/`, v4.5.1)
och CoffeeVein-modifierad version (`tikmanager/tik_manager4/tik_manager4/`, v4.5.0-baserad).

> **OBS:** Vår modifierade version bygger pa v4.5.0. Originalet i `tik_manager4-dev` ar v4.5.1.
> Manga UI-filer (dialog, layouts, mcv, widgets) har skiljer sig pa grund av uppstroms-uppdateringar
> i v4.5.1, INTE CoffeeVein-andringar. Dessa listas separat i slutet av detta dokument.

---

## CoffeeVein-specifika andringar

### 1. `dcc/extract_core.py`
**Typ:** Ny feature
**Beskrivning:**
- Ny `CancelledException`-klass -- exception som kastas nar anvandaren avbryter en extraktion.
- Nytt attribut `_progress_callback = None` i `__init__()` -- callback for progress-uppdateringar till UI.
- Ny metod `set_progress_callback(callback)` -- satter callback-funktion for progressmeddelanden.
- Ny `except CancelledException`-block i `extract()` -- fangar avbrytning, satter `state = "cancelled"` istallet for "failed", loggar som info istallet for error.

### 2. `dcc/nuke/extract/render.py`
**Typ:** Ny feature / Total omskrivning
**Beskrivning:**
Fullstandig omskrivning av Nuke render-extractorn med foljande forbattringar:
- **Farg andrad:** Fran (160, 15, 200) lila till (71, 143, 203) bla.
- **Import av utils:** Flyttad till lokal import inuti `__init__()` (undviker cirkulara importer).
- **Filmformat-stod:** `mov` tillagt i format-dropdown. Default andrad fran `"exr"` till `"Use Node Settings"`.
- **Colorspace-dropdown:** Andrad fran fri text (string) till combo-dropdown med fordefinierade varden (`Use Node Settings`, `scene_linear`, `rec709`, `sRGB`, `linear`, `Cineon`, `raw`).
- **`_cancel_requested` flagga:** Tillater UI-driven avbrytning.
- **`request_cancel()` metod:** Anropas av UI for att begara avbrytning.
- **`collect()` andrad:** Nu icke-statisk, samlar valda Write-noder forst (om nagot ar markerat), annars alla Write-noder. Originalversion filterade bort disabled noder -- ny version tar alla.
- **`_render_movie()` ny metod:** Renderar filmfiler (mov/mp4/avi) -- hela frame-rangen pa en gang. Stodjer ESC-avbrytning via Nukes interna progressbar. Tar bort partial renderingar vid avbrytning. Skriver render-tid till konsol.
- **`_render_sequence()` ny metod:** Renderar bildsekvenser frame-for-frame med `nuke.ProgressTask`. Visar progress, tid per frame, uppskattad aterstande tid. Stodjer avbrytning via bade ProgressTask och `_cancel_requested` flagga.
- **`_extract_default()` omskriven:**
  - Sparar originalinstallningar (file, file_type, colorspace) for varje Write-nod INNAN andringar.
  - Detekterar movie vs sequence baserat pa format.
  - Anropar `_render_movie()` respektive `_render_sequence()`.
  - **`finally`-block:** Aterstaller ALLTID originalinstallningar pa Write-noden (aven vid fel/avbrytning) -- detta saknas i originalet.
  - Seq-uppslag anvander `glob.glob` istallet for `fileseq` (externt beroende borttaget).
- **`fileseq`-beroende borttaget:** Originalversionen importerar `tik_manager4.external.fileseq`. Modifierad version anvander Python-standardbiblioteket `glob`.

### 3. `dcc/nuke/extract/movie.py`
**Typ:** Ny fil / Ny feature
**Beskrivning:**
Ny Movie-extractor for Nuke. Exporterar MOV/MP4 fran viewer eller vald nod.
- Skapar temporar Write-nod, renderar, rensar upp.
- Stodjer val av codec (mov64/mp4/avi) och kvalitet (Low/Medium/High/Max).
- Stodjer Input Range och Custom Range.
- **OBS:** Denna fil anvander `add_setting()` som inte finns i ExtractCore -- den anvander troligen en annan API-signatur och kan behova uppdateras for att fungera.

### 4. `dcc/nuke/extract/_render_original_backup.py`
**Typ:** Backup-fil
**Beskrivning:**
Kopia av den URSPRUNGLIGA `render.py` (fran originalet). Sparad som referens/backup.
Identisk med originalets `render.py` forutom att filmformat-detektering (mov/mp4/avi) lagts till utan den fulla progress/cancel-logiken.

### 5. `dcc/nuke/extract/source.py`
**Typ:** Ingen andring
**Beskrivning:**
Filerna ar identiska. Ingen orphan-funktion hittades i nagon av versionerna -- den har troligen redan blivit borttagen.

### 6. `dcc/nuke/extract/__init__.py`
**Typ:** Ingen andring
**Beskrivning:**
Filerna ar identiska. Autodiscovery-logiken laddar dynamiskt alla `.py`-filer som inte borjar med `_`. Det innebar att `movie.py` automatiskt laddas i modifierad version (ny extractor) medan `_render_original_backup.py` exkluderas (korrekt beteende tack vare `_`-prefix).

### 7. `dcc/nuke/utils.py`
**Typ:** Ny feature / Forbattring
**Beskrivning:**
- **Ny import:** `from PySide2 import QtWidgets, QtCore` tillagd.
- **`set_ranges()` omskriven:** Fran enkel 2-raders funktion till en komplett `FrameRangePanel` QDialog:
  - Dropdown med alla aktiva Read-noder.
  - Visar nodnamn (filnamn-baserat) och frame range.
  - "Apply to Project Settings"-knapp som uppdaterar `nuke.Root()` first/last frame och lasar rangen.
  - Fallback-meddelande om inga Read-noder finns.
  - **OBS Bugg:** Efter dialogen kors `nuke.Root()['first_frame'].setValue(range_list[0])` och `['last_frame'].setValue(range_list[-1])` AVEN om dialogen redan satt varden -- detta overrider potentiellt dialogens val. Dessutom kors dessa rader aven om inga Read-noder finns.
- **Utkommenterad gammal kod:** Innehaller utkommenterad alternativ implementation med `nuke.Panel`.

### 8. `dcc/nuke/main.py`
**Typ:** Ny feature
**Beskrivning:**
- Ny metod `sync_project_settings()` tillagd i `Dcc`-klassen.
- Synkar TIK Manager-projektegenskaper till Nuke Root: frame range (forst fran task, sedan fran projekt) och FPS.
- Visar meddelande via `nuke.message()` med synkade varden.

### 9. `dcc/nuke/ingest/render.py`
**Typ:** Ny fil / Ny feature
**Beskrivning:**
Ny Render-ingestor for Nuke. Importerar publicerade renderingar (EXR-sekvenser, MOV, etc).
- Stodjer bade bildsekvenser och filmfiler.
- Skapar Read-nod med korrekt file path (med/utan frame padding).
- Detekterar sekvens-monster (filer med frame-nummer).
- Stodjer kategorier: render, source, reference.

### 10. `dcc/nuke/ingest/movie.py`
**Typ:** Ny fil / Ny feature
**Beskrivning:**
Ny Movie-ingestor for Nuke. Importerar filmfiler (MOV, MP4, AVI, MXF, M4V).
- Skapar Read-nod UTAN frame padding.
- Forsoker lasa frame range fran filmens metadata.
- Stodjer kategorier: source, reference.
- Kommenterad colorspace-sattning for framtida anvandning.

### 11. `dcc/nuke/ingest/__init__.py`
**Typ:** Ingen andring
**Beskrivning:**
Identisk fil. Autodiscovery laddar automatiskt `render.py` och `movie.py` (nya filer).

### 12. `dcc/nuke/setup/auto_project_settings.py`
**Typ:** Ny fil / Ny feature
**Beskrivning:**
Automatisk applicering av projektinstallningar fran TIK Manager vid Nuke-start.
- Registrerar callback pa `nuke.addOnCreate(..., nodeClass="Root")`.
- Applicerar: frame range, FPS, resolution (skapar nytt format om det inte finns).
- Prioriteringsordning: task-data forst, sedan projekt-data, sedan fallback-varden.

### 13. `dcc/standalone/main.py`
**Typ:** Buggfix (PySide6-kompatibilitet)
**Beskrivning:**
- `QFontMetrics.width(text)` andrad till `QFontMetrics.horizontalAdvance(text)` i `text_to_image()`.
- `.width()` ar deprecated/borttagen i PySide6/Qt6. `.horizontalAdvance()` ar den korrekta ersattaren.

### 14. `ui/dialog/publish_dialog.py`
**Typ:** Ny feature
**Beskrivning:**
- **`extract_all()` utokad:**
  - Ny logik: Satter `progress_callback` pa varje extractor via `set_progress_callback()` sa att extractors kan uppdatera WaitDialogen med progressmeddelanden i realtid.
  - Ny hantering av `"cancelled"` state -- visar info-dialog och avbryter publiceringen.
  - Callback-hanteringens `display()`-anrop behalls for att visa dialogen.

### 15. `ui/widgets/pop.py`
**Typ:** Forbattring
**Beskrivning:**
- **Modal andrad:** Fran `setModal(True)` till `setModal(False)` -- dialogen ar nu icke-modal for att lata ESC-tangenten na Nukes `ProgressTask` for render-avbrytning.
- **`set_message()` forenklad:** Borttagna `self.close()` och `self.show()` anrop. Uppdaterar nu bara text och processar events -- undviker flimmer och z-order-problem.

### 16. `management/__init__.py`
**Typ:** Konfigurationsandring
**Beskrivning:**
- ShotGrid-integrationen ar utkommenterad (4 rader):
  ```python
  # from tik_manager4.management.shotgrid.main import ...
  # from tik_manager4.management.shotgrid.ui_extension import ...
  # platforms["shotgrid"] = sg_platform
  # ui_extensions["shotgrid"] = sg_ui_extension
  ```
- Kitsu-integrationen behalls aktiv.
- Trolig anledning: ShotGrid-modul ar inte tillganglig eller ShotGrid anvands inte i CoffeeVein-pipelinen.

### 17. `_version.py`
**Typ:** Versionsandring
**Beskrivning:**
- Original: `('4', '5', '1')` -- d.v.s. v4.5.1
- Modifierad: `('4', '5', '0')` -- d.v.s. v4.5.0
- Var modifierade version bygger pa en aldre version av tik_manager4.

### 18. `dcc/nuke/extract/tmp/render - Copy.py` och `dcc/nuke/extract/tmp/render_.py`
**Typ:** Temporara filer
**Beskrivning:**
Utvecklingskopior/experiment-filer i `tmp/`-mappen. Bor inte levereras.

### 19. `dcc/nuke/__init__.py`
**Typ:** Ingen andring
**Beskrivning:**
Bada filerna ar tomma (0 rader). Identiska.

---

## Uppstroms-skillnader (v4.5.0 vs v4.5.1)

Foljande filer skiljer sig INTE pa grund av CoffeeVein-andringar utan pa grund av att var version bygger pa v4.5.0
medan originalet ar v4.5.1. Dessa ar uppstroms-uppdateringar.

### UI-andringar i v4.5.1
De storsta andringarna ar att `ValidateRow` och `ExtractRow` i `publish_dialog.py` andrades
fran `QHBoxLayout` (v4.5.0, var version) till `QWidget` (v4.5.1). Liknande refaktorering
genomfordes i manga andra UI-filer:

| Fil | Andring i v4.5.1 |
|-----|-------------------|
| `ui/dialog/publish_dialog.py` | ValidateRow/ExtractRow: QHBoxLayout -> QWidget, CollapsibleLayout och SettingsLayout tar nu parent-parameter |
| `ui/dialog/project_dialog.py` | Uppstroms UI-refaktorering |
| `ui/dialog/settings_dialog.py` | Uppstroms UI-refaktorering |
| `ui/dialog/subproject_dialog.py` | Uppstroms UI-refaktorering |
| `ui/dialog/task_dialog.py` | Uppstroms UI-refaktorering |
| `ui/dialog/user_dialog.py` | Uppstroms UI-refaktorering |
| `ui/dialog/work_dialog.py` | Uppstroms UI-refaktorering |
| `ui/dialog/__init__.py` | Uppstroms andring |
| `ui/main.py` | Uppstroms andring |
| `ui/layouts/collapsible_layout.py` | QLayout -> QWidget refaktorering |
| `ui/layouts/settings_layout.py` | QLayout -> QWidget refaktorering |
| `ui/layouts/__init__.py` | Uppstroms andring |
| `ui/mcv/category_mcv.py` | Uppstroms andring |
| `ui/mcv/project_mcv.py` | Uppstroms andring |
| `ui/mcv/subproject_mcv.py` | Uppstroms andring |
| `ui/mcv/task_mcv.py` | Uppstroms andring |
| `ui/mcv/user_mcv.py` | Uppstroms andring |
| `ui/mcv/version_mcv.py` | Uppstroms andring |
| `ui/mcv/__init__.py` | Uppstroms andring |
| `ui/widgets/browser.py` | Uppstroms andring |
| `ui/widgets/common.py` | Uppstroms andring |
| `ui/widgets/path_browser.py` | Uppstroms andring |
| `ui/widgets/settings_widgets.py` | Uppstroms andring |
| `ui/widgets/signals.py` | Uppstroms andring |
| `ui/widgets/validated_string.py` | Uppstroms andring |
| `ui/widgets/value_widgets.py` | Uppstroms andring |
| `ui/widgets/__init__.py` | Uppstroms andring |

### External/vendor-andringar
Alla filer under `external/shotgunsoftware/` skiljer sig ocksa mellan versionerna.
Detta ar Autodesk ShotGrid-beroenden (tank, shotgun_api3, yaml, ruamel_yaml) som
uppdaterats i v4.5.1. Dessa filer har INTE modifierats av CoffeeVein.

---

## Sammanfattning

| Kategori | Antal filer |
|----------|-------------|
| CoffeeVein-specifika andringar | 11 filer |
| Nya filer (CoffeeVein) | 6 filer |
| Inga andringar (verifierat identiska) | 3 filer |
| Uppstroms UI-skillnader (v4.5.0 vs v4.5.1) | ~27 filer |
| Uppstroms external/vendor-skillnader | ~120+ filer |
| Temporara filer (bor tas bort) | 2 filer |

### Att gora vid uppgradering till v4.5.1+:
1. Applicera CoffeeVein-andringar (punkt 1-16 ovan) pa den nya versionen.
2. Testa att `FrameRangePanel` i `utils.py` fungerar med ny UI-arkitektur.
3. Se over bugg i `set_ranges()` -- dubbelskrivning av frame range.
4. Verifiera att `movie.py` extractor fungerar med korrekt API.
5. Avgora om ShotGrid-stod behovs (nu utkommenterat).
