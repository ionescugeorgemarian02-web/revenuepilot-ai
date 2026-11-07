# Checkpoint istoric — blocaj rezolvat prin creare manuală

Acest document păstrează raportul inițial. Starea curentă este în /PROGRESS.md.

# Registru persistent minimal — PASUL 00

Data: 2026-11-07 UTC. Executor: Codex; identitatea exactă a modelului și nivelul UI nu sunt expuse verificabil sesiunii. Recomandarea planului pentru 00: GPT-6.1 Sol / Medium.

## Stare și contract

PASUL 00: **BLOCKED**. Nicio dependență. Scope: repository nou privat, import integral al celor două surse, punct unic de pornire și dovezi Git. Nu sunt autorizate module, hosting, API-uri, modificări în fabrica-autonoma sau execuția PASULUI 01.

Owner autentificat verificat: `ionescugeorgemarian02-web` (GitHub user ID 342118131).
Repository propus: `ionescugeorgemarian02-web/revenuepilot-ai` — **NU ESTE CREAT**.
Branch local inițial: `step-00-bootstrap`. Commit de bază: niciunul (istoric nou).
Commitul acestui checkpoint se identifică prin `git log -1 --format=%H -- PROGRESS.md`; hashul nu este inserat autoreferențial în propriul conținut.
Remote: neconfigurat. Push: NOT_RUN. PR: necreat. Branch implicit remote: necunoscut.
PASUL 01: NOT_STARTED, depinde de 00; nu este READY înainte de verificarea remote și push.
Pașii 02–84: NOT_STARTED; dependențele și modelele rămân în planul canonic.

## Dovezi și verificări efectiv executate

- PASS: citire integrală a meta-promptului (11 pagini) și planului (34 pagini), prin `pdftotext -layout` și citirea extragerilor pe intervale.
- PASS: conectorul GitHub `get_profile` confirmă contul; `gh auth status` și `gh api user --jq '{login, id}'` confirmă aceeași identitate în CLI. Niciun token salvat în proiect.
- PASS: `gh api -i user/repos --method GET --paginate --jq '.[].full_name'` permite listarea; RevenuePilot AI nu apărea în lista returnată.
- FAIL: `gh repo create ionescugeorgemarian02-web/revenuepilot-ai --private --description ...` → `GraphQL: Resource not accessible by integration (createRepository)`.
- FAIL: `gh api --method POST user/repos -f name=revenuepilot-ai -F private=true -f description=...` → HTTP 403, `Resource not accessible by integration`.
- Acces de citire verificat; creare refuzată. Dreptul de push pe noul repository rămâne NOT_RUN, deoarece repository-ul nu există.
- Verificarea locală de integritate: `sha256sum -c SHA256SUMS` în docs/canonical; comparație byte-for-byte a PDF-urilor cu atașamentele; regenerare pdftotext și comparație cu textele importate. Rezultatele sunt în LOCAL_CHECKS.txt.
- Verificări Git locale: `git fsck --full`, `git status --porcelain`, `git log -1`. Hash efectiv și rezultate în raportul final.
- Build / unit / integrare / UI / E2E / CI / live APIs / deploy: NOT_RUN; nu există produs în scope.
- Review independent: NOT_RUN, neobligatoriu pentru clasa M a pasului 00; nu există aprobare cross-family pretinsă.

Baseline: nu exista checkout RevenuePilot AI în /workspace, nici repository cu acest nume în lista accesibilă. După execuție există numai un checkpoint Git local, documentar. Fabrica-autonoma nu a fost clonată sau modificată; nicio operație de scriere a vizat-o.

## Blocaj și unica acțiune manuală

Conexiunea existentă nu permite crearea remote (GraphQL refuzat și REST HTTP 403). Nu se poate declara succes remote sau DONE.

De pe telefon, creează un repository **Private**, gol, numit `revenuepilot-ai`, în contul `ionescugeorgemarian02-web`, la https://github.com/new (fără README, .gitignore sau licență inițială).

După crearea manuală, o nouă sesiune reia tot PASUL 00 și verifică accesul conexiunii la noul repository; crearea manuală nu dovedește automat dreptul conexiunii de push.

## Decizii, limite, lecție și handoff

D00-1: folosim CLI autentificat în același cont deoarece conectorul nu oferă creare repository. Am verificat atât GraphQL, cât și REST; ambele refuză crearea. Nu încercăm ocolirea permisiunilor.
D00-2: păstrăm originalele PDF și extragerile text cu SHA-256; nu copiem cod din alte proiecte. Acest registru este minimul pentru 00, nu închiderea PASULUI 01.
Costuri noi: niciun serviciu plătit/API comercial activat; costul sesiunii și quota abonamentului nu sunt expuse, deci nu sunt cuantificate.
Risc: workspace-ul nu substituie stocarea remote și nu are aici o garanție verificată de retenție; copia bundle exportată permite recuperarea. Remote și push rămân blocante.
Lecție candidată: autentificarea și listarea repository-urilor nu dovedesc dreptul de creare. Probă: succes user/repos vs refuz createRepository și POST user/repos. Îmbunătățire propusă: verificați operația concretă înainte de orice DONE. Nu este promovată ca regulă runtime; nu există motor de învățare sau schimbare de ponderi.

Gates: G0 BLOCKED (remote/push lipsesc); G1–G8 NOT_IMPLEMENTED. Dovezile locale nu certifică gates de platformă.

Reluare: citește README, sursele canonice și acest registru; verifică identitatea contului și repository-ului, branchul/HEAD și worktree curat; rezolvă exclusiv 00, verifică PDF-uri/texte/hashuri și push/HEAD remote. Numai după dovezi complete poate deveni DONE, cu 01 READY. STOP după 00.

Model pentru reluarea 00: GPT-6.1 Sol / Medium (alternativ Claude Sonnet 5.5 / Medium). Pentru PASUL 01, după închiderea 00: GPT-6 Luna / Low (alternativ Claude Haiku 5.5 / Low), dacă sunt disponibile în selector. Utilizatorul schimbă manual modelul.
