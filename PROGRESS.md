# Registru persistent minimal — RevenuePilot AI

## Stare curentă

Data: 2026-11-07 UTC. PASUL 00: **IMPLEMENTED**, verificare push în curs.
PASUL 01: NOT_STARTED până la confirmarea remote; pașii 02–84: NOT_STARTED.
Executat exclusiv 00. Niciun modul de produs. Nu modifica fabrica-autonoma.

Repository privat: https://github.com/ionescugeorgemarian02-web/revenuepilot-ai
Owner: ionescugeorgemarian02-web, ID 342118131. Repo ID: 1449074103.
Branch de lucru: step-00-bootstrap. Branch implicit: main.
Bază remote: 590e4d181a7b07afdbf496ff08cd954543699a02 (Initial commit, README creat de utilizator).
Checkpoint local anterior: 55c5d695d76f8c940b1f11268c390706ed930ef0.
Integrare: merge al celor două istorice; conflict add/add README rezolvat prin completarea paginii de pornire. Commitul inițial remote este păstrat, fără force-push.
Commitul registrului se identifică prin `git log -1 --format=%H -- PROGRESS.md`; HEAD prin `git rev-parse HEAD`.

## Scope și acceptare

Un repository separat, preferabil privat, ambele PDF-uri originale și textele integrale, progres minimal, URL/branch/HEAD și dovada accesului efectiv. Fără hosting, API-uri, module, cod din alte proiecte sau execuția 01. Nicio cheltuială nouă autorizată ori inițiată.

## Dovezi

- PASS: conectorul GitHub get_repo și gh repo view confirmă repository privat, main și drepturi admin/push/pull.
- PASS: fetch real prin HTTPS; origin exact repository RevenuePilot AI; main conținea numai README.md cu titlul proiectului.
- PASS: integritatea surselor verificată prin SHA-256, comparație byte-for-byte PDF și regenerare pdftotext identică (11 + 34 pagini). Detalii: LOCAL_CHECKS.txt.
- PASS: cele două documente au fost citite integral în sesiunea inițială; rămân canonice, nemodificate.
- Publicare/PR și verificare remote: în curs, fără afirmație de succes anticipată.
- Build, teste unitare/UI/E2E, API-uri live, CI și deploy: NOT_RUN, fără produs în scope.
- Review independent: NOT_RUN, neobligatoriu pentru clasa M a pasului 00; nicio aprobare cross-family pretinsă.

Baseline: commit local cu 00 BLOCKED și remote creat manual cu un README. Rezultat urmărit: ambele istorice păstrate, surse și stare accesibile pe GitHub. Raportul istoric al refuzurilor GraphQL/REST rămâne în docs/step-00-initial-blocker.md și Git.

## Decizii, limite și lecție

D00-3: README-ul creat accidental nu impune ștergerea sau recrearea repository-ului. Păstrăm commitul inițial și completăm README în merge auditat.
D00-4: folosim PR pentru publicarea documentelor, fără a introduce politica Git completă rezervată pasului 02. Nu pretindem review independent dacă nu a avut loc.
Costuri: fără servicii plătite sau API-uri comerciale; costul/quota sesiunii nu sunt expuse măsurabil.
Host și chei API comerciale: indisponibile conform specificației; nu au fost configurate. GitHub este sursă de adevăr, nu hostingul produsului sau DB runtime.
Lecție candidată: dreptul de creare și dreptul de push sunt distincte; eroarea inițială de creare nu dovedește imposibilitatea scrierii într-un repo creat manual. Probă: refuz 403 anterior, acces metadata/fetch actual. Nu este regulă runtime promovată și nu există motor de învățare implementat.
Executor: Codex; numele exact al modelului și nivelul UI nu sunt expuse verificabil. Niciun reviewer extern invocat.
Gates: G0 BLOCKED până la verificarea push/remote; G1–G8 NOT_IMPLEMENTED.

## Reluare și STOP

Citește README, sursele canonice, acest registru și dovezile. Verifică remote, branch, HEAD, worktree și progresul actualizat înainte de orice editare. Un singur pas per sesiune. Nu executa PASUL 01 în sesiunea curentă.
După închiderea verificată a 00, următorul pas este 01 (registru persistent extins și jurnal de decizii), cu dependența 00 satisfăcută. Model recomandat: GPT-6 Luna / Low; alternativ Claude Haiku 5.5 / Low, dacă sunt în selector. Alegerea se face manual de utilizator.
