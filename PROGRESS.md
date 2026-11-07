# RevenuePilot AI — index și stare curentă

Punct unic de reluare. Ultima actualizare: 2026-11-07, Codex, PASUL 07. Citește planul canonic și [predarea curentă](docs/security/handoff.md) înainte de lucru.

## Proiect și limite

Repository public: https://github.com/ionescugeorgemarian02-web/revenuepilot-ai
Owner `ionescugeorgemarian02-web` (GitHub ID 342118131), repository ID 1449074103. Branch canonic `main`.
Surse canonice nemodificate: [Meta-prompt V3](docs/canonical/RevenuePilot_AI_META_PROMPT_CONSTRUCTIE_V3.pdf), [Plan V3](docs/canonical/RevenuePilot_AI_PLAN_CONSTRUCTIE_GITHUB_V3.pdf). PDF-urile sunt sursa de adevăr; textul extras ajută căutarea. Hashuri în `docs/canonical/SHA256SUMS`.

GitHub păstrează codul și documentația. Hostingul, DB runtime și cheile API comerciale nu sunt configurate. Nu modifica `fabrica-autonoma`; nu adăuga secrete ori date clienți. Un pas per sesiune, apoi STOP. Acordul permanent al utilizatorului permite operațiile de dezvoltare necesare fără confirmări repetate (D07-1); dovezile/review-ul rămân reale.

## Registrul execuțiilor

| Pas | Status | Autor / model declarat | Dovezi / rezultat | Review |
|---|---|---|---|---|
| 00 | DONE | Codex; model exact neverificat atunci | `1e0cf44`, PR #1; surse canonice și repository separat | Independent nepretins |
| 01 | DONE | Codex; Luna / Low declarat de utilizator atunci | index, jurnale, decizii și handoff în main | Clasa L |
| 02 | DONE | Codex politică; Claude Sonnet 5.5 verificare | [GIT_POLICY](GIT_POLICY.md), D02-1; main protejat | Clasa T |
| 03 | DONE | Claude Sonnet 5.5; audit preliminar Codex | [Audit](AUDIT_PASUL_03.md), repository public | Clasa M |
| 04 | DONE | Codex; model/efort runtime neverificate | [Arhitectură](docs/architecture/README.md), remediere `5dc5e27`, inclusă în main | Claude Opus 5.5 APPROVED: [raport](docs/architecture/review-claude.md) |
| 05 | DONE | Codex; model/efort runtime neverificate | [Probe CI](docs/ci/step-05.md), PR #7 integrat `4d2bd75`; Actions #42351263418 și #42351267008 PASS pe `ce52da3` | Clasa M |
| 06 | DONE | Claude Sonnet 5.5 | [Baseline KPI](docs/planning/baseline-kpi.md), [backlog](docs/planning/backlog.md), PR #8 integrat `63ac761` | Clasa L |
| 07 | REVIEW_PENDING | Codex; model/efort runtime neverificate | [Threat model, 18 amenințări și politici](docs/security/README.md); baza `63ac761`, branch `step-07/threat-model` | Clasa H: review real Claude încă NOT_RUN |
| 08–84 | NOT_STARTED | — | 08 depinde de 05 și 07, conform planului canonic | — |

Corecție față de indexul vechi: `main` la `63ac761c0fb972d10592bdd38a3335c23a4312e8` conține 00–06. Mențiunile anterioare „main are doar 00–01”, „05/06 neintegrat” și lanțul obligatoriu de PR-uri suprapuse sunt depășite; istoria rămâne în Git și SESSION_LOG. PR #9 pentru autorizare/CI este separat și nu a fost integrat de această sesiune. Numărul curent al aprobărilor GitHub nu este dedus din auditul istoric; regulile efective se verifică la integrare, fără bypass.

Nu inventa model runtime, versiune, efort sau usage. Utilizatorul a cerut să nu se folosească usage; nu îl urmări și nu raporta procente.

## Stări și tranziții

Stări: `NOT_STARTED`, `READY`, `CLAIMED`, `IN_PROGRESS`, `IMPLEMENTED`, `TESTING`, `REVIEW_PENDING`, `CHANGES_REQUESTED`, `VERIFIED`, `DONE`, `BLOCKED`, `DEFERRED`, `FAILED`.

1. La start: fetch; confirmă repository, branch, HEAD și worktree; citește indexul, planul și ultima intrare de jurnal.
2. READY cere dependențe DONE și scope autorizat. Înregistrează autorul, modelul verificabil/declarat, baza, branchul și claim-ul înainte de lucru.
3. Parcurge CLAIMED → IN_PROGRESS → IMPLEMENTED → TESTING; raportează testele efective, nu cele deduse din documentație.
4. VERIFIED/DONE cer criterii, commit/push, probe și review real când este cerut. Fără reviewer pentru H: REVIEW_PENDING, nu DONE.
5. Lipsa accesului/dependenței: BLOCKED/DEFERRED, cu probă și cale de rezolvare. Nu sări peste dependențe.
6. Jurnalele de sesiuni și decizii sunt append-only; review-ul aparține reviewerului și identifică SHA-ul. Fără force-push ori review inventat.

## Dovezi și limite curente

- E07-1 PASS local: hashuri canonice 4/4; graf conceptual cu control pozitiv și zece mutații negative; linkuri în 12 fișiere; `git diff --check`. Comenzi în [verification](docs/security/verification.md).
- E07-2: [PR #10](https://github.com/ionescugeorgemarian02-web/revenuepilot-ai/pull/10), livrare `3d94c3999783631936ba407575c18983c42cb9d3`, trigger CI `d402574`. Push/HEAD remote PASS. CI remote BLOCKED/NOT_RUN: dispatch respins HTTP 422, `Actions has been disabled for this user`. Workflow active, dar zero runs/checks pentru 07. Detalii în checkpointul S07 din [SESSION_LOG](SESSION_LOG.md).
- E07-3 NOT_RUN: toate scenariile runtime T01–T18, build/unit/integration/E2E/deploy/API live și review independent 07. Nu există implementare de produs în acest pas.
- Cost comercial nou activat: zero. Nu s-au creat servicii, conturi, hosting sau credențiale. Nu pretindem cost monetar Actions fără facturare.
- Blocaj CI: Actions dezactivat la nivelul utilizatorului GitHub; triggerul push și dispatch explicit nu au produs o rulare. Reactivarea contului/Actions trebuie rezolvată prin mecanismele GitHub; nu este o lipsă de aprobare pentru lucru. Review-ul documentar Claude poate începe, integrarea așteaptă probele CI.
- Riscul curent: măsurile de securitate sunt contracte propuse, nu protecții deja instalate. Clasa H necesită reviewer din familia opusă înainte de DONE.

## Reluare și predare

Reluarea este **review-ul PASULUI 07** din `step-07/threat-model`, după fetch și verificarea SHA-ului curent. Recomandat Claude Opus 5.5 / High. Există autorizare pentru operațiile Git necesare; nu cere din nou confirmarea proprietarului. Review-ul verifică livrarea, poate cere R07-n și permite integrarea numai cu probele cerute și mecanismele GitHub disponibile.

După DONE 07: PASUL 08, GPT-6.1 Sol / Medium sau Claude Sonnet 5.5 / Medium; dependențe 05,07. În această sesiune STOP înainte de 08.

Istoric: [SESSION_LOG.md](SESSION_LOG.md), [DECISIONS.md](DECISIONS.md). Șablon: [SESSION_TEMPLATE.md](SESSION_TEMPLATE.md). Documentele vechi de handoff sunt instantanee istorice; acest index și predarea 07 descriu punctul curent.
