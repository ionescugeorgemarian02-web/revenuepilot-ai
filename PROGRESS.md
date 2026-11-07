# RevenuePilot AI — index și stare curentă

Punct unic de reluare: această pagină. Sesiunea următoare citește planul canonic și cel mai recent handoff înainte de lucru.

## Proiect și limite

Repository public: https://github.com/ionescugeorgemarian02-web/revenuepilot-ai
Owner `ionescugeorgemarian02-web` (GitHub ID 342118131), repository ID 1449074103. Branch canonic `main`.
Surse canonice nemodificate: [Meta-prompt V3](docs/canonical/RevenuePilot_AI_META_PROMPT_CONSTRUCTIE_V3.pdf), [Plan V3](docs/canonical/RevenuePilot_AI_PLAN_CONSTRUCTIE_GITHUB_V3.pdf). PDF-urile sunt sursa de adevăr; textul extras ajută căutarea. Hashuri în `docs/canonical/SHA256SUMS`.

GitHub păstrează codul și documentația. Hostingul și runtime-ul aplicației, baza de date și cheile API comerciale nu sunt configurate. Nu modifica `fabrica-autonoma`; nu adăuga secrete ori date personale; nu activa cheltuieli fără autorizare. Un pas per sesiune, apoi STOP.

## Pas curent

- PASUL 00: DONE — repository separat și privat, surse canonice importate, push verificat. Merge commit `1e0cf4451aac1f59e88e849f8e997a999fbfcd91`; PR #1.
- PASUL 01: DONE prin PR-ul acestei livrări. A creat indexul, reguli de stare, istoric, decizii, tracker de blocaje/dovezi și handoff.
- PASUL 02: DONE — politica în [GIT_POLICY.md](GIT_POLICY.md). Protecția clasică pe `main` verificată din API (2026-11-07): PR cu 1 aprobare, `enforce_admins=true`, force-push și ștergere interzise. Ruleset-ul `main` rămâne `disabled` (nefolosit). Integrarea în `main` se face prin PR #3 → #4 → #5, doar de proprietar.
- PASUL 03: DONE — audit în [AUDIT_PASUL_03.md](AUDIT_PASUL_03.md) (secțiunile 1–6). Repo public din decizia C (D03-4); runnerele Actions NU au fost re-măsurate.
- PASUL 04: DONE — [arhitectura](docs/architecture/README.md), PR #6. Re-review Claude Opus 5.5 pe `5dc5e27`: R04-1..R04-4 rezolvate, APPROVED ([review](docs/architecture/review-claude.md)). Integrarea în `main` după PR #3 → #4 → #5.
- PASUL 05: DONE pe branch — [verificări fără host](docs/ci/step-05.md), PR #7; pe commitul final `ce52da3c3cfc6c808ce929fee7ff5f03eea913c2`, rulările Actions #42351263418 (push) și #42351267008 (PR) au PASS. PR-urile #3–#7 încă trebuie integrate în ordine în main.
- PASUL 06: READY conform dependenței 05, neînceput; recomandare GPT-6 Luna / Low sau Claude Haiku 5.5 / Low.
- PASUL 07–84: NOT_STARTED.

## Stări și tranziții

Stări: `NOT_STARTED`, `READY`, `CLAIMED`, `IN_PROGRESS`, `IMPLEMENTED`, `TESTING`, `REVIEW_PENDING`, `CHANGES_REQUESTED`, `VERIFIED`, `DONE`, `BLOCKED`, `DEFERRED`, `FAILED`.

1. La start, verifică repository, branch, HEAD, worktree, acest index și ultimul handoff.
2. `NOT_STARTED → READY` numai când dependențele sunt DONE și pasul este autorizat/modelul potrivit.
3. `READY → CLAIMED → IN_PROGRESS → IMPLEMENTED → TESTING`; înregistrează autor, model declarat, SHA de bază și scop.
4. `TESTING → VERIFIED → DONE` doar cu criterii și dovezi reale, commit/push și review real când este cerut. Nu deduce testele din cod sau din plan.
5. Lipsa dependenței/accesului duce la `BLOCKED` ori `DEFERRED`, cu probă și pas de deblocare. Nu sări peste dependențe.
6. Review-ul independent este scris de reviewer, separat de autor. Fără reviewer disponibil, păstrează `REVIEW_PENDING` când planul îl cere.
7. Istoricul este append-only. Corecțiile noi indică intrarea anterioară; fără force-push.

## Registrul execuțiilor

| Pas | Status | Autor / model declarat | Bază → rezultat | Review |
|---|---|---|---|---|
| 00 | DONE | Codex; modelul exact nu a fost verificat atunci | `590e4d1` → `1e0cf44`; surse și progres publicate prin PR #1 | Review independent nepretins |
| 01 | DONE | Codex; utilizatorul a confirmat GPT-6 Luna / Low înainte de execuție | `1e0cf44` → SHA-ul PR-ului curent; jurnal și handoff în PR | Clasa L; review independent necerut/nepretins |
| 02 | DONE | Codex (politică); verificare protecție: Claude Sonnet 5.5 | Bază `df7d134` → branch `docs/step-02-git-policy` (PR #3) | Review independent neefectuat, necerut de plan pentru clasa T |
| 03 | DONE | Claude Sonnet 5.5 (selectat de utilizator); audit preliminar: Codex | `08e715f` → branch `claude/blissful-galileo-9tz9fz` (PR #4, #5) | Clasa M; review independent necerut |
| 04 | DONE | Codex; runtime/efort neverificate | Bază `7f692ba`; branch `step-04/architecture`, remediere `5dc5e27` | Claude Opus 5.5: CHANGES_REQUESTED pe `fd2ebbe`, APPROVED pe `5dc5e27` |

| 05 | DONE | Codex; runtime/efort neverificate | Bază `b9607d23f8d16d52a1e7f8bfd27be377dd530499`; PR #7, Actions #42351263418 și #42351267008 PASS pe HEAD final | Clasa M; review independent necerut/nepretins |

Nu inventa model runtime, versiune, efort sau usage dacă nu sunt verificabile. Instrucțiunea utilizatorului pentru sesiunile curente este să nu se folosească usage; nu îl urmări și nu raporta procente.

## Decizii curente

Jurnalul append-only: [DECISIONS.md](DECISIONS.md). Sesiunile și handoff-urile: [SESSION_LOG.md](SESSION_LOG.md). Șablon: [SESSION_TEMPLATE.md](SESSION_TEMPLATE.md).

- D00-1: permisiunea de creare remote a lipsit inițial; proprietarul a creat repo privat, după care push-ul a fost verificat. Istoric: `docs/step-00-initial-blocker.md`.
- D00-2: PDF-urile originale, textul extras și hashurile rămân împreună; fără import de cod din alte proiecte.
- D01-1: `PROGRESS.md` este singurul index pentru starea curentă; jurnalul de sesiuni și decizii rămân append-only, evitând statusuri concurente.
- D01-2: autorul consemnează modelul selectat de utilizator; modelul intern neverificabil este etichetat ca atare.

## Blocaje, riscuri, limite

- Blocaj istoric al protecției repo privat rezolvat: repository public, protecție clasică main verificată (D02-1). Ruleset-ul separat disabled nu este mecanismul activ.
- Host și chei API comerciale: neconfigurate; nu blochează documentarea.
- Build/test produs, CI, deploy și API live: NOT_RUN; nu există implementare de produs în scope-ul PASULUI 01.

## Dovezi

| ID | Pas | Probă | Rezultat |
|---|---|---|---|
| E00-1 | 00 | Extragere pdftotext 11 + 34 pagini, comparație byte-for-byte și `sha256sum -c` | PASS |
| E00-2 | 00 | GitHub repo metadata, permisiuni admin/push, push și citire fișiere remote | PASS |
| E00-3 | 00 | PR #1, `git fsck --full`; istorice inițiale păstrate | PASS |
| E01-1 | 01 | Planul canonic și registrul reluate; dependența 00 verificată | PASS |
| E01-2 | 01 | Linkuri locale, consistența indexului și diff whitespace | Se consemnează după verificare |
| E01-3 | 01 | Push, PR și HEAD main comparat | Se consemnează după verificare |

## Procedura de reluare și handoff

La început: fetch; confirmă `ionescugeorgemarian02-web/revenuepilot-ai`, branch, HEAD și worktree; citește indexul, pasul din plan și ultima intrare din `SESSION_LOG.md`; selectează primul pas READY cu dependențe închise.

La final: adaugă intrarea sesiunii fără a rescrie trecutul; actualizează statusul și probele; notează defecte/decizii/lecții numai dacă există dovezi; commit/push/PR; raportează PASS/FAIL/NOT_RUN, SHA, blocaje și model recomandat; STOP.

Punct de reluare: PASUL 05 DONE pe branch (PR #7, Actions #42351263418 și #42351267008 PASS pe HEAD final). Integrarea PR-urilor #3–#7 în main rămâne deschisă, main protejat. Următorul pas eligibil este 06, model recomandat GPT-6 Luna / Low sau Claude Haiku 5.5 / Low. STOP după 05.


## Integrare în main — stare curentă

Pașii 01–05 au dovezi de finalizare pe branchuri/PR; PR-urile #3–#7 sunt încă deschise. `main` rămâne protejat. La 2026-11-07, PR #3 a raportat `REVIEW_REQUIRED`, iar `gh pr merge 3 --merge --match-head-commit b73fc9b` a fost respins de regula branchului. Nu s-a folosit bypass `--admin`; integrarea cere review GitHub valid, apoi merge în ordine. Această limită ține de integrarea în main, nu de rezultatul CI al PASULUI 05.

## S05 — checkpoint curent

PASUL 04 a fost aprobat de Claude pe `5dc5e27` și marcat DONE în `b9607d2`. PASUL 05 a rulat doar verificări documentare și nu a adăugat produs/hosting. Local: hashuri canonice 4/4 PASS, validator conceptual și zece mutații negative PASS, linkuri relative PASS. GitHub Actions #42351263418 și #42351267008: PASS efectiv pe ce52da3; workflow activ. Model recomandat după 05: GPT-6 Luna / Low pentru PASUL 06, dacă este disponibil.


## Dovezi PASUL 05

- E05-1 PASS local: `sha256sum -c SHA256SUMS` 4/4, `python3 -B -I docs/architecture/check_contract.py` 10 mutații negative, `python3 -B -I scripts/verify_docs.py` 7 fișiere, `git diff --check`.
- E05-2 PASS GitHub Actions pe HEAD final `ce52da3c3cfc6c808ce929fee7ff5f03eea913c2`: [push run 42351263418](https://github.com/ionescugeorgemarian02-web/revenuepilot-ai/actions/runs/42351263418) și [PR run 42351267008](https://github.com/ionescugeorgemarian02-web/revenuepilot-ai/actions/runs/42351267008), ambele `completed/success`. CI pe main NOT_RUN; PR-urile sunt încă suprapuse.
- E05-3 NOT_RUN: build, unit, integrare, UI/E2E, live APIs, deployment ale produsului; produsul nu are încă module. Costuri externe noi zero. A apărut avertisment de deprecere Node 20 pentru actions/checkout v4, fără eșec de job; actualizare ulterioară cu pin verificat.
