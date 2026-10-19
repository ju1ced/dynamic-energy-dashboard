# Dashboard Requirements

Status: standalone MVP en HACS-ready read-only Lovelace-kaart lokaal gevalideerd  
Gerelateerde tickets: P1-012, P2-003, P2-008 en P2-009  
Laatst bijgewerkt: 2026-10-02

## Doel

Het dashboard moet energiegedrag begrijpen, simuleren en opvolgen. Het is geen controlpaneel totdat iedere control afzonderlijk technisch en veilig is goedgekeurd.

## Algemene UX-eisen

- De visuele stijl is gebaseerd op de door de eigenaar aangeleverde AIHub-
  screenshot: compacte linker navigatie, gedempte groene applicatiebalk,
  vlakke lichtgrijze werkvlakken, monospaced datadetails en hoge informatiedichtheid.
- Desktop en mobiel worden afzonderlijk gevalideerd.
- De gebruiker kan de interface lokaal schalen naar 100%, 112% of 125%; de
  keuze blijft uitsluitend in browseropslag bewaard.
- Werkelijke data, forecast, simulatie en geplande actie hebben verschillende visuele semantiek.
- Stale, ontbrekende of geschatte data is direct herkenbaar.
- Elke automatische beslissing toont reden, inputs, constraints en geldigheidsduur.
- Controls die niet bewezen veilig zijn, worden niet als werkende UI getoond.

## View 1 - Overview

Realtime flow: PV → House ↔ Battery ↔ Grid en House/Grid → EV.

Minimaal:

- huisverbruik;
- PV-productie;
- batterijvermogen en SOC;
- import/export;
- EV-laadvermogen;
- huidige afname- en injectieprijs;
- volgende prijswijziging;
- datakwaliteit en laatst bijgewerkt;
- actieve Energy Strategy.

## View 2 - Price timeline

Per 15 minuten of uur, volgens contract en beschikbare bron:

- markt- en contractprijs;
- negatieve, goedkope en dure intervallen;
- PV-forecast met onzekerheid;
- gepland EV-laden;
- geplande batterijlading/-ontlading;
- huidige tijd en volgende publicatie van prijzen.

De classificatie goedkoop/duur gebruikt configureerbare of statistische drempels en mag geen verborgen hardcoded oordeel zijn.

## View 3 - Financial

- kost vandaag en deze maand;
- injectieopbrengst;
- netto energiekost;
- gewogen gemiddelde aankoop- en verkoopprijs;
- huidig contract versus dynamische shadow bill;
- dagelijkse, maandelijkse en cumulatieve delta;
- opsplitsing energie, net, heffingen/belastingen, vaste kosten en injectie;
- datadekking en aantal onvolledige intervallen.

## View 4 - Battery

- SOC en beschikbaar geschatte energie;
- charge/discharge power;
- cumulatieve energie en efficiëntie-indicator;
- huidige lokale modus;
- voorspelde SOC-band;
- voorgestelde laad-/ontlaadvensters;
- limieten en reserve-SOC;
- redenen waarom een actie wel of niet is toegestaan.

Conceptuele toekomstige modi: AUTO, SELF CONSUMPTION, DYNAMIC, CHARGE NOW, HOLD en BACKUP. Geen control vóór officiële validatie.

## View 5 - EV

- voertuig-SOC indien betrouwbaar beschikbaar;
- plug- en chargerstatus;
- laadvermogen, sessie-energie en kosten;
- geplande laadintervallen;
- benodigde energie tegen vertrektijd;
- actuele beperking of reden voor uitstel.

Conceptuele toekomstige inputs: target-SOC, departure time, minimum-SOC, maximum price, solar only, cheapest hours en charge now.

## View 6 - Energy Decision Log

Per beslissing:

- timestamp en strategie;
- observatie en gebruikte data;
- reden in mensentaal;
- overwogen actie;
- blokkerende constraints;
- geldigheidsduur;
- voorspeld kost-/energie-effect;
- werkelijk resultaat indien beschikbaar;
- model-/regelversie.

Voorbeeldweergave: `EV charging delayed: cheaper validated window starts at 02:00; departure constraint remains satisfied.`

## Wireframegate

Voor implementatie moeten wireframes:

1. alle views en navigatie tonen;
2. mobiele en desktopstates omvatten;
3. loading, stale, unavailable, negative-price en fault states bevatten;
4. werkelijke versus gesimuleerde waarden zichtbaar scheiden;
5. door de eigenaar worden goedgekeurd.

De eigenaar koos op 2026-09-30 voor een apart, volledig read-only
webdashboard en leverde de AIHub-screenshot als stijlreferentie. De eerste
werkende MVP geldt als interactief wireframe; Cloudflare-publicatie en live
Home Assistant-writes maken geen deel uit van deze goedkeuring.

## MVP-architectuur

- Primair oppervlak: monitor, niet controlpaneel.
- Frontend: statische HTML, CSS en JavaScript zonder externe runtime-
  afhankelijkheden.
- Datalaag: gegenereerde privacy-safe JSON uit gevalideerde evidence.
- Netwerk: lokale HTTP-server bindt expliciet op `0.0.0.0`; de gebruiker opent
  het dashboard via het LAN-IP en een niet-geprivilegieerde poort.
- Cloudflare: compatibel met een latere tunnel naar de lokale HTTP-origin, maar
  geen tunnel of publieke hostname wordt automatisch aangemaakt.
- Veiligheid: geen muterende API-routes, formulieren of apparaatcontrols.

## Live Home Assistant-oppervlak

De eigenaar autoriseerde op 2026-10-02 een aanvullend read-only Lovelace-
oppervlak. Dit wordt geleverd als HACS-dashboardplugin met een visuele editor.

- De kaart leest live states via het frontend-`hass`-object.
- Verplichte mappings zijn grid, PV, batterijvermogen en batterij-SOC.
- Huis, EV en warmtepomp zijn optioneel. De observerende shadow-feed kan zowel
  een planning als toekomstige ENTSO-E/Ecopower-kwartierprijzen leveren; de
  prijzen blijven zichtbaar wanneer de planning fail-closed `NO_ACTION` is.
- De gedeelde netpiekgrens en sign conventions zijn via de GUI instelbaar.
- Het actuele planinterval wordt op absolute timestamp geselecteerd.
- De kaart toont een horizontaal scrollbare toekomstige prijstijdlijn met
  marktprijs, Ecopower-afnameprijs, indicatieve referentie en geplande actie.
- De kaart toont stale, missing, unavailable en setup-required als expliciete
  statussen.
- De kaart bevat geen acties, servicecalls, setpoints of apparaatcontrols.
- De Python-optimizer blijft buiten Lovelace en blijft de reproduceerbare
  planningsbron.

## Niet-functionele eisen

- Geen dashboardfout mag lokale energiewerking beïnvloeden.
- Rendering moet bruikbaar blijven bij ontbrekende optionele entities.
- Berekeningen horen in een testbare datalaag, niet uitsluitend in kaartconfiguratie.
- Belangrijke financiële waarden tonen broninterval en dekking.
- Historische grafieken respecteren lokale tijd, zomertijd en ontbrekende intervallen.
