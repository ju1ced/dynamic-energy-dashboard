# Scenario A Shadow Billing 2025-06 to 2026-05

Ticket: P2-002  
Status: `VERIFIED OFFLINE BACKTEST`  
Uitgevoerd: 2026-09-30

## Scope

Scenario A past de formule van Dynamische Burgerstroom versie
`ECOPOWER_DBS_2026-08-01` retrospectief toe op exact dezelfde historische
Fluvius-afname en -injectie als de gevalideerde Groene
Burgerstroom-factuurperiode. Er is geen energie verschoven en er is geen
Home Assistant-, SMA-, batterij-, Smappee-, laadpaal- of contractinstelling
gewijzigd.

Dit is een contractbacktest, geen reconstructie van een werkelijk beschikbaar
historisch dynamisch contract. De tariefversie geldt vanaf 1 augustus 2026 en
wordt hier bewust als vaste scenario-aanname gebruikt over het eerdere
factuurjaar.

## Datadekking

- lokaal venster: 2025-06-01 00:00 tot 2026-06-01 00:00 Europe/Brussels;
- exact UTC-venster: 2025-05-31T22:00:00Z tot 2026-05-31T22:00:00Z;
- energie-intervallen: 35.040 kwartieren;
- prijsintervallen: 35.040 kwartieren;
- ontbrekende prijzen: 0;
- geschatte Fluvius-intervallen: 99;
- afname: 9.161,589 kWh;
- injectie: 1.160,728 kWh.

De eerdere ENTSO-E-reeks met UTC-middernacht als jaargrens is vóór deze
berekening gecorrigeerd. Energie en prijzen hebben nu exact hetzelfde lokale
factuurvenster; er worden geen acht kwartieren aan de randen verwisseld.

## Leverancierscomponenten exclusief btw

| Component | Historische baseline | Dynamisch Scenario A |
|---|---:|---:|
| Afname-energie | € 1.192,08 | € 880,56 |
| GSC | € 100,78 | € 100,78 |
| WKK | € 35,91 | € 35,91 |
| Abonnement | € 0,00 | € 60,00 |
| Injectiewaarde | € 23,21 credit | € 2,68 credit |
| Netto leverancierscomponent | € 1.305,56 | € 1.074,57 |
| Verschil |  | € -230,99 |

De gewogen dynamische afname-energieprijs is `€0,096114/kWh` exclusief btw.
De gewogen injectievergoeding is slechts `€0,002312/kWh`: 582,356 kWh werd
geïnjecteerd in kwartieren waarin de dynamische injectieformule negatief was.

## Volledige factuurtegenberekening

Netkosten, capaciteitstarief, databeheer, energiebijdrage, accijns en
Energiefonds zijn ongewijzigd overgenomen uit de gereconcilieerde factuur. Alleen
de contractafhankelijke leverancierscomponenten zijn vervangen.

| Totaal | Historische factuur | Scenario A | Verschil |
|---|---:|---:|---:|
| Exclusief btw | € 2.690,39 | € 2.459,40 | € -230,99 |
| Btw | € 162,82 | € 147,72 | € -15,10 |
| Inclusief btw | € 2.853,21 | € 2.607,12 | € -246,09 |

Een negatief verschil betekent dat Scenario A in deze retrospectieve backtest
goedkoper is. Dit resultaat is nog geen contractadvies: een tweede prijsjaar,
actuele contractvoorwaarden, maandelijkse afrekening, gedragseffecten en
operationele randvoorwaarden moeten nog in de gevoeligheidsanalyse worden
meegenomen.

## Maandverschil leverancierscomponent exclusief btw

| Maand | Dynamisch minus historisch |
|---|---:|
| 2025-06 | € +2,40 |
| 2025-07 | € -3,99 |
| 2025-08 | € -6,46 |
| 2025-09 | € -16,00 |
| 2025-10 | € -39,88 |
| 2025-11 | € -38,69 |
| 2025-12 | € -56,55 |
| 2026-01 | € -42,19 |
| 2026-02 | € -35,12 |
| 2026-03 | € -18,05 |
| 2026-04 | € +13,76 |
| 2026-05 | € +9,77 |

De wintermaanden leveren in deze dataset het grootste voordeel op. Juni 2025,
april 2026 en mei 2026 zijn duurder onder het dynamische scenario, vooral door
de lagere of negatieve waarde van PV-injectie.

## Datakwaliteit en gevoeligheid

De 99 geschatte Fluvius-kwartieren blijven in het resultaat opgenomen en zijn
afzonderlijk gemarkeerd. Hun bijdrage aan het verschil is slechts `€+0,20`
exclusief btw; zij bepalen de hoofdconclusie niet. Ontbrekende prijsdata zou de
engine laten falen in plaats van een waarde te forward-fillen.

De engine bewaart per kwartier en per dag de baseline, dynamische
leverancierskost, het verschil en het cumulatieve verschil. De volledige reeks
staat in Git-ignored `data/raw/`; de privacy-safe samenvatting staat in
`docs/evidence/shadow-bill-scenario-a-2025-06-01_2026-06-01.json`.

## Reproduceerbaarheid

Script: `scripts/shadow_bill_scenario_a.py`  
Tariefconfiguratie: `config/tariffs/ecopower-dbs-2026-08-01.json`

De invoer bestaat uit de owner-provided Git-ignored Fluvius-CSV, de gevalideerde
ENTSO-E-kwartierprijzen en de gemaskeerde factuurbaseline. De implementatie test
expliciet negatieve prijzen, ontbrekende marktdata, geschatte intervallen,
herhaalde wintertijd en vervanging van uitsluitend contractafhankelijke
factuurcomponenten.
