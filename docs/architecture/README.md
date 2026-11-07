# PASUL 04 — arhitectura țintă și minimul implementabil

Autor: Codex. Data: 2026-11-07. Recomandare canonică: GPT-6 Astra / High;
modelul/efortul real nu sunt expuse verificabil în această sesiune.
Status: **REVIEW_PENDING**; dependența 03 este DONE conform `d87acab`.
Corecție R04-4: 01–03 sunt DONE conform predării Claude `d87acab`.
Review-ul Claude pe `fd2ebbe`, consemnat în `c377257`, a cerut modificări.
R04-1..R04-4 sunt remediate de autor și așteaptă re-review real Claude
(recomandat Opus 5.5 / High); nu reprezintă aprobare și nu deschid PASUL 05.

Bază: `7f692ba4002e75e1224836cc05bf732f2542e0dc`, ultima predare Claude,
PR #5, peste auditul PR #4. Main verificat: `df7d1347a99c19119544c56e57761b7d3fb46d99`.
Branch dedicat: `step-04/architecture`. Autor principal Codex; revendicat
2026-11-07T06:39:01Z, lease până la 2026-11-07T08:39:01Z, eliberat la publicarea
handoff-ului. Nu este lock atomic; verifică PR-urile și activitatea înainte de preluare.

## 1. Contract și ipoteze

Livrare exclusiv documentară: comparații, diagramă, domenii, limite de securitate,
plan de migrare, costuri, contracte de dependență și probe de consistență.
Limbajul/frameworkul definitiv se aleg la 08, threat model la 07, DB/migrații la 12,
orchestrator la 18, deployment la 76–77. Niciun modul produs nu este implementat aici.

Cerințe: Meta-prompt §§1–3, 5–12 și 15–19; Plan V3 PASUL 04, dependență 03.
Auditul 03 distinge mediile Codex/Claude: versiuni diferite, instalări indisponibile
în mediul Claude. Nu extrapolăm accesul unuia la celălalt. GitHub rămâne depozit
pentru cod și probe, nu baza de date a clienților sau backend comercial.

Corecție R04-4: repository public și main protected=true, reverificate din API
la remediere. Situația anterioară rămâne în SESSION_LOG și Git. Niciun host ori
API comercial activat aici; disponibilitatea unui VPS gratuit nu este presupusă.
Ipoteză de proiectare: volum inițial mic și muncă asistată, de măsurat pe pilot.
Nu există SLO, throughput, buget comercial sau prețuri validate; nu le promitem.

## 2. ADR-04-1 — unitate de livrare

| Variantă | Avantaje | Cost și risc | Decizie propusă |
|---|---|---|---|
| Monolit modular, joburi durabile în aceeași DB | O singură versiune, tranzacții locale, debug și teste simple | Izolarea resurselor slabă dacă joburile grele rămân în proces | Alegere minimă; module și porturi explicite |
| HTTP serverless + DB + job runner extern | Scalare independentă la trafic variabil | Conexiuni DB, timeout, retries, egress și facturare per invocare; schimbări de furnizor | Nu este ținta inițială; serviciile plătite necesită autorizare și probe host/cost |
| API + worker separat, aceeași versiune de domeniu | Limite CPU/memorie și reluare joburi fără blocarea HTTP | Două procese, coordonare deployment și job leases | Prima extracție dacă măsurătorile arată necesitatea |
| Microservicii per agent/domeniu | Echipe și scalare independente | Consistență distribuită, observabilitate, operațiuni și cost de migrare mari | Amânat; nu există motiv măsurat acum |

Scopul modularității este să putem separa procese fără să rescriem regulile.
Nu avem un proces LLM pentru fiecare rol. Rolurile sunt contracte/logici versionate;
providerii runtime rămân dezactivați până la acces și buget verificate.

## 3. Diagrama conceptuală

Săgețile de mai jos arată fluxul de date, nu importuri de cod.

```text
[Utilizator mobil / operator]                 [Import manual Codex/Claude/Gemini]
             | HTTPS viitor                              |
             v                                          v
+--------------------- LIMITA APLICAȚIEI -------------------------------+
| CONTROL: identitate -> tenant/rol -> validare -> politici/buget       |
|          -> caz de utilizare -> quality review -> aprobare versionată |
|                              |                                      |
|                   tranzacție date + outbox                           |
|                              v                                      |
| EXECUȚIE: job durabil -> lease -> revalidare drepturi/buget/aprobare   |
|          -> port provider -> rezultat/receipt -> reconciliere         |
|          -> eveniment -> evaluare -> lecție candidată                 |
|                                                                     |
| Domeniu comun: brand, campanie, lead, evaluare, memorie per tenant     |
+---------------------------------------------------------------------+
       | port persistență         | port assets        | port provider
       v                          v                    v
 [DB relațională viitoare] [storage obiecte viitor] [API autorizat viitor]
```

Control și execuție sunt separate logic din prima versiune. Inițial același deploy,
cu joburi scurte și limitate; media/CPU intens se extrage în worker înainte de utilizare
reală. În absența providerului, exportul are status READY_FOR_MANUAL_ACTION;
nu devine PUBLISHED fără confirmare cu proveniență. Un adapter dezactivat respinge
apelul explicit, nu întoarce succes simulat.

## 4. Domenii și relații

| Domeniu / owner logic | Entități și relații | Regula de acces |
|---|---|---|
| Identitate | User global; Organization; Membership(User, Organization, Role) | Identitatea nu implică drept în toate organizațiile |
| Brand | Organization → Brand → Offer/Audience/ProfileVersion | Fiecare versiune are tenant și proveniență |
| Campanii | Brand → Brief → Strategy → Campaign → ContentVersion/AssetRef | Brief/brand și versiune aprobate explicit |
| Quality / approvals | Evaluation(ContentVersion, RubricVersion); Approval(artifact hash, policy version, actor) | Generatorul nu promovează propriile praguri critice |
| Execution | Task → Job/Attempt → ProviderReceipt; Outbox/Inbox | tenant, correlation, idempotency și scope limitat |
| Lead / CRM | Campaign → Lead → Opportunity/Conversion | Consent, sursă și ID compus; export separat per tenant |
| Analytics / experimente | Event → MetricAggregate; Experiment → Assignment | Separare TEST/LIVE; venit și cost cunoscute pentru ROI |
| Memorie | Source → MemoryItem → LessonCandidate → CalibrationProposal | Retrieval și invalidare pentru același tenant |
| Buget / integrare | Organization → BudgetReservation/Integration/SecretRef | Policy decide; secretul nu apare în artefact |
| Audit / privacy | AuditMetadata; RetentionPolicy; DeletionRequest | Evenimente minimizate; datele sensibile au retenție |

Un domeniu nu modifică tabelele altuia arbitrar; folosește cazuri de utilizare și
porturi explicite. Nucleul nu depinde de furnizori, HTTP, framework sau DB concretă.
Importurile permise sunt în `dependencies.json`; composition root le conectează.
Dependințele declarate nu dovedesc izolarea codului încă neimplementat.

## 5. Invariante de securitate și date

- Tenantul autorizat rezultă din sesiune și membership validate server-side; un tenant_id
  trimis de client nu este dovadă. Reautorizare pentru joburi, exporturi, linkuri de
  download, cache, căutare și evenimente. RBAC explicit, implicit deny.
- Resursele au chei `(tenant_id, id)` și relații către `(tenant_id, parent_id)`;
  unicitatea de idempotency este `(tenant_id, operation, key)`. Nu folosi FK doar pe id
  când permite relație între organizații. Query-urile primesc context obligatoriu.
- PostgreSQL RLS este apărare suplimentară propusă, nu substitut al autorizării.
  Setarea tenantului trebuie legată de tranzacție și resetată între conexiuni; rolul
  aplicației nu deține tabele și nu are bypass RLS. Disponibilitatea se probează la 12.
- Providerii primesc numai payloadul necesar; secretele vin din storage dedicat,
  accesibil exclusiv adapterului. Callback-ul are semnătură și identificator server-side
  al integrării; tenantul nu se acceptă din payload nevalidat.
- Approval este legat de versiunea/hashul artefactului, canal și limite de buget.
  O editare, retragere a consimțământului sau expirare invalidează execuția; înaintea
  efectului extern se revalidează și se auditează revocarea concurentă. Nu se poate
  retracta garantat un apel deja în zbor; răspunsul se reconciliază și se escaladează.
- Conținutul importat este date neîncredere: nu poate acorda tool permissions sau
  modifica politica. Ingestia URL/media cere mitigări SSRF și upload la 07/49.
- Metadata de audit poate fi append-only în limita retenției; PII/payloadurile sunt
  separate și ștergibile. Ștergerea tenantului invalidează surse, index/cache, memorii,
  exemple derivate și jobs. Pentru R04-1, registrul de ștergeri (deletion ledger)
  trăiește în storage durabil separat de DB-ul operațional și de snapshoturile sale,
  cu backup separat și o copie într-un domeniu de pierdere distinct de host. Nu este
  suprascris de restore-ul aplicației. Furnizorul/accesul/costul vor fi verificate la
  alegerea hostului; fără registru independent recuperabil, restore-ul rămâne blocat.
- Ledgerul reține doar ID-uri opace nereutilizabile, scope-ul ștergerii, sequence ID,
  moment, versiune și status, fără PII brută. Identificatorii și registrul sunt și ei
  protejați prin acces limitat și retenție verificată juridic. Retenția este cel puțin
  durata maximă a tuturor backupurilor restaurabile plus fereastra de restaurare/replay;
  expirarea unei intrări cere dovada că nicio copie relevantă nu mai este restaurabilă.
- Fluxul ștergerii: se confirmă durabil intenția în ledger înainte de finalizarea DSAR,
  apoi se elimină/invalidează datele și derivatele; retries sunt idempotente. Un crash
  după intenție lasă o operațiune pending care se reia. Fără confirmarea ledgerului,
  cererea nu devine completed; tenantul rămâne suspendat cât operațiunea este pending.
- Restore: snapshot T0, ștergere la T1, restore T0 la T2. Aplicația pornește izolată,
  cu acces utilizatori și efecte externe oprite. Recuperează ledgerul actual independent,
  verifică integritatea și continuitatea până la ultimul sequence confirmat, aplică
  toate intențiile relevante inclusiv cele pending, apoi invalidează cache/index,
  memorii, exemple și joburi și verifică absența datelor. Ledger indisponibil, incomplet
  ori prospețime nedovedită => fail closed, fără reactivare. Un checkpoint de reluare
  sincronizează și ștergerile sosite în timpul restore-ului; nu redeschide accesul
  până la drenarea lor. RPO pentru ștergerile confirmate trebuie să fie zero înainte
  de servire: dacă infrastructura aleasă nu poate proba acest lucru, nu se redeschide.
  Procedura exactă și testele sunt la 45/77; cerințele juridice se validează separat.

## 6. ADR-04-2 — persistență și livrare de joburi

| Opțiune | Utilizare | Cost de schimbare / compromis |
|---|---|---|
| PostgreSQL relațional | Țintă propusă pentru tranzacții, FK compuse, concurență, RLS | Necesită DB reală și probe de backup/conectare; serviciul nu este ales |
| SQLite local | Eventuale demo-uri/teste portabile, numai cu limitări etichetate | Nu validează RLS/concurența PostgreSQL; migrarea necesită conversie date și teste pe motorul țintă |
| DB managed/serverless relațională | Alternativă viitoare; costul plătit necesită aprobare, nu țintă inițială | Probe de SQL/tranzacții, pooling, cost invocări/egress, export și restore înainte de alegere |
| DB document / cache / vector store separate | Doar dacă cerințe măsurate o justifică | Cost de sincronizare, tranzacții și ștergere cross-store; nejustificat acum |

Stare și eveniment outbox se scriu în aceeași tranzacție. Workerul folosește lease
cu expirare și fencing token/version la finalizare; un worker expirat nu finalizează
rezultatul altuia. Delivery este at-least-once. Inbox și idempotency deduplică retries;
un timeout după trimitere produce UNKNOWN_OUTCOME și reconciliere prin receipt sau
interogare provider. Pentru provider fără idempotency/query, escaladare manuală,
fără retrimitere oarbă. Nu promitem exactly-once pentru efect extern.

Bugetul se rezervă atomic înainte de job; totalul disponibil include rezervările.
Retry are limită, deadline, backoff și limită de cost. Un rezultat ambiguu păstrează
rezervarea până la reconciliere; anularea din coadă nu anulează automat efecte externe.
La indisponibilitate DB înainte de commit nu se efectuează apelul; la cădere după apel
se păstrează incertitudinea și se recuperează prin procesul de mai sus.

Assets sunt obiecte în storage cu metadata în DB, nu fișiere mari în Git. Uploadul și
DB nu au tranzacție comună: staging → validare → referință activă; garbage collection
cu grație, verificare referințe și replay sigur. SQLite/mock nu dovedește acest flux.

## 7. ADR-04-3 — memorie, evaluare și adaptare

Inițial: lecții manuale versionate, retrieval filtrat per tenant, proveniență, TTL și
retragere. Căutare simplă înainte de embeddings. LLM judge produce opinie cu probe;
politica deterministă aplică hard gates. Factualitatea nu derivă dintr-un scor creativ.
O propunere de calibrare păstrează baseline, dataset și versiuni; holdout separat,
review independent, canary ulterior și rollback. Fără date reale: rezultat SIMULAT,
fără concluzii de venit/viralitate și fără schimbare a ponderilor modelelor consumer.
MCP/A2A/LangGraph/DSPy se evaluează la pașii 24/42, nu devin dependențe prin diagramă.

## 7a. ADR-04-4 — resurse, oprire și mod degradat (R04-2)

Țintă inițială de topologie: un singur host mic cu aplicația, workerul și PostgreSQL
pe același VPS, numai dacă la 76 se confirmă un host disponibil/autorizat fără cost
nou. Procesele pot fi separate pe același host fără microservicii. Nu există un VPS
configurat acum; dacă nu există resursă gratuită adecvată, se continuă local/asistat,
nu se cumpără infrastructură. Copia independentă a ledgerului/backupului de mai sus
este o condiție de restore, nu un serviciu presupus disponibil gratuit.
Serverless și DB managed plătite sunt alternative care cer aprobarea costului,
nu variante implicit gratuite. Alegerea definitivă se validează la 76.

Bugetul de RAM/CPU/disk se măsoară pe hostul ales: rezervă OS + PostgreSQL + aplicație
+ vârful workerului + marjă; definește limite și observă OOM, I/O, latența și spațiul
liber înainte de trafic real. Nu inventăm o capacitate numerică. Concurență implicită
propusă: un singur job activ per host, maximum unul per tenant/integrare, ajustabilă
numai după măsurători și bugete. Limita este partajată prin lease atomic în DB,
nu câte un contor local per worker; crash-ul nu dublează capacitatea rezervată.
Coada are plafoane finite configurate global și per tenant (număr și dimensiune),
deadline și politică echitabilă de selecție. Fără plafoane configurate, enqueue automat
este dezactivat. La plafon se returnează DEFERRED/429 cu motiv și retry limitat;
nu se pierde taskul prin acceptare falsă și nu se acumulează memorie nelimitată.

Kill switch persistent, global și per tenant/integrare, cu prioritate STOP dacă
oricare nivel este oprit. Operatorul autorizat poate opri/reporni, acțiunea și
versiunea politicii sunt auditate; restart-ul nu îl resetează. Executorul citește
starea durabilă proaspătă înainte de claim și înainte de fiecare apel cu efect extern,
inclusiv fiecare retry. Citire eșuată/stare necunoscută => fără efect extern. Revalidarea
este coordonată cu emiterea permisului de dispatch; un STOP blochează toate permisele
ulterioare. Un apel deja autorizat/în zbor poate totuși termina: este marcat și
reconciliat, nu promis anulat. La restore, starea implicită este STOP până la
reconcilierea setărilor curente de oprire și revocare, nu valoarea ENABLED din backup.

Când providerul, bugetul sau resursele nu permit automatizarea, taskul devine
PAUSED/READY_FOR_MANUAL_ACTION, cu motiv vizibil și checkpoint. Exportul manual
rămâne supus drepturilor și consimțământului; un stop de securitate nu poate fi ocolit
prin export. Nu se lansează automat retry când operatorul a preluat acțiunea:
claim-ul manual și confirmarea externă se înregistrează, se reconciliază orice efect
ambiguu înainte de reluare. Reluarea cere autorizare și o nouă verificare a politicii.

## 8. Migrare la host și costuri

1. La 08/12: fixează runtime/lockfile și probează motorul DB țintă; cazurile din test-plan
   devin teste executabile pe cod. Aceeași versiune și aceleași fixtures în ambele medii.
2. La 76: compară hostul real după DB, job runner, storage, limite CPU/timp, egress,
   observabilitate, backup/restore, regiune, contract și cost. Dacă niciunul nu este
   autorizat, se păstrează modul local și activitățile independente ale planului.
3. La 77: staging cu date sintetice, migrație expand/backfill/validate/contract,
   număr de rânduri și hashuri pe tenant; perioadă de compatibilitate înainte de drop.
   Backup restaurat cu ledger independent conform §5, kill switch implicit STOP,
   healthchecks și rollback probat înainte de activare reală.
4. La separarea workerului: conservă contractele, schema mesajului și versiunea de
   domeniu; rollout compatibil cu joburile vechi, drain și lease transfer fără dublare.
5. Rollback de aplicație doar cât schema rămâne compatibilă; rollback date destructive
   nu este automat sigur. Restore implică fereastră de pierdere măsurată și reconcilierea
   efectelor externe; nu refolosi orbește snapshot-uri de joburi finalizate.

Estimarea totală propusă: host + DB + backup + storage GB-lună + egress GB + job CPU
+ API/media per operație + monitorizare + suport uman + cost migrare. Rata de retry și
munca manuală intră în cost/tenant. Nu avem tarife sau volum validate; cost în bani și
ore de migrare UNKNOWN. Cost nou activat în acest pas: zero.

Extragerea workerului devine necesară când joburile depășesc limita HTTP ori afectează
latența măsurată. Separarea DB/servicii se reevaluează la limite de conexiuni, contention,
cerințe de izolare contractuală sau echipe independente; pragurile se fixează după
baseline, nu din numărul de „agenți”. Complexitatea evitabilă este un cost real.

## 9. Validare și acceptare

Vezi [test-plan](test-plan.md) și [handoff](handoff.md). Validatorul verifică exclusiv
contractul de dependențe conceptual; nu dovedește securitatea, durabilitatea sau
performanța unei aplicații. Verdictul arhitectural este o propunere pentru reviewer.
Pentru DONE: review real din familia opusă, constatări rezolvate, dependența 03 închisă,
commit/push și starea actualizată. Nu începe 05 în această sesiune.


Actualizare 2026-11-07: integrată predarea Claude `d87acabe39b7ca7808d4f55c7ffa62bb583b043c`, care închide 02–03. Repo public și main protected=true reverificate. Mențiunile de dependență deschisă din istoricul inițial descriu situația la redactare; blocajul actual al PASULUI 04 este review-ul independent. PR-urile anterioare sunt încă deschise.
