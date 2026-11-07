# PASUL 14 — bugete, cote și gardă înainte de orice efect extern

Autor: Claude Sonnet 5.5 (clasă M; Codex neutilizat, D11-2). Data: 2026-11-07. Bază: `ea45a5f` (`main`, 13 DONE). Branch `step-14/budgets`.

## Ce este implementat (`src/revenuepilot/guardrails.py`)
Referință în memorie; persistența, outbox-ul și workerul vin la pasul 18. **Nu există niciun furnizor real**: orice furnizor este `DISABLED` până la configurare explicită și un furnizor dezactivat nu poate fi apelat. Abonamentele (Codex, Claude, ChatGPT) nu sunt modelate ca API.

- **Bani** ca unități minore întregi + monedă. Cost necunoscut, zero, negativ, boolean, float, text sau listă → DENY. Plafon nedefinit la orice nivel → DENY (niciodată „nelimitat”). Monedă diferită → DENY.
- **Rezervare atomică** sub lock, verificată pe patru niveluri: global, tenant, furnizor (per tenant) și task; `rezervat + consumat + estimare ≤ plafon` la fiecare. O cerere peste buget este blocată determinist, exact la limită trece, cu 1 peste e respinsă.
- **Aprobare explicită de cheltuială**: pragul automat implicit este 0, deci orice cheltuială cere o aprobare de la un `approver` al aceluiași tenant, nu expirată, cu maxim ≥ estimare, în aceeași monedă, **de unică folosință**. Aprobarea unui alt tenant, prea mică, expirată sau refolosită → DENY. Bugetul se aplică și cu aprobare.
- **Kill switch** global / tenant / integrare; cel mai restrictiv câștigă; STOP crește un epoch, deci permisele emise înainte nu mai funcționează nici după un START; **agentul poate cere STOP, niciodată START**; starea de STOP necitibilă (excepție la citire) înseamnă STOP.
- **Poarta unică `Dispatcher.run`**: re-validează totul (permis, epoch, rezervare, STOP, starea furnizorului, limita de reîncercări), consumă permisul (**unică folosință**) și abia apoi apelează adaptorul. Dacă orice verificare cade, adaptorul nu este apelat.
- **Rezultat necunoscut** (`TimeoutAfterSend`): banii rămân rezervați, reîncercarea automată este blocată până la reconciliere; eliberarea fără confirmare e refuzată după un dispatch.
- **Reîncercări limitate** (1 inițială + `max_retries`, implicit 2), fiecare cu permis nou și verificare STOP; **circuit breaker** per (tenant, furnizor): se deschide după 3 eșecuri, jumătate-deschis cu o singură sondă, se închide la succes.
- **Depășire**: dacă suma reală > estimare, se înregistrează și integrarea este pusă pe STOP până la revizuire umană.
- **Stări pentru lipsa API/cotă**: `DISABLED` (implicit), `QUOTA_EXHAUSTED`, `ENABLED`; răspuns `provider_disabled` / `provider_quota_exhausted`.
- **Audit**: fiecare decizie → eveniment `budget.decision` (cod de motiv, sumă, monedă; fără permis sau secret), cu trace ID.

## Dovezi rulate efectiv
- **90 teste PASS** pe Python 3.12 și 3.13 (20 noi în `tests/test_guardrails.py`): plafoane pe fiecare nivel, exact la limită, cost/monedă/plafon invalide, 20 de fire concurente pe ultimul sold (exact 6 reușite, restul respinse, suma ≤ plafon), idempotență, izolare între tenanți, aprobări (rol, tenant, valoare, expirare, folosire unică), STOP pe cele trei niveluri, agent vs om, epoch, store necitibil, furnizor lipsă/dezactivat/cotă, un apel exact o dată, permis unic, permisuri falsificate/străine, depășire, rezultat necunoscut, reîncercări limitate, circuit breaker (închis → deschis → sondă → închis), audit.
- **Zero apeluri externe neautorizate:** adaptorul este un fals care numără apelurile; în fiecare caz refuzat contorul rămâne 0, iar la un apel autorizat este exact 1.
- **16 mutații** (cod stricat intenționat, apoi restaurat): 15 detectate. Una nu are efect observabil (apel de dispatch pe o rezervare „necunoscută”: permisul este deja consumat, deci calea este neatinsă; mutant echivalent).
- Defect găsit în testele pasului 13: un eșec intermitent (≈1 din 10 rulări) — `request.completed` se emite după scrierea răspunsului, deci clientul poate vedea răspunsul înaintea evenimentului. Testul a fost corectat cu o așteptare mărginită; comportamentul serverului este documentat aici, nu ascuns.
- Build, hash-uri canonice, linkuri, contract arhitectură: PASS.

## Limite (NU sunt implementate sau dovedite)
- **În memorie**: la repornire dispar rezervările, aprobările și STOP-urile; STOP implicit după restore, ledger și outbox (A15, R04-1) sunt cerințe ale pașilor 18/45/77, nu sunt acoperite aici. Fără tranzacție comună cu DB (pasul 12) și fără lease/fencing între procese.
- Nu există coadă finită, backpressure sau limită de concurență (A16): pasul 18. Nu există conectare la `TenancyService`: rolul de `approver` este primit ca parametru, deci apelantul trebuie să îl verifice prin pasul 11.
- Nu există ceas monoton pentru expirări (se folosește ceasul injectat); sumele nu au perioade calendaristice (plafonul este per instanță).
- Niciun furnizor real, niciun cost real. CI remote NOT_RUN. Review independent necerut pentru clasa M.

## Note pentru reviewer
Atacă: `_authorize` (ordinea verificărilor și consumul permisului), `_used` (contabilitatea pentru UNKNOWN_OUTCOME/SETTLED), `reconcile` → `settle` sub același lock, `release(confirmed_no_effect=True)` ca vector de abuz, `stop` apelabil de oricine.
