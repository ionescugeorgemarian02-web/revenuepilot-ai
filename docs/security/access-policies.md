# Contractul viitor de acces

Acesta este un contract de proiectare, **nu un motor de politici implementat**. Se aplică arhitecturii aprobate la 04. Orice lipsă, eroare de evaluare, dependență indisponibilă ori valoare necunoscută produce DENY înainte de efecte externe.

## Identitate și privilegii minime

Tenantul efectiv provine din sesiune și membership verificat server-side; un header, parametru, mesaj în coadă sau text de model nu poate acorda membership. Schimbarea tenantului cere reevaluare. Joburile păstrează principalul inițiator, tenantul, scopul și versiunea politicii; workerul reevaluează starea actuală înainte de dispatch/retry, fără a moșteni drepturile altui job.

| Principal/scop | Permisiuni țintă | Interdicții implicite |
|---|---|---|
| Anonim | autentificare și resurse publice aprobate | orice obiect tenant, job sau token |
| Tenant viewer | citire obiecte explicit vizibile ale propriului tenant | scriere, export masiv, aprobări, provider |
| Tenant editor | draft și propunere de job în tenant | publicare, conectare OAuth, schimbare rol, buget sau politici |
| Tenant approver | aprobarea unei intenții în tenant, în limita delegată | autoextindere de plafon/scop; aprobarea nu execută direct |
| Tenant admin | membership, integrări și limite în plafonul produsului | drepturi în alt tenant, acces token brut, depășire plafon global |
| Agent runtime | citire minimă și propuneri prin unelte numite | shell/SQL/Git arbitrar, acces secret, aprobare, schimbare politică |
| Executor/worker | consum job autorizat și un adapter selectat | schimbare artefact/scop, alegere liberă tenant, bypass policy |
| Operator platformă | sănătate agregată, STOP global, incident response | citire implicită date client; acces de suport necesită grant temporar auditat |
| CI pentru PR | checkout și verificări fără secrete, contents:read | deploy, write token, execuție privilegiată a codului din fork |

Permisiunile sunt conjunctive: rol **și** obiect/tenant **și** acțiune **și** context curent. Rolurile nu implică moștenire ascunsă; un admin care publică are nevoie de grantul corespunzător. Schimbările de rol nu permit actorului să își depășească plafonul delegat. Service accounts au audiență/scop/TTL limitate și se rotesc. Accesul de suport se acordă de tenant, cu motiv, durată și obiecte, fără tokenuri exportabile.

## Policy-as-code viitor

Un singur punct logic de decizie, apelat de toate căile (UI, API, job, retry, webhook, fallback manual); enforcement înaintea efectului și la nivelul stocării. Politicile versionate sunt artefacte review-uite în Git, fără secrete. Modelul poate propune o modificare, dar nu o poate instala sau relaxa. Cache-ul nu poate prelungi membership, aprobare ori politică revocată.

Intrare tipată obligatorie: `principal_id`, `principal_type`, `tenant_id`, `membership_version`, `action`, `resource_id`, `resource_tenant_id`, `artifact_hash`, `destination`, `integration_id`, `requested_cost`, `currency`, `policy_version`, `approval_id`, `job_id`, `idempotency_key`, `kill_switch_epoch`, `now`. Unele acțiuni de citire nu cer aprobare/buget; profilul acțiunii trebuie să specifice explicit câmpurile neaplicabile. Câmpurile suplimentare, acțiunile și schemele necunoscute sunt respinse. Timestamp-ul, identitatea și versiunea autorității sunt furnizate de server, nu de model.

Ordine logică (tranzacțiile concrete se aleg la implementare):
1. Validează schema, autentificarea, revocarea și membership-ul curent.
2. Verifică aceeași identitate tenant pe resursă, credential, memorie și job; verifică rolul și allowlist-ul uneltei/argumentelor/destinației.
3. Verifică STOP global/tenant/integration și versiunea curentă a politicii. Starea necitibilă înseamnă STOP.
4. Pentru efecte externe, validează grantul/aprobarea exactă, expirarea, revocarea și limitele; rezervă atomic bugetul și dreptul de execuție cu idempotency/fencing.
5. Revalidează imediat înainte de dispatch. Înregistrează decizia și auditul durabil; dacă nu se pot persista, nu emite permis.
6. Emite un permis de unică utilizare, scurt, legat de job/tenant/artefact/destinație și epoch; executorul îl consumă atomic. Nu îl reutilizează la retry. Rezultatul returnează ALLOW/DENY, reason code, versiunea politicii și ID-ul auditului, fără date sensibile.

Nu promitem tranzacție atomică DB + provider. STOP/revocare liniarizate înainte de emiterea permisului blochează acel permis; un request deja în zbor poate avea efect. Permisele vechi sunt invalidate la schimbarea epoch; efectele cu rezultat necunoscut intră în reconciliere, fără retry orb sau eliberare prematură a rezervării. Limita cursei și garanția providerului sunt afișate în starea jobului și testate (T13–T15).

## Aprobări și autorizare permanentă

Acordul utilizatorului din această sesiune autorizează agenții să facă operațiile de dezvoltare necesare și integrarea după verificări/review. Nu mai cerem confirmarea proprietarului pentru acest pas. Nu dezactivăm protecțiile Git și nu fabricăm review-uri. Pentru livrarea documentară 07, utilizatorul a eliminat explicit review-ul Claude prin D07-2. Nu îl mai tratăm drept condiție de închidere și nu îl raportăm ca efectuat. Excepția privește acest pas; politicile de review propuse pentru viitoarele capabilități sunt descrise separat mai jos.

În produs, grantul uman poate fi anticipat: tenantul autorizează explicit un set finit de acțiuni, destinații, interval de timp și plafon; motorul determinist verifică fiecare execuție. Cererea generică de dezvoltare nu devine grant pentru conturile viitorilor clienți. În lipsa grantului, se creează propunere în așteptare, fără publicare, cheltuială sau mesaje externe.

Înregistrare de aprobare: actor autentificat cu drept de aprobare, tenant, intenție, hash și versiune artefact, canal/destinație, integrare/scopes, cost maxim și monedă, plafon cumulat, expirare, utilizări permise, policy version, timestamp, reason, revocation version. Orice schimbare relevantă invalidează aprobarea; draftul editat nu poate folosi aprobarea veche. Granturile generale nu permit granturi mai largi prin delegare. Pentru schimbarea politicilor, privilegii de platformă, scoaterea STOP global și acceptarea riscului critic: operator autorizat + review independent consemnat. Actorul care propune relaxarea nu este singurul ei reviewer.

Aprobările GitHub depind și de identitatea contului/API disponibil; aceeași identitate de cont nu reprezintă două aprobări GitHub independente. Un raport real Claude trebuie să numească SHA-ul revizuit și verdictul. Dacă o protecție tehnică cere un reviewer distinct indisponibil, integrarea rămâne blocată cu dovadă, fără să se inventeze un cont sau review.

## Kill switch și reacție la incident

STOP persistent pe trei niveluri (global, tenant, integrare); nivelul cel mai restrictiv câștigă. Un tenant autorizat poate opri propriul trafic, operatorul poate opri global; agentul poate solicita STOP, niciodată START. STOP nu cere confirmare prealabilă. START este explicit, auditat, verifică remedierea și nu reactivează automat aprobări expirate ori joburi cu rezultat necunoscut. După restore/pierdere store/control plane: STOP implicit până la reconciliere și replay ledger complet.

La incident: oprește efectele afectate, revocă tokenuri/sesiuni/permise, izolează uploadul ori integrarea, păstrează audit redacted cu acces restrâns, identifică tenanturile afectate, reconciliază operațiile în zbor și restaurează din surse verificate. Ownerul incidentului documentează impactul și obligațiile de notificare; nu trimite automat date sau notificări către terți. Secret în Git public: revocare imediată înainte de curățare; ștergerea fișierului nu elimină copiile/clonările.
