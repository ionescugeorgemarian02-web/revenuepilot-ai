# PASUL 12 — persistență, migrații și date demo

Autor: Claude Sonnet 5.5 (clasă M; Codex nu a fost folosit, conform D11-2). Data: 2026-11-07. Bază: `09130e7` (`main`, 11 DONE). Branch `step-12/persistence`.

## Ce este implementat (`src/revenuepilot/storage.py`)
- **Motor:** SQLite din biblioteca standard (zero dependențe, zero cost). **Nu este ținta de producție** (ADR-04-2: PostgreSQL). Alegerea este pentru demo/teste locale și pentru a valida forma schemei; migrarea la PostgreSQL cere conversie și teste pe motorul țintă.
- **Schema (migrația 1):** organizații, utilizatori, memberships (`rol` cu CHECK, versiune), contoare de ID per tenant, resurse cu cheie `(tenant_id, id)`, granturi, evenimente de audit. **Chei străine compuse**: părintele unei resurse, proprietarul ei și beneficiarul unui grant trebuie să existe în **același tenant**; o referință între tenanturi este imposibilă în schemă, nu doar filtrată în cod. CHECK-uri pe tip, vizibilitate, lungimi, status și coerența aprobării.
- **Migrația 2:** index suplimentar, strict aditiv (expand).
- **Migrații:** versionate, cu `up` și `down`, checksum, fiecare pas într-o tranzacție (rollback complet la eroare); istoricul alterat, necunoscut (bază mai nouă decât codul) sau cu goluri este refuzat.
- **Store tenant-scoped:** fiecare metodă primește explicit `tenant_id`; update/aprobare cu concurență optimistă (versiune); o editare anulează aprobarea; căutarea escapează wildcard-urile LIKE; un utilizator care nu e membru al tenantului nu vede nimic; export segregat; **retenție** pentru auditul fiecărui tenant (`purge_audit_before`).
- **La reluare** (`open_store`): verifică istoricul, `PRAGMA integrity_check`, `foreign_key_check` și versiunea. WAL și `synchronous=FULL` pentru fișiere.
- **Fixture-uri sintetice** (idempotente): 3 organizații din 3 industrii (marketing, sănătate, alimentație), prefix `[SINTETIC]`, câte 3 membri și 2 resurse; fără date personale reale.

## Dovezi rulate efectiv
- `python3 -B -I -m unittest discover -s tests`: **56 teste PASS** pe Python 3.12 și 3.13 (16 noi în `tests/test_storage.py`): rulare up/down/up, rollback la migrare defectă, istoric alterat, creare/citire/update/scop pe 3 tenanturi cu același `r1`, injecție în ID, referințe între tenanturi respinse de schemă, CHECK-uri, concurență și aprobare, fără stare parțială la eșec, vizibilitate/căutare/export, retenție per tenant, fixture-uri idempotente, **persistență după repornire**, refuzul bazei mai noi sau corupte, detectarea unei încălcări FK la reluare, și o gardă la execuție care urmărește SQL-ul real și cere filtru de tenant.
- **Mutații** (7, cod/schemă stricate intenționat, apoi restaurate): toate detectate (FK părinte fără tenant, citire fără filtru, update fără filtru, checksum neverificat, FK dezactivate, retenție pe toți tenanții, non-membru care vede resurse). Notă: mutația „FK fără tenant” este prinsă de SQLite ca „foreign key mismatch” (13 erori), nu de testul semantic.
- Defect găsit de teste în codul meu: `visible_resources` arăta resursele tenantului oricărui `user_id`, chiar nemembru; corectat (membership cerut în interogare).
- Build, hash-uri canonice, linkuri, contract arhitectură: PASS.

## Limite (NU sunt dovedite sau implementate)
- **`TenancyService` (pasul 11) nu folosește încă acest store**: serviciul rămâne în memorie. Integrarea (și rularea testelor de izolare 11 pe store) este de planificat; nu se pretinde persistență pentru API-ul HTTP.
- SQLite nu validează RLS, pooling sau concurență multi-conexiune (A03, T10 la nivel de stocare): NOT_RUN. Nu există backup/restore testat, ledger de ștergeri (R04-1) sau criptare.
- Nu există migrare de date între motoare. Cost: zero. Hostul și DB-ul de producție rămân neales.
- CI remote NOT_RUN (Actions dezactivat pe cont). Review independent: necerut pentru clasa M, nepretins.

## Note pentru reviewer
Atacă: concurența între două procese pe același fișier (WAL), `_Transaction` (COMMIT după excepție), ordinea contorului față de INSERT, `purge_audit_before` ca vector de pierdere de probe.
