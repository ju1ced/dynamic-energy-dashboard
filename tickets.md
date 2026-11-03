# Backlog en ticketregister

De tickets staan sinds 3 november 2026 in [GitHub Issues](https://github.com/ju1ced/dynamic-energy-dashboard/issues); dit bestand is alleen nog een index van ticketnummer naar issue. De volledige ticketinhoud (doel, afhankelijkheden, acceptance criteria, resultaat en implementatiestatus) staat in de issuebeschrijving, samen met de kanbaninformatie van vóór de migratie (kolom, volgorde, samenvatting). Het bord staat in [KANBAN.md](KANBAN.md).

## Conventies

- **Titel:** `Px-xxx — <titel>`; nieuwe tickets nemen het volgende vrije nummer binnen hun fase.
- **Milestone:** de epic (`E01` t/m `E07`), zie [milestones](https://github.com/ju1ced/dynamic-energy-dashboard/milestones).
- **Labels:** prioriteit `P0`/`P1`/`P2` en, zolang het issue open is, precies één status: `status:backlog`, `status:in-progress`, `status:review` of `status:blocked`. Een voorwaardelijke prioriteit (bijvoorbeeld "P0 voor activatie") staat voluit in de issuebeschrijving.
- **Klaar:** issue gesloten als *completed*.
- **Afhankelijkheden:** in de issuebeschrijving, met `#nummer`-verwijzingen.

## Index

De status hieronder is een momentopname bij de migratie; het issue is leidend.

| Ticket | Issue | Titel | Milestone | Status bij migratie |
|---|---|---|---|---|
| P1-001 | [#16](https://github.com/ju1ced/dynamic-energy-dashboard/issues/16) | Projectfundament en traceerbaarheid | E01 Discovery & Evidence | Klaar |
| P1-002 | [#17](https://github.com/ju1ced/dynamic-energy-dashboard/issues/17) | Beschikbare eigenaarinformatie en bewijsmateriaal inventariseren | E01 Discovery & Evidence | Klaar |
| P1-003 | [#18](https://github.com/ju1ced/dynamic-energy-dashboard/issues/18) | PV-installatie onderzoeken | E01 Discovery & Evidence | Klaar |
| P1-004 | [#19](https://github.com/ju1ced/dynamic-energy-dashboard/issues/19) | SMA-batterijsysteem en arbitragemogelijkheden onderzoeken | E01 Discovery & Evidence | Klaar |
| P1-005 | [#20](https://github.com/ju1ced/dynamic-energy-dashboard/issues/20) | SMA Home Manager 2.0 rol en controllergrenzen onderzoeken | E01 Discovery & Evidence | Klaar |
| P1-006 | [#21](https://github.com/ju1ced/dynamic-energy-dashboard/issues/21) | EV en laadpaal onderzoeken | E01 Discovery & Evidence | Klaar |
| P1-007 | [#22](https://github.com/ju1ced/dynamic-energy-dashboard/issues/22) | Home Assistant entity- en datakwaliteitsinventaris | E03 Energy Data Foundation | Klaar |
| P1-008 | [#23](https://github.com/ju1ced/dynamic-energy-dashboard/issues/23) | Ecopower huidig en dynamisch tarief onderzoeken | E02 Dynamic Readiness | Klaar |
| P1-009 | [#24](https://github.com/ju1ced/dynamic-energy-dashboard/issues/24) | Dynamic Tariff Readiness Matrix en gaps opstellen | E02 Dynamic Readiness | Klaar |
| P1-010 | [#25](https://github.com/ju1ced/dynamic-energy-dashboard/issues/25) | Voorlopige architectuur en control ownership | E06 Optimization & Control | Klaar |
| P1-011 | [#26](https://github.com/ju1ced/dynamic-energy-dashboard/issues/26) | Shadow-billing- en scenarioplan | E04 Shadow Billing | Klaar |
| P1-012 | [#27](https://github.com/ju1ced/dynamic-energy-dashboard/issues/27) | Dashboardvereisten en wireframeplan | E05 Dashboard Experience | Klaar |
| P1-013 | [#28](https://github.com/ju1ced/dynamic-energy-dashboard/issues/28) | Fase-1 documentatie valideren | E07 Safety & Operations | Klaar |
| P1-014 | [#29](https://github.com/ju1ced/dynamic-energy-dashboard/issues/29) | Eigenaarvalidatie en fase-2-go/no-go | E07 Safety & Operations | Klaar |
| P2-001 | [#30](https://github.com/ju1ced/dynamic-energy-dashboard/issues/30) | Veilige Home Assistant data-export verzamelen | E03 Energy Data Foundation | Klaar |
| P2-002 | [#31](https://github.com/ju1ced/dynamic-energy-dashboard/issues/31) | Shadow-billing minimum viable monitor bouwen | E04 Shadow Billing | Klaar |
| P2-003 | [#32](https://github.com/ju1ced/dynamic-energy-dashboard/issues/32) | Dashboardwireframes ontwerpen | E05 Dashboard Experience | Klaar |
| P2-004 | [#33](https://github.com/ju1ced/dynamic-energy-dashboard/issues/33) | Contractpassende EPEX Day-Ahead-kwartierfeed | E03 Energy Data Foundation | Klaar |
| P2-005 | [#34](https://github.com/ju1ced/dynamic-energy-dashboard/issues/34) | Forecastkwaliteit en issue-time-opslag | E03 Energy Data Foundation | Klaar |
| P2-006 | [#35](https://github.com/ju1ced/dynamic-energy-dashboard/issues/35) | Energy Decision Log-datamodel | E05 Dashboard Experience | Klaar |
| P2-007 | [#36](https://github.com/ju1ced/dynamic-energy-dashboard/issues/36) | Meerjarige financiële en batterijgevoeligheidsanalyse | E04 Shadow Billing | Klaar |
| P2-008 | [#37](https://github.com/ju1ced/dynamic-energy-dashboard/issues/37) | Read-only shadow-controller voor dynamische sturing | E06 Optimization & Control | In uitvoering |
| P2-009 | [#38](https://github.com/ju1ced/dynamic-energy-dashboard/issues/38) | HACS-installable live Lovelace shadow dashboard | E05 Dashboard Experience | In uitvoering |
| P3-001 | [#39](https://github.com/ju1ced/dynamic-energy-dashboard/issues/39) | EV-laadoptimalisatie in simulatie | E06 Optimization & Control | In uitvoering |
| P3-002 | [#40](https://github.com/ju1ced/dynamic-energy-dashboard/issues/40) | Batterijarbitrage in simulatie | E06 Optimization & Control | In uitvoering |
| P3-003 | [#41](https://github.com/ju1ced/dynamic-energy-dashboard/issues/41) | Control authority en failure modes valideren | E07 Safety & Operations | Geblokkeerd |
| P3-004 | [#42](https://github.com/ju1ced/dynamic-energy-dashboard/issues/42) | Gezamenlijke batterij- en EV-sturingslogica in dry-run | E06 Optimization & Control | In uitvoering |
