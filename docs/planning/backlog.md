# Backlog inițial testabil (pașii 07–15, fundația)

Fiecare element are dependență, acceptanță verificabilă și risc. Nu este o listă de nume de funcții. Surse: plan V3 (identitatea pasului rămâne cea din plan), `docs/architecture/test-plan.md` (A01–A17). Status: toate NOT_STARTED. Modelul din plan este recomandare; selectorul decide.

| Pas | Obiectiv | Depinde de | Acceptanță măsurabilă (dovadă) | Risc | Clasă / model plan |
|---|---|---|---|---|---|
| 07 | Threat model și politici de acces | 04 | Document cu active, limite de încredere, amenințări STRIDE per flux din ADR-04; fiecare amenințare are control sau risc acceptat; review din familia opusă | Mare: decizie de securitate greu reversibilă | H / Astra sau Opus |
| 08 | Alegere stack și schelet minim | 07 | Versiuni și lockfile fixate; un test de „bună ziua” rulat local și în CI; verificare reală a importurilor între straturi (înlocuiește validatorul conceptual, A01); instalare doar fără sudo și fără servicii plătite | Mediu: medii diferite Codex/Claude | M / Sol sau Sonnet |
| 09 | Kit UI mobil minim | 08 | Pagini goale responsive la 360 px; contrast și navigare cu tastatura verificate manual și într-un test automat; fără date reale | Mic | T / Terra |
| 10 | Identitate, sesiuni, autentificare | 08 | Teste: login/logout, expirare sesiune, parolă ne-stocată în clar, rate limit; fără provider extern plătit | Mare: securitate | M+ / Sol High |
| 11 | Multi-tenant, RBAC, izolare | 10 (corectat la pasul 11; versiunea inițială spunea greșit „10, 12”) | A02 trece: tenant A nu atinge resurse B (API, export, căutare, cache); chei compuse; implicit deny; teste pozitive și negative | Mare: scurgere de date | H / Astra sau Opus |
| 12 | Persistență, migrare, date demo | 08 | Migrații reproductibile (expand/backfill/validate); fixtures sintetice pentru 3 organizații din 3 industrii; A03 (refolosire conexiune) | Mare | M / Sol |
| 13 | Evenimente, audit, observație | 11, 12 | Evenimente cu tenant și correlation ID; fără PII în loguri (test); retenție configurată | Mediu | M / Sol |
| 14 | Bugete și guardrails | 11, 13 | A07 (două joburi, un buget), A15 (kill switch global/tenant/integrare), A16 (concurență 1, coadă finită) | Mare: cost necontrolat | M+ / Sol High |
| 15 | Review independent fundație + baseline securitate | 07–14 | Review scris de familia opusă pe SHA examinat; scanare secrete și dependențe în CI; constatările HIGH rezolvate | Mare | H / Astra sau Opus |

## Reguli
- Un element intră în lucru doar când dependențele sunt DONE în `PROGRESS.md`.
- Un test care ar trece cu o implementare falsă (mock pe loc de DB reală) nu este acceptanță pentru 11–12 (Meta §15.3).
- Orice element cu risc „Mare” necesită review independent înainte de DONE.
- Estimările de efort nu sunt incluse: nu există istoric suficient (K03). Se adaugă după 3–5 pași măsurați.
