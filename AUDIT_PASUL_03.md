# PASUL 03 — audit preliminar, dependență deschisă

Data 2026-11-07 UTC. Autor: Codex; model runtime/efort nu sunt disponibile verificabil. Bază de lucru: branch-ul PASULUI 02 cu commit `b73fc9b2173a1dc1d76fb46ce6eec87165af5ee2`. Solicitare explicită a utilizatorului de a pregăti PASUL 03. Status: BLOCKED, nu DONE: PASUL 02 nu are încă protecție main verificată și PR-ul său este draft.

| Componentă | Status | Dovadă / limită |
|---|---|---|
| GitHub identity | VERIFIED | `gh auth status` și metadata GitHub confirmă contul ionescugeorgemarian02-web; drepturile repo indică admin/push. |
| Git local | VERIFIED | `git --version`: 2.52.0. |
| GitHub CLI | VERIFIED | `gh --version`: 2.46.0. |
| Python | VERIFIED | `python3 --version`: 3.12.14. |
| Node / npm | VERIFIED | `node --version`: v24.22.1; `npm --version`: 11.9.0. |
| Docker CLI | VERIFIED | `docker --version`: 29.9.2; daemon și containere NOT_RUN. |
| Workspace | VERIFIED / UNKNOWN | `df -h /workspace`: 7.9G total, 7.5G disponibil la măsurare. Persistența între medii nu este garantată; Git remote este sursa durabilă. |
| GitHub Actions | UNKNOWN | endpointul `/actions/permissions` a returnat 403; `/actions/runs` a returnat 0 rulări. Nu dovedește disponibilitatea sau quota. CI efectiv NOT_RUN. |
| Protecție main | UNAVAILABLE pentru această conexiune | Metadata `protected=false`; GET branch protection HTTP 403. Nu dovedește că proprietarul nu are posibilități în UI. |
| Host aplicație | UNKNOWN | Specificația declară hostul nepregătit; nu a fost configurat sau verificat în această sesiune. |
| Chei API runtime comerciale | UNKNOWN | Specificația nu presupune chei. Nu s-au verificat valori de secrete și nu s-a apelat API runtime. Abonamentul interactiv nu este API backend. |
| Costuri / cote GitHub | UNKNOWN | Nu s-a verificat planul comercial, cota CI sau costul efectiv. Niciun serviciu plătit nou activat. |

Comanda `pdftotext --version` a eșuat deoarece versiunea instalată tratează `--version` ca nume de fișier; aceasta nu dovedește că utilitarul lipsește. Documentele au fost anterior extrase prin `pdftotext -layout`, dovadă în PASUL 00. Nu confunda eroarea cu o integrare indisponibilă.

Review independent NOT_RUN; build, CI, API live și deploy NOT_RUN. Nu se raportează auditul ca finalizat până când PASUL 02 este închis, dovezile necesare revizuite și schimbările integrate prin PR. Predare: rezolvă mai întâi PASUL 02 din PR #3; reia acest document, verifică din nou mediul și permisiunile și actualizează starea fără a șterge constatările.
