<p align="center">
  <img src="https://raw.githubusercontent.com/cierzniak/ha-dynamiczne-info/main/custom_components/dynamiczne_info/brand/logo@2x.png" alt="dynamiczne.info" height="96">
</p>

# dynamiczne.info - Home Assistant

Integracja Home Assistant **wraz z** kartą Lovelace dla godzinowych cen prądu
[dynamiczne.info](https://dynamiczne.info). Wystawia gotową pod automatyzacje
rekomendację na każdą godzinę: **używaj / ogranicz / sprzedaj**, oraz
**harmonogramy odbiorników** (EV, bojler, ...), które same wybierają najtańsze godziny.

Korzysta z publicznego API dynamiczne.info (`GET /api/v1/outlook/{operator}/{tariff}`)
i zamienia je na sensory, na których oprzesz automatyzacje - kiedy włączyć urządzenia
albo ładować magazyn (tanie godziny), kiedy ograniczyć pobór (drogie godziny), a kiedy
rozładować / sprzedać do sieci (wysoka cena odkupu).

> Integracja nazywała się wcześniej **Pstryk Fixing** (`pstryk_fixing`, repozytorium
> `cierzniak/ha-pstryk-fixing`). Przechodzisz ze starej wersji? Zobacz
> [Migracja z Pstryk Fixing](#migracja-z-pstryk-fixing).

## Wymagania

- Home Assistant `2025.3` lub nowszy (API podwpisów konfiguracji jest wymagane
  przez całą integrację, również bez dodanych odbiorników).
- Dostęp sieciowy do `https://dynamiczne.info` (publiczne API; bez konta, bez klucza).

## Instalacja (HACS / Katalog społeczności)

Najprościej przyciskiem (otwiera repozytorium w HACS albo w Katalogu społeczności, zależnie
od wersji HA):

[![Otwórz repozytorium w Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=cierzniak&repository=ha-dynamiczne-info&category=integration)

Ręcznie:

1. Dodaj repozytorium `https://github.com/cierzniak/ha-dynamiczne-info` jako własne,
   typ **Integracja** (*Integration*):
   - **HA 2026.11 i nowsze:** Ustawienia (*Settings*) -> **Katalog społeczności**
     (*Marketplace*) -> ⋮ -> *Niestandardowe repozytoria* (*Custom repositories*);
     wymaga połączenia z GitHubem, kreator to zaproponuje,
   - **HA do 2026.10:** HACS -> ⋮ -> *Niestandardowe repozytoria* (*Custom repositories*).
2. Zainstaluj (*Install*) **dynamiczne.info** i zrestartuj Home Assistant.

Karta Lovelace (`custom:dynamiczne-info-card`) jest spakowana **wewnątrz** integracji i
rejestruje się automatycznie przy starcie - jedno repo, bez osobnego pluginu HACS, bez
ręcznego dodawania zasobu (resource) Lovelace.

## Instalacja (ręczna)

1. Skopiuj `custom_components/dynamiczne_info/` do `config/custom_components/` w swoim HA
   (karta Lovelace jedzie razem w środku).
2. Zrestartuj Home Assistant.

## Konfiguracja

Ustawienia -> Urządzenia i usługi -> **Dodaj integrację** -> *dynamiczne.info*:

1. Wybierz swojego **operatora dystrybucji** (pobierany z API).
2. Wybierz **taryfę** oraz czy pobierać **ceny sprzedaży (odkupu)**.

Adres API jest stały (`dynamiczne.info`) - nie ma nic więcej do ustawiania. Możesz
dodać integrację wiele razy, dla kilku kombinacji operator/taryfa.

## Encje

Na każdą skonfigurowaną parę operator/taryfa (urządzenie `dynamiczne.info <OPERATOR> <TARYFA>`):

| Encja | Opis |
|---|---|
| `sensor.*_current_price` | Cena **kupna** brutto bieżącej godziny (PLN/kWh). W atrybutach niesie `now`, tablice godzin `today` / `tomorrow`, `thresholds` oraz `today_summary`. |
| `sensor.*_advice` | Rekomendacja zużycia na bieżącą godzinę - `use` / `neutral` / `limit` (enum). W atrybutach liczniki godzin dnia: `use` / `neutral` / `limit` / `sell`. |
| `sensor.*_next_cheap_hour` | Znacznik czasu najbliższej nadchodzącej godziny `use` (zaczynającej się po teraz) - gotowy wyzwalacz automatyzacji. Atrybuty: `hour`, `buy_gross_pln_per_kwh`. |
| `sensor.*_cheapest_hour_today` | Znacznik czasu najtańszej godziny dziś - do planowania odraczalnych odbiorników. |
| `sensor.*_current_sell_price` | Cena **sprzedaży** brutto bieżącej godziny (tylko gdy tryb sprzedaży włączony). |
| `sensor.*_next_sell_hour` | Znacznik czasu najbliższej nadchodzącej godziny wartej sprzedaży/rozładowania (tylko gdy tryb sprzedaży włączony). |
| `binary_sensor.*_sell_now` | `on`, gdy bieżąca godzina jest warta rozładowania / sprzedaży (tylko gdy tryb sprzedaży włączony). |

## Karta Lovelace

Karta jest rejestrowana przez integrację, więc po instalacji wystarczy dodać ją na
dashboard (bez konfiguracji zasobu):

```yaml
type: custom:dynamiczne-info-card
entity: sensor.dynamiczne_info_energa_g11f_current_price
title: dynamiczne.info - wskazówki na dziś
```

Rysuje 24 godziny pokolorowane wg rekomendacji (używaj / neutralnie / ogranicz), badge
sprzedaży i wyróżnienie bieżącej godziny, plus nagłówek z podsumowaniem: teraz / następna
tania / następna sprzedaż. Czyta atrybuty `today`, `now` i `today_summary` sensora ceny
i podąża za aktywnym motywem Home Assistant (jasny/ciemny).

Jeśli zaraz po instalacji widzisz `Custom element doesn't exist: dynamiczne-info-card`,
zrestartuj Home Assistant, a następnie odśwież frontend (twardy reload, a w razie potrzeby
wyczyść dane strony / Service Worker w przeglądarce lub cache aplikacji mobilnej) -- to
jednorazowy efekt cache PWA, nie błąd integracji.

## Harmonogram odbiorników (EV, bojler, ...)

Poza sensorami informacyjnymi możesz dodać **harmonogramy odbiorników** - sterowalnych
urządzeń (ładowarka EV, bojler, pralka), które mają ruszać w dobrych (tanich) godzinach.
Każdy odbiornik to **podwpis (subentry)** na wpisie taryfy:

Ustawienia -> Urządzenia i usługi -> wpis `dynamiczne.info <OPERATOR> <TARYFA>` ->
**Dodaj odbiornik** -> podaj nazwę i tryb.

Integracja zostaje cienka: nie steruje urządzeniem bezpośrednio, tylko wystawia sygnał
`uruchom teraz` (binary_sensor) oraz `zaplanowany start` (znacznik czasu). Faktycznym
włączeniem urządzenia zajmuje się Twoja automatyzacja (jest gotowy blueprint, niżej).

> Minimalna wersja dla całej integracji, w tym podwpisów (subentries), to
> **Home Assistant 2025.3**.

### Tryby

| Tryb | Co robi | Parametry |
|---|---|---|
| `cheapest_window` (Najtańsze okno) | Wybiera łącznie do N godzin w cyklu do "gotowe do" | `Gotowe do`, `Czas pracy` |
| `fixed` (Sztywny start) | Blok pracy od "start o" (do "stop o", jeśli ustawione - inaczej jedna godzina) | `Start o`, opcjonalnie `Stop o` |
| `price_below` (Poniżej progu ceny) | Każda nadchodząca godzina z ceną kupna `<=` próg | `Próg ceny`, opcjonalnie `Stop` |
| `advice_use` (Godziny zalecane) | Godziny z serwerową rekomendacją `use` | opcjonalnie `Stop` |

Czasy liczone są w lokalnej strefie Home Assistant. `Stop` wcześniejszy niż `Start`
oznacza okno przez północ (np. `22:00 -> 06:00`). Plan na noc zależy od cen jutra
(publikowane wczesnym popołudniem) - wcześniej bywa prowizoryczny.

### Encje odbiornika

W trybach `price_below` i `advice_use` ustawiony `Stop` jest codzienną godziną
graniczną: od tej chwili odbiornik pozostaje wyłączony do północy, również po
odświeżeniu cen lub restarcie. Po północy warunki ceny/rekomendacji znów obowiązują
do kolejnego dziennego limitu. Bez `Stop` te tryby działają przez całą dobę.

Każdy odbiornik to osobne urządzenie. Nazwy encji pochodzą od nazwy odbiornika
(np. `Ładowarka` -> `..._ladowarka_...`):

| Encja | Rola |
|---|---|
| `switch.<odbiornik>_harmonogram` | Włącz/wyłącz harmonogram |
| `select.<odbiornik>_tryb` | Tryb (jeden z czterech powyżej) |
| `time.<odbiornik>_gotowe_do` | Deadline "gotowe do" (tryb okna) |
| `time.<odbiornik>_start_o` | Sztywny start (tryb fixed) |
| `time.<odbiornik>_stop_o` | Koniec bloku `fixed` lub dzienny limit w `price_below` / `advice_use`; nie dotyczy `cheapest_window` |
| `number.<odbiornik>_czas_pracy_godziny` | Ile godzin pracy (tryb okna) |
| `number.<odbiornik>_prog_ceny` | Próg PLN/kWh (tryb progu) |
| `binary_sensor.<odbiornik>_uruchom_teraz` | **Sygnał startu** - tu wpinasz automatyzację |
| `sensor.<odbiornik>_zaplanowany_start` | Najbliższy zaplanowany start. Atrybuty: `selected_hours`, `selected_count`, `total_price`, `avg_price`, `mode`, `enabled` |

### Karta harmonogramu

Tryb `cheapest_window` pamięta rozpoczęte godziny i nie przyznaje nowego budżetu
przy każdym odświeżeniu. Cykl kończy się o `Gotowe do` (bez tej wartości: o północy)
i wtedy zaczyna się kolejny. Przyszłe godziny mogą zmienić się po publikacji cen,
ale już rozpoczęte nadal wliczają się do limitu, również po restarcie lub pauzie.
Zmiana `Czasu pracy` albo `Gotowe do` rozpoczyna nowy cykl; samo wyłączenie/włączenie
harmonogramu go nie resetuje. To budżet godzinowych przedziałów, nie pomiar czasu
faktycznej pracy urządzenia. Godzina rozpoczęta częściowo liczy się jako jeden
przedział; wybierane przedziały muszą kończyć się przed deadline.

```yaml
type: custom:dynamiczne-info-scheduler-card
entity: sensor.ladowarka_zaplanowany_start
```

`entity` to **dowolna encja odbiornika** - karta sama wykryje urządzenie, dociągnie resztę
kontrolek oraz sensor cen rodzica do siatki godzin (zamiast `entity` możesz podać `device`
z ID urządzenia odbiornika). Karta pokazuje siatkę godzin z podświetlonymi wybranymi
godzinami, przełącznik trybu, kontrolki zależne od trybu, włącznik harmonogramu i
podsumowanie planu. Jedzie w tym samym pliku co `dynamiczne-info-card`, więc nie wymaga
dodatkowego zasobu Lovelace.

### Wpięcie urządzenia (blueprint)

Sygnał `uruchom teraz` wepnij w urządzenie - najprościej gotowym blueprintem
`blueprints/automation/dynamiczne_info/run_load.yaml` (wskazujesz sensor `uruchom teraz`
oraz akcje startu i stopu). Albo ręcznie:

```yaml
automation:
  - alias: Ładowarka wg planu dynamiczne.info
    trigger:
      - platform: state
        entity_id: binary_sensor.ladowarka_uruchom_teraz
        to: "on"
    action:
      - action: switch.turn_on
        target: { entity_id: switch.wallbox }
  - alias: Ładowarka stop wg planu dynamiczne.info
    trigger:
      - platform: state
        entity_id: binary_sensor.ladowarka_uruchom_teraz
        to: "off"
    action:
      - action: switch.turn_off
        target: { entity_id: switch.wallbox }
```

## Przykłady automatyzacji

Włącz gniazdko w tanich godzinach:

```yaml
automation:
  - alias: Bojler gdy prąd tani
    trigger:
      - platform: state
        entity_id: sensor.dynamiczne_info_energa_g11f_advice
        to: "use"
    action:
      - action: switch.turn_on
        target: { entity_id: switch.boiler }
```

Rozładuj / sprzedaj z magazynu, gdy odkup się opłaca:

```yaml
automation:
  - alias: Rozładowanie magazynu gdy sprzedaż się opłaca
    trigger:
      - platform: state
        entity_id: binary_sensor.dynamiczne_info_energa_g11f_sell_now
        to: "on"
    action:
      - action: select.select_option
        target: { entity_id: select.battery_mode }
        data: { option: "Export" }
```

Domknij okno - wyłącz bojler, gdy godzina przestaje być tania:

```yaml
automation:
  - alias: Bojler wyłącz gdy prąd przestaje być tani
    trigger:
      - platform: state
        entity_id: sensor.dynamiczne_info_energa_g11f_advice
        from: "use"
    action:
      - action: switch.turn_off
        target: { entity_id: switch.boiler }
```

I zakończ sprzedaż, gdy odkup przestaje się opłacać:

```yaml
automation:
  - alias: Magazyn wróć do trybu auto gdy sprzedaż przestaje się opłacać
    trigger:
      - platform: state
        entity_id: binary_sensor.dynamiczne_info_energa_g11f_sell_now
        to: "off"
    action:
      - action: select.select_option
        target: { entity_id: select.battery_mode }
        data: { option: "Auto" }
```

## Migracja z Pstryk Fixing

Do wersji `0.2.x` integracja nazywała się **Pstryk Fixing** i była w repozytorium
`cierzniak/ha-pstryk-fixing`. Od `0.3.0` nazywa się **dynamiczne.info** i ma nową
domenę `dynamiczne_info`. Dla Home Assistant to **inna integracja**, więc nie
zaktualizuje się sama: trzeba ją dodać od nowa i poprawić odwołania w automatyzacjach
oraz na dashboardach.

1. **Zanotuj konfigurację**: operator, taryfa, tryb sprzedaży oraz ustawienia każdego
   odbiornika (nazwa, tryb, czas pracy, "gotowe do", limit ceny, ...).
2. **Usuń stare wpisy**: Ustawienia -> Urządzenia i usługi -> *Pstryk Fixing* -> usuń
   każdy wpis.
3. **Usuń starą integrację z HACS**: HACS -> *Pstryk Fixing* -> ⋮ -> **Usuń**, a potem
   w **Własnych repozytoriach** usuń `https://github.com/cierzniak/ha-pstryk-fixing`.
   Zrestartuj Home Assistant.
4. **Zainstaluj dynamiczne.info** wg [Instalacji](#instalacja-hacs--katalog-społeczności),
   zrestartuj, dodaj integrację i odtwórz odbiorniki z punktu 1.
5. **Popraw odwołania** w automatyzacjach, skryptach, szablonach i na dashboardach:

| Było (Pstryk Fixing) | Jest (dynamiczne.info) |
|---|---|
| `sensor.pstryk_<operator>_<taryfa>_*` | `sensor.dynamiczne_info_<operator>_<taryfa>_*` |
| `binary_sensor.pstryk_<operator>_<taryfa>_sell_now` | `binary_sensor.dynamiczne_info_<operator>_<taryfa>_sell_now` |
| `type: custom:pstryk-fixing-card` | `type: custom:dynamiczne-info-card` |
| `type: custom:pstryk-fixing-scheduler-card` | `type: custom:dynamiczne-info-scheduler-card` |
| `integration_entities('pstryk_fixing')` | `integration_entities('dynamiczne_info')` |
| blueprint `pstryk_fixing/run_load.yaml` | blueprint `dynamiczne_info/run_load.yaml` |

Encje odbiorników biorą ID z nazwy odbiornika, więc jeśli usuniesz stare wpisy (punkt 2)
przed dodaniem nowych i nadasz odbiornikom te same nazwy, ich ID się nie zmienią.
Zaimportowany wcześniej blueprint działa dalej (wskazuje tylko encję `uruchom teraz`),
wystarczy w automatyzacji wskazać nową encję.

Jeśli po migracji dashboard pokazuje `Custom element doesn't exist`, sprawdź `type:` karty
(tabela wyżej), a potem odśwież frontend jak w sekcji [Karta Lovelace](#karta-lovelace).

## Jak to się składa w całość

To cykl 2 wsparcia dynamiczne.info dla Home Assistant. Cykl 1 (backend) liczy
rekomendację per godzina po stronie serwera i wystawia ją przez `/api/v1/outlook`;
to repo jest cienkim konsumentem. Progi klasyfikacji stroi się centralnie w panelu
admina dynamiczne.info, więc każdy konsument (web + HA) trzyma się tych samych wartości.

## Licencja

MIT - zobacz [LICENSE](LICENSE).
