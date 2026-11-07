# RevenuePilot AI — index și stare curentă

Punct unic de reluare: această pagină. Sesiunea următoare citește planul canonic și cel mai recent handoff înainte de lucru.

## Proiect și limite

Repository privat: https://github.com/ionescugeorgemarian02-web/revenuepilot-ai
Owner `ionescugeorgemarian02-web` (GitHub ID 342118131), repository ID 1449074103. Branch canonic `main`.
Surse canonice nemodificate: [Meta-prompt V3](docs/canonical/RevenuePilot_AI_META_PROMPT_CONSTRUCTIE_V3.pdf), [Plan V3](docs/canonical/RevenuePilot_AI_PLAN_CONSTRUCTIE_GITHUB_V3.pdf). PDF-urile sunt sursa de adevăr; textul extras ajută căutarea. Hashuri în `docs/canonical/SHA256SUMS`.

GitHub păstrează codul și documentația. Hostingul și runtime-ul aplicației, baza de date și cheile API comerciale nu sunt configurate. Nu modifica `fabrica-autonoma`; nu adăuga secrete ori date personale; nu activa cheltuieli fără autorizare. Un pas per sesiune, apoi STOP.

## Pas curent

- PASUL 00: DONE — repository separat și privat, surse canonice importate, push verificat. Merge commit `1e0cf4451aac1f59e88e849f8e997a999fbfcd91`; PR #1.
- PASUL 01: DONE prin PR-ul acestei livrări. A creat indexul, reguli de stare, istoric, decizii, tracker de blocaje/dovezi și handoff.
- PASUL 02: BLOCKED — politica este pregătită în [GIT_POLICY.md](GIT_POLICY.md), dar main este neprotejat și accesul la protecție a returnat HTTP 403. Nu considera pasul închis.
- PASUL 03: IMPLEMENTED, nu DONE — auditul complet este în [AUDIT_PASUL_03.md](AUDIT_PASUL_03.md) (secțiunea „verificare completă”, Claude). DONE așteaptă închiderea PASULUI 02, care cere o decizie a proprietarului (opțiunile A/B/C din §2 al auditului).
- PASUL 04–84: NOT_STARTED; urmează dependențele și recomandările modelului din plan.

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
| 02 | BLOCKED | Codex; model runtime/efort neverificat | Bază `df7d1347a99c19119544c56e57761b7d3fb46d99`; politică pregătită pe branch dedicat | Review independent neefectuat; protecția main neconfirmată. Cauză identificată în audit 03: limită de plan GitHub (repo privat, fără Pro), nu permisiuni |
| 03 | IMPLEMENTED | Claude Sonnet 5.5 (selectat de utilizator); audit preliminar anterior: Codex | Bază `08e715f046840a27dc1921b70db55f4c5943cbee` → branch `claude/step-03-audit-verificat` | Clasa M; review independent necerut, nepretins. DONE blocat de dependența 02 |

Nu inventa model runtime, versiune, efort sau usage dacă nu sunt verificabile. Instrucțiunea utilizatorului pentru sesiunile curente este să nu se folosească usage; nu îl urmări și nu raporta procente.

## Decizii curente

Jurnalul append-only: [DECISIONS.md](DECISIONS.md). Sesiunile și handoff-urile: [SESSION_LOG.md](SESSION_LOG.md). Șablon: [SESSION_TEMPLATE.md](SESSION_TEMPLATE.md).

- D00-1: permisiunea de creare remote a lipsit inițial; proprietarul a creat repo privat, după care push-ul a fost verificat. Istoric: `docs/step-00-initial-blocker.md`.
- D00-2: PDF-urile originale, textul extras și hashurile rămân împreună; fără import de cod din alte proiecte.
- D01-1: `PROGRESS.md` este singurul index pentru starea curentă; jurnalul de sesiuni și decizii rămân append-only, evitând statusuri concurente.
- D01-2: autorul consemnează modelul selectat de utilizator; modelul intern neverificabil este etichetat ca atare.

## Blocaje, riscuri, limite

- Rulesets GitHub pentru repo privat au fost refuzate de API în planul curent. Fără upgrade sau schimbare de vizibilitate; PASUL 02 va documenta politica aplicabilă.
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

Punct de reluare: PASUL 02 BLOCKED până la dovada protecției main și review; apoi PASUL 03 conform dependenței, recomandat GPT-6.1 Sol / Medium.
