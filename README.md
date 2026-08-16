# 🌍 Earthquake Monitor (INGV + USGS + EMSC) for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/lucabarsanti/INGV_USGS_Earthquake/actions/workflows/validate.yml/badge.svg)](https://github.com/lucabarsanti/INGV_USGS_Earthquake/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**English** | [Italiano](#-italiano)

Real-time earthquake monitoring for Home Assistant, combining **INGV**
(Istituto Nazionale di Geofisica e Vulcanologia), **USGS** (United States
Geological Survey) and **EMSC** (European-Mediterranean Seismological Centre)
into a single integration — with a beautiful **Leaflet map card**,
distance/magnitude **alerts**, events for **notifications**, and a plugin
architecture ready for a future **local seismograph** (Raspberry Shake,
MQTT, …).

<p align="center"><img src="docs/screenshot-card.png" width="420" alt="earthquake-map-card screenshot" /></p>

> ⚠️ **This is NOT an earthquake early-warning system.** Data arrives from
> public catalogs minutes after an event and must never be relied upon for
> life-safety decisions.

## ✨ Features

- 🇮🇹 **INGV** + 🌎 **USGS** + 🇪🇺 **EMSC** in one place, with smart
  cross-network de-duplication (INGV > EMSC > USGS for the same event)
- 📏 Everything is computed **relative to your home** (or any coordinates):
  distance, monitoring radius, alert radius, maximum depth
- 🔔 **Alert engine**: binary sensor turns on when a quake happens within
  *X km* and above magnitude *Y* in the last *N* minutes (and turns off
  punctually) — plus a `earthquake_monitor_quake` event fired for **every new
  quake** and a `earthquake_monitor_quake_updated` event when a magnitude is
  **revised** significantly
- 🧪 **`simulate_quake` service** to test your automations and notifications
  without waiting for a real earthquake
- 🗺️ **Custom Lovelace card** with a Leaflet map (CARTO / OpenStreetMap
  tiles, automatic dark mode, **visual editor**, EN/IT localization),
  magnitude-scaled markers, popups with tsunami/felt info, alert-radius circle
  and a clickable list — auto-registered, zero manual resources, **no CDN**
  (Leaflet is bundled and served locally)
- 📍 `geo_location` entities, so quakes also appear on the built-in HA map
- 🌊 USGS extras per quake: **tsunami flag**, felt reports, ShakeMap intensity
- 🧩 **Pluggable source architecture** — a local seismograph source is planned
  and slots in without touching the rest of the code
- 🛡️ Solid: connection test at setup, per-source failure **repair issues**,
  state persisted across restarts (no missed or duplicated events), full
  **test suite** run in CI
- 🛠️ UI configuration (config flow + options flow), diagnostics, translations
  (English + Italiano), notification **blueprint** included

## 📦 Installation

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories**
2. Repository: `https://github.com/lucabarsanti/INGV_USGS_Earthquake` — Category: **Integration**
3. Install **Earthquake Monitor (INGV + USGS)** and restart Home Assistant
4. **Settings → Devices & Services → Add Integration → Earthquake Monitor**

### Manual

Copy `custom_components/earthquake_monitor` into your `config/custom_components/`
folder and restart Home Assistant.

## ⚙️ Configuration (all via UI)

| Option | Default | Description |
|---|---|---|
| Latitude / Longitude | your home | Reference point for distances |
| Data sources | INGV + USGS | INGV, USGS, EMSC in any combination |
| Monitoring radius | 500 km | Quakes farther away are ignored |
| Minimum magnitude | 2.0 | Quakes weaker than this are ignored |
| Alert radius | 100 km | Alert condition: distance |
| Alert minimum magnitude | 3.5 | Alert condition: magnitude |
| Alert active window | 60 min | How long the alert sensor stays on |
| Maximum depth | 700 km | Deeper quakes are ignored |
| History window | 24 h | Lookback for lists and counters |
| Update interval | 5 min | Polling interval |

Every option can be changed later from **Configure** on the integration.

## 🧭 Entities

| Entity | Description |
|---|---|
| `sensor.*_last_earthquake` | Magnitude of the most recent quake. Attributes include the full quake and a `quakes` list (up to 50) used by the map card |
| `sensor.*_nearest_earthquake` | Distance (km) to the closest quake |
| `sensor.*_strongest_earthquake` | Strongest magnitude in the history window |
| `sensor.*_earthquake_count` | Number of quakes in the window (with per-source breakdown) |
| `sensor.*_last_alert` | Timestamp of the last alert (survives restarts) |
| `binary_sensor.*_earthquake_alert` | **On** when a recent quake matches the alert distance + magnitude |
| `geo_location.*` | One entity per quake, visible on the standard HA map |

Services:

- `earthquake_monitor.refresh` — refresh on demand
- `earthquake_monitor.simulate_quake` — fire a synthetic
  `earthquake_monitor_quake` event (choose magnitude, distance, depth, place)
  to **test automations, the blueprint and push notifications** safely

## 🗺️ Map card

The card is registered automatically and has a **visual editor** — just add
"Earthquake Map Card" from the card picker, or in YAML:

```yaml
type: custom:earthquake-map-card
entity: sensor.earthquake_monitor_last_earthquake
title: Earthquakes
height: 420          # px, optional
zoom: 6              # optional
tiles: auto          # auto | carto_light | carto_dark | osm
show_list: true      # list under the map
max_list: 8
show_radius: true    # dashed alert-radius circle around home
follow_last: false   # keep the map centered on the latest quake
```

Markers are colored and sized by magnitude; popups show magnitude, place,
time, depth, distance, tsunami/felt info and a link to the INGV/USGS/EMSC
event page. Tiles follow your light/dark theme automatically with
`tiles: auto`. Leaflet is bundled with the integration and served locally —
the only external requests are the map tiles themselves.

## 🔔 Notifications

### Blueprint (easiest)

Import the included blueprint and pick distance, magnitude and your phone:

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Flucabarsanti%2FINGV_USGS_Earthquake%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fearthquake_monitor%2Fearthquake_notification.yaml)

### Manual automation on the event

Every new quake fires `earthquake_monitor_quake` with `magnitude`,
`distance_km`, `place`, `depth_km`, `latitude`, `longitude`, `source`, `url`,
`time`, `tsunami`, `felt`, `mmi` and `is_alert` (true when it matches your
alert settings). When a catalog revises a magnitude by ≥ 0.3, a
`earthquake_monitor_quake_updated` event fires with the same payload plus
`previous_magnitude`. Test everything with the `simulate_quake` service
(Developer tools → Actions).

```yaml
automation:
  - alias: Earthquake push
    trigger:
      - platform: event
        event_type: earthquake_monitor_quake
    condition:
      - "{{ trigger.event.data.distance_km <= 80 and trigger.event.data.magnitude >= 3.0 }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "🌍 Earthquake M {{ trigger.event.data.magnitude }}"
          message: >-
            {{ trigger.event.data.place }} —
            {{ trigger.event.data.distance_km }} km from home
```

Or simply trigger on `binary_sensor.*_earthquake_alert` turning **on**.

## 🔭 Roadmap

- **Local seismograph support** — the source layer is already abstracted
  (`sources/base.py`); planned backends: Raspberry Shake local API, generic
  MQTT seismograph topic, Seedlink. See `sources/local.py`.
- Optional MapLibre GL / OpenFreeMap vector-tile renderer for the card
- Long-term statistics and magnitude histogram
- Icon on [home-assistant/brands](https://github.com/home-assistant/brands)

Contributions are welcome — adding a source only requires implementing one
class and registering it.

## 🙏 Data & attribution

- **INGV** — earthquake data from the [INGV FDSN event web service](https://webservices.ingv.it/), licensed **CC BY 4.0** © INGV
- **USGS** — earthquake data from the [USGS FDSN event web service](https://earthquake.usgs.gov/fdsnws/event/1/), public domain
- **EMSC** — earthquake data from the [EMSC seismicportal](https://www.seismicportal.eu/)
- **Maps** — [Leaflet](https://leafletjs.com/) (BSD-2, bundled); tiles by [CARTO](https://carto.com/attributions) / [OpenStreetMap](https://www.openstreetmap.org/copyright) © OpenStreetMap contributors

---

# 🇮🇹 Italiano

Monitoraggio dei terremoti in tempo reale per Home Assistant, che unisce
**INGV** (Istituto Nazionale di Geofisica e Vulcanologia), **USGS** (United
States Geological Survey) ed **EMSC** (Centro Sismologico Euro-Mediterraneo)
in un'unica integrazione — con una bella **scheda mappa Leaflet**, **allerte**
per distanza/magnitudo, eventi per le **notifiche** e un'architettura pronta
per un futuro **sismografo locale** (Raspberry Shake, MQTT, …).

<p align="center"><img src="docs/screenshot-card.png" width="420" alt="screenshot della scheda earthquake-map-card" /></p>

> ⚠️ **NON è un sistema di allarme sismico (early warning).** I dati arrivano
> dai cataloghi pubblici minuti dopo l'evento e non devono mai essere usati
> per decisioni di sicurezza personale.

## ✨ Funzionalità

- 🇮🇹 **INGV** + 🌎 **USGS** + 🇪🇺 **EMSC** insieme, con de-duplicazione
  intelligente tra le reti (per lo stesso evento vince INGV > EMSC > USGS)
- 📏 Tutto è calcolato **rispetto a casa tua** (o a coordinate qualsiasi):
  distanza, raggio di monitoraggio, raggio di allerta, profondità massima
- 🔔 **Motore di allerta**: un binary sensor si attiva quando avviene un
  terremoto entro *X km* e sopra magnitudo *Y* negli ultimi *N* minuti (e si
  spegne puntuale) — più un evento `earthquake_monitor_quake` per **ogni
  nuovo terremoto** e un evento `earthquake_monitor_quake_updated` quando una
  magnitudo viene **rivista** in modo significativo
- 🧪 **Servizio `simulate_quake`** per testare automazioni e notifiche senza
  aspettare un terremoto vero
- 🗺️ **Scheda Lovelace personalizzata** con mappa Leaflet (tile CARTO /
  OpenStreetMap, dark mode automatica, **editor visuale**, localizzazione
  IT/EN), marker proporzionali alla magnitudo, popup con info tsunami e
  segnalazioni, cerchio del raggio di allerta e lista cliccabile — registrata
  automaticamente, zero risorse manuali, **niente CDN** (Leaflet è incluso e
  servito in locale)
- 📍 Entità `geo_location`: i terremoti compaiono anche sulla mappa nativa di HA
- 🌊 Extra USGS per ogni evento: **flag tsunami**, segnalazioni, intensità ShakeMap
- 🧩 **Architettura a sorgenti plug-in** — il sismografo locale è previsto e
  si aggiungerà senza toccare il resto del codice
- 🛡️ Solidità: test di connessione al setup, **repair issue** per sorgenti in
  errore, stato persistito ai riavvii (niente eventi persi o duplicati),
  **suite di test** completa eseguita in CI
- 🛠️ Configurazione da interfaccia (config flow + opzioni), diagnostica,
  traduzioni (inglese + italiano), **blueprint** di notifica incluso

## 📦 Installazione

### HACS (consigliato)

1. HACS → ⋮ → **Repository personalizzati**
2. Repository: `https://github.com/lucabarsanti/INGV_USGS_Earthquake` — Categoria: **Integrazione**
3. Installa **Earthquake Monitor (INGV + USGS)** e riavvia Home Assistant
4. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Earthquake Monitor**

### Manuale

Copia `custom_components/earthquake_monitor` dentro `config/custom_components/`
e riavvia Home Assistant.

## ⚙️ Configurazione (tutta da interfaccia)

| Opzione | Default | Descrizione |
|---|---|---|
| Latitudine / Longitudine | casa | Punto di riferimento per le distanze |
| Sorgenti dati | INGV + USGS | INGV, USGS, EMSC in qualsiasi combinazione |
| Raggio di monitoraggio | 500 km | I terremoti più lontani vengono ignorati |
| Magnitudo minima | 2.0 | I terremoti più deboli vengono ignorati |
| Raggio di allerta | 100 km | Condizione di allerta: distanza |
| Magnitudo minima di allerta | 3.5 | Condizione di allerta: magnitudo |
| Durata dell'allerta | 60 min | Per quanto resta attivo il sensore di allerta |
| Profondità massima | 700 km | I terremoti più profondi vengono ignorati |
| Finestra storica | 24 h | Periodo per liste e contatori |
| Intervallo di aggiornamento | 5 min | Frequenza di polling |

Ogni opzione è modificabile in seguito da **Configura** sull'integrazione.

## 🧭 Entità

| Entità | Descrizione |
|---|---|
| `sensor.*_last_earthquake` | Magnitudo dell'ultimo terremoto. Negli attributi ci sono tutti i dettagli e la lista `quakes` (fino a 50) usata dalla scheda mappa |
| `sensor.*_nearest_earthquake` | Distanza (km) del terremoto più vicino |
| `sensor.*_strongest_earthquake` | Magnitudo più alta nella finestra storica |
| `sensor.*_earthquake_count` | Numero di terremoti nella finestra (con dettaglio per sorgente) |
| `sensor.*_last_alert` | Timestamp dell'ultima allerta (sopravvive ai riavvii) |
| `binary_sensor.*_earthquake_alert` | **On** quando un terremoto recente rientra in distanza + magnitudo di allerta |
| `geo_location.*` | Un'entità per terremoto, visibile sulla mappa standard di HA |

Servizi:

- `earthquake_monitor.refresh` — aggiornamento immediato
- `earthquake_monitor.simulate_quake` — genera un evento
  `earthquake_monitor_quake` sintetico (scegli magnitudo, distanza,
  profondità, luogo) per **testare in sicurezza automazioni, blueprint e
  notifiche push**

## 🗺️ Scheda mappa

La scheda si registra da sola e ha l'**editor visuale** — aggiungi
"Earthquake Map Card" dal selettore delle schede, oppure in YAML:

```yaml
type: custom:earthquake-map-card
entity: sensor.earthquake_monitor_last_earthquake
title: Terremoti
height: 420          # px, opzionale
zoom: 6              # opzionale
tiles: auto          # auto | carto_light | carto_dark | osm
show_list: true      # lista sotto la mappa
max_list: 8
show_radius: true    # cerchio tratteggiato del raggio di allerta
follow_last: false   # tiene la mappa centrata sull'ultimo evento
```

I marker sono colorati e dimensionati in base alla magnitudo; i popup mostrano
magnitudo, luogo, orario, profondità, distanza, info tsunami/segnalazioni e il
link alla pagina INGV/USGS/EMSC dell'evento. Con `tiles: auto` la mappa segue
il tema chiaro/scuro. Leaflet è incluso nell'integrazione e servito in locale —
le uniche richieste esterne sono le tile della mappa.

## 🔔 Notifiche

### Blueprint (il modo più semplice)

Importa il blueprint incluso e scegli distanza, magnitudo e il tuo telefono:

[![Apri la tua istanza Home Assistant e mostra il dialogo di importazione blueprint.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Flucabarsanti%2FINGV_USGS_Earthquake%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fearthquake_monitor%2Fearthquake_notification.yaml)

### Automazione manuale sull'evento

Ogni nuovo terremoto genera l'evento `earthquake_monitor_quake` con
`magnitude`, `distance_km`, `place`, `depth_km`, `latitude`, `longitude`,
`source`, `url`, `time`, `tsunami`, `felt`, `mmi` e `is_alert`. Quando un
catalogo rivede una magnitudo di ≥ 0.3 viene generato
`earthquake_monitor_quake_updated` con in più `previous_magnitude`. Puoi
testare tutto con il servizio `simulate_quake` (Strumenti per sviluppatori →
Azioni):

```yaml
automation:
  - alias: Notifica terremoto
    trigger:
      - platform: event
        event_type: earthquake_monitor_quake
    condition:
      - "{{ trigger.event.data.distance_km <= 80 and trigger.event.data.magnitude >= 3.0 }}"
    action:
      - service: notify.mobile_app_tuo_telefono
        data:
          title: "🌍 Terremoto M {{ trigger.event.data.magnitude }}"
          message: >-
            {{ trigger.event.data.place }} —
            a {{ trigger.event.data.distance_km }} km da casa
```

Oppure usa direttamente `binary_sensor.*_earthquake_alert` come trigger.

## 🔭 Roadmap

- **Supporto sismografo locale** — il livello sorgenti è già astratto
  (`sources/base.py`); backend previsti: API locale Raspberry Shake, topic
  MQTT generico, Seedlink. Vedi `sources/local.py`.
- Renderer vettoriale MapLibre GL / OpenFreeMap opzionale per la scheda
- Statistiche a lungo termine e istogramma delle magnitudo
- Icona su [home-assistant/brands](https://github.com/home-assistant/brands)

I contributi sono benvenuti — aggiungere una sorgente richiede una sola
classe da implementare e registrare.

## 🙏 Dati e attribuzioni

- **INGV** — dati sismici dal [servizio FDSN INGV](https://webservices.ingv.it/), licenza **CC BY 4.0** © INGV
- **USGS** — dati sismici dal [servizio FDSN USGS](https://earthquake.usgs.gov/fdsnws/event/1/), pubblico dominio
- **EMSC** — dati sismici dal [seismicportal EMSC](https://www.seismicportal.eu/)
- **Mappe** — [Leaflet](https://leafletjs.com/) (BSD-2, incluso); tile di [CARTO](https://carto.com/attributions) / [OpenStreetMap](https://www.openstreetmap.org/copyright) © OpenStreetMap contributors

## 📄 License / Licenza

[MIT](LICENSE)
