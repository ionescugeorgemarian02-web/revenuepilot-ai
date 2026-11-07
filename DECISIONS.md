# Jurnal append-only de decizii

Adaugă decizii noi; nu șterge intrări anterioare.

## D00-1 — Crearea remote
Autor: Codex. GraphQL și REST au refuzat crearea repo-ului (HTTP 403); proprietarul a creat repository-ul privat. S-a verificat separat dreptul de push. Probe istorice: `docs/step-00-initial-blocker.md`.

## D00-2 — Proveniența surselor
Autor: Codex. Se păstrează PDF-urile originale, extragerile integrale și SHA-256; nu se copiază cod din alt proiect.

## D00-3 — README inițial
Autor: Codex la cererea utilizatorului. Commitul README inițial a fost păstrat în istorie și pagina completată prin PR.

## D01-1 — Un singur index
Autor: Codex; model selectat declarat de utilizator: GPT-6 Luna / Low. `PROGRESS.md` este punctul unic de intrare și status. `SESSION_LOG.md` și `DECISIONS.md` păstrează istoria append-only. Aceasta reduce riscul ca mai multe copii ale statusului să se contrazică.

## D01-2 — Identitate model
Autor: Codex; utilizatorul a confirmat Luna / Low. Se înregistrează selecția raportată de utilizator; dacă modelul runtime nu este verificabil, se spune explicit. Nu se inventează versiune sau efort.

## D01-3 — Usage
Autor: Codex la instrucțiunea utilizatorului. Usage-ul nu se urmărește și nu se deduce. Handoff-ul se actualizează la finalul sesiunii, fără prag procentual.

## D03-1 — Executarea lui 03 cu dependența 02 deschisă
Autor: Claude, la cererea explicită a utilizatorului, care credea 02 închis. Auditul nu modifică și nu închide 02; rezultatul este IMPLEMENTED, nu DONE. Motiv: auditul este documentare read-only, iar blocajul 02 nu depinde de el; marcarea DONE ar fi ocolit regula „nu sări peste dependențe”.

## D03-2 — Cauza blocajului 02 și lipsa deciziei agentului
Autor: Claude. GET protecție și GET rulesets returnează mesaj de plan GitHub (Pro sau repo public). Corectează interpretarea „doar permisiuni”. Alegerea între control procedural (A), plan plătit (B) și repo public (C) este a proprietarului; agentul nu schimbă vizibilitatea sau planul. Opțiunile sunt în `AUDIT_PASUL_03.md` §2.

## D03-3 — Versiuni fixate la PASUL 08
Autor: Claude. Mediile Codex și Claude diferă (Python 3.12 vs 3.13, Node 24 vs 22, git/gh diferite) și pachetele noi nu pot fi instalate în mediul Claude. PASUL 08 trebuie să fixeze versiuni și lockfile și să nu depindă de instalări posibile doar într-un singur motor.

## D03-4 — Proprietarul alege opțiunea C (repository public)
Autor: Claude; decizia aparține proprietarului (mesaj din sesiune, 2026-11-07). Efect: protecția `main`, rulesets și runnerele Actions standard devin disponibile doar după ce repository-ul este public. Starea verificată la momentul deciziei: `private=true`, protecția și rulesets returnează HTTP 403 (plan). Agentul NU a schimbat vizibilitatea: acțiunea este greu reversibilă (conținutul poate fi indexat/copiat) și se face manual de proprietar. Înainte de publicare: conținutul repo-ului este doar documentație (planul V3, jurnale); nu conține secrete sau date personale verificate în această sesiune, dar proprietarul confirmă că acceptă expunerea strategiei și a planului. Din acel moment, orice commit nou este public: nu se adaugă secrete, date de clienți sau strategie comercială sensibilă.


## D04-1 — 2026-11-07 — propunere Codex, REVIEW_PENDING
Cererea explicită pentru PASUL 04 permite redactarea arhitecturii cu 03 neînchis; nu schimbă statusurile 02/03 și nu elimină review-ul cross-family H. Bază: 7f692ba (Claude). Se propune monolit modular cu separare logică control/execuție și worker ulterior pe dovezi (ADR-04-1), DB relațională țintă și outbox/idempotency/reconciliere (ADR-04-2), memorie per tenant și calibrare evaluată (ADR-04-3). Alternativele, costurile necunoscute și migrarea sunt în docs/architecture/README.md. Alegerea stackului rămâne la 08, niciun serviciu activat. Verdictul final este rezervat review-ului real și închiderii dependențelor.


## D02-1 — Închiderea pașilor 02 și 03
Autor: Claude, după verificare din API (2026-11-07): `required_approving_review_count=1`, `enforce_admins=true`, `allow_force_pushes=false`, `allow_deletions=false`; repo `public`. Limite: nu s-a testat un push direct respins (proxy-ul sesiunii nu permite scrieri pe main); protecția este dovedită din configurație, nu din încercare. Ruleset-ul `main` rămâne disabled. Review independent: necerut. Opțiunea A/B/C → C aplicată.


## D04-2 — Remediere după review Claude (2026-11-07)
Autor: Codex. Acceptate R04-1..4: deletion ledger recuperabil independent de snapshot, retenție suficientă și fail closed la restore; ADR-04-4 pentru resurse finite și oprire persistentă; adapters limitați la ports/domain; corectarea stării curente. Topologia pe un singur host este țintă condiționată de resurse gratuite/autorizate, nu dovadă de hosting existent. Variantele plătite rămân supuse autorizării costurilor. Detalii și limite în docs/architecture/remediation-r04.md. Re-review Claude necesar înainte de acceptare; R04-5 informativ rămâne cerință pentru 08.


## D05-1 — CI minimal fără host (2026-11-07)
Autor: Codex. PASUL 04 DONE pe branch, după re-review Claude. Alegere: workflow GitHub Actions read-only pentru integritatea surselor și contractul arhitectural, plus verificare de linkuri și whitespace; niciun provider, pachet nou sau secret. Alternativele de build/test runtime nu sunt executabile înaintea scheletului din 08. Până la job real, starea 05 rămâne TESTING, nu DONE. Costul efectiv Actions se verifică din cont; repo public nu este garanție de quota nelimitată.
