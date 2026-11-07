# PASUL 06 — Baseline KPI, riscuri și criterii 30/60/90

Autor: Claude Sonnet 5.5 (selectat de utilizator; planul recomandă Haiku/Luna, clasă L; modelul superior nu schimbă criteriile). Data: 2026-11-07.
Bază: `4d2bd75` (branch `step-06/baseline`, peste lanțul 02–05, neintegrat în `main`).

**Regula centrală:** niciun număr din acest document nu este o măsurătoare comercială. Cifrele marcate `IPOTEZĂ` sunt praguri propuse pentru decizie, nu fapte, și le confirmă proprietarul. Valoarea măsurată actual este `N/A` până când există produs, utilizatori sau date. Nu există preț, volum, venit sau cost de infrastructură dovedit (Meta §11.1, Plan 06).

## 1. Indicatori

Status: `MĂSURABIL_ACUM` (din Git/CI/jurnale), `NECESITĂ_PRODUS`, `NECESITĂ_CLIENȚI`.

| ID | Familie | Indicator | Definiție / sursă | Status | Valoare actuală |
|---|---|---|---|---|---|
| K01 | Efort | Pași DONE din 84 | `PROGRESS.md` | MĂSURABIL_ACUM | pașii 00–05 DONE (6 din 85, numerotați 00–84) pe lanțul de branch-uri; `main` conține doar 00–01 |
| K02 | Efort | Sesiuni per pas | intrări `SESSION_LOG.md` per pas | MĂSURABIL_ACUM | 00:1, 01:1, 02:1, 03:3 (audit Codex + Claude + actualizări), 04:3 (propunere, review, remediere + re-review), 05:1. Medie nepublicată: eșantion prea mic |
| K03 | Timp | Timp de execuție per pas | timestamp primul/ultimul commit al pasului | MĂSURABIL_ACUM | N/A: nu s-a calculat sistematic; se calculează de la 07 |
| K04 | Timp | Latență review independent | timp de la predare la verdict | MĂSURABIL_ACUM | pas 04: câteva ore în aceeași zi (de măsurat exact din commituri) |
| K05 | Defecte | Constatări per review și severitate | `review-*.md` | MĂSURABIL_ACUM | pas 04: 2 MEDIUM, 2 LOW, 1 INFO; toate rezolvate la re-review |
| K06 | Defecte | Defecte scăpate (găsite după DONE) | intrări de corecție în jurnal | MĂSURABIL_ACUM | 0 înregistrate; atenție: lipsa înregistrării nu dovedește lipsa defectelor |
| K07 | Defecte | Rată CI roșu / total rulări | Actions API | MĂSURABIL_ACUM | 6 rulări, 0 eșuate (doar verificări documentare; nu validează produs) |
| K08 | Învățare | Learning accuracy: lecții candidate confirmate / lecții candidate | registrul de lecții (de creat la pasul 40+) | NECESITĂ_PRODUS | `insuficient calibrat`; nu există evaluare |
| K09 | Învățare | Recurența defectelor deja înregistrate | căutare în jurnale | MĂSURABIL_ACUM | 1 lecție candidată explicită (`__pycache__` în commit); recurența neobservată încă |
| K10 | Cost | Cheltuieli noi activate | jurnal | MĂSURABIL_ACUM | 0 (GitHub Actions pe repo public; cost exact UNKNOWN) |
| K11 | Cost | Cost AI per task finalizat | facturare API | NECESITĂ_PRODUS | N/A: nu există chei API runtime |
| K12 | Acces | Capabilități verificate / necesare (host, DB, API, CI, protecție main) | `AUDIT_PASUL_03.md` | MĂSURABIL_ACUM | verificate: GitHub, CI, protecție main (0 aprobări, PR obligatoriu); lipsesc: host, DB, chei API |
| K13 | Business | Clienți pilot activi (domenii diferite) | CRM propriu | NECESITĂ_CLIENȚI | 0 |
| K14 | Business | Timp până la prima valoare (onboarding → primul material aprobat) | evenimente produs | NECESITĂ_PRODUS | N/A |
| K15 | Business | Rată de acceptare a materialelor propuse | aprobări vs respingeri | NECESITĂ_PRODUS | N/A |
| K16 | Business | Corecturi umane per material | evenimente | NECESITĂ_PRODUS | N/A |
| K17 | Business | Plătitori, MRR, retenție, CAC, marjă | facturare | NECESITĂ_CLIENȚI | N/A; „nevalidat” până la plăți reale (Meta §14.3) |

Corelația nu este cauzalitate: K15–K17 nu se atribuie platformei fără experiment sau date de atribuire (Meta §5.15).

## 2. Criterii de succes / stop 30 / 60 / 90 zile

Zilele se numără de la acceptarea acestui document de proprietar. Pragurile numerice sunt `IPOTEZĂ`, de confirmat; ele decid ce urmează, nu promit rezultate.

| Orizont | Succes (toate necesare) | Semnal de oprire sau reevaluare |
|---|---|---|
| 30 zile | Fundația 07–15 la nivel de plan executată fără pași sărați peste dependențe; `main` actualizat cu pașii DONE; K06 și K07 urmărite; zero cheltuieli neautorizate. Ținta de volum (IPOTEZĂ): cel puțin pașii 06–10 DONE. | Mai mult de 2 pași consecutivi cu CHANGES_REQUESTED la același tip de defect; orice secret în Git; cheltuială neautorizată |
| 60 zile | Schelet minim funcțional testat local/CI (08–12), izolare tenant dovedită de teste (11), kill switch și bugete (14). Ținta (IPOTEZĂ): primul flux de brief → conținut asistat → aprobare funcționează cu date sintetice. | Fără cod executabil testat → opriți planificarea și reduceți scope-ul la un singur flux |
| 90 zile | Pilot cu 2–3 firme din domenii diferite pornit (cerință din Meta §14.3), cu consimțământ și date reale minimizate; măsurat: K13, K14, K15, K16. Dacă hostul și o cheie API nu sunt autorizate, rămâne mod manual/asistat. | Fără niciun client dispus să testeze → reevaluare ofertă; fără plată reală rămâne „nevalidat”. Nicio extindere fără K15/K16 măsurate |

Condiții de blocare permanente: nicio publicare automată, niciun cost, nicio ofertă de „AI autopilot” fără conector verificat și buget autorizat (Meta §12.2, §13.4).

## 3. Registrul de riscuri

| ID | Risc | Probabilitate (IPOTEZĂ) | Impact | Mitigare / verificare |
|---|---|---|---|---|
| R01 | Starea din `main` rămâne învechită față de lanțul de branch-uri; sesiune nouă citește stare greșită | Mare (deja) | Mediu | Regula „sursa de adevăr” în `PROGRESS.md`; integrare periodică de proprietar |
| R02 | Niciun host/DB/API disponibile gratuit | Mare | Mare | Mod local/asistat; pasul 76 compară opțiuni cu aprobare de cost |
| R03 | Protecția `main` cu 0 aprobări nu oprește un merge neanalizat al proprietarului | Medie | Mediu | Review independent în repo pentru clasele H; PR obligatoriu rămâne |
| R04 | Medii Codex/Claude cu versiuni diferite produc rezultate diferite | Medie | Mediu | CI ca referință; fixare versiuni la 08 |
| R05 | Scop prea larg (85 de pași, ~20 de familii de funcționalități) înainte de validare cu clienți | Mare | Mare | Criterii 30/60/90; un singur flux la început |
| R06 | Verificări CI doar documentare creează falsă încredere | Medie | Mediu | Etichetă explicită NOT_RUN pentru produs; test real la 08 |
| R07 | Conținut generat cu afirmații nedovedite, GDPR/ePrivacy, drepturi | Medie | Mare | Quality engine și audit juridic la pașii dedicați; nu se publică automat |
| R08 | Dependență de abonamente consumer, fără acord pentru uz în produs | Medie | Mare | Nu se folosește abonamentul ca backend; verificare termeni înainte de integrare |
| R09 | Secrete sau date personale în repo public (repo e public) | Mică | Mare | Scanare secrete în CI (de adăugat), reguli în `GIT_POLICY.md` |

## 4. Limite

Nimic din acest document nu este testat cu utilizatori. K03 și K04 nu au fost calculate din timpii reali ai commiturilor. K08, K11, K13–K17 nu pot fi măsurate fără produs și clienți. Probabilitățile din §3 sunt judecăți, nu statistici.
