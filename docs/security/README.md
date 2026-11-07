# PASUL 07 — model de amenințări și acces

Autor: Codex, 2026-11-07; modelul și efortul runtime nu sunt verificabile în această sesiune. Recomandarea canonică: GPT-6 Astra / High; reviewer recomandat inițial: Claude Opus 5.5 / High; cerință exceptată ulterior de utilizator pentru 07 (D07-2). Bază: `63ac761c0fb972d10592bdd38a3335c23a4312e8` pe `main`, cu pașii 00–06 integrați. Dependența 04 este DONE, cu review Claude APPROVED pe `5dc5e27`.

**Scope:** contract de securitate pentru implementările viitoare, fără module de produs, host, DB, API comerciale sau teste de penetrare. Stare: BLOCKED (CI). Review-ul independent pentru 07 nu mai este cerut, conform D07-2; nu a fost efectuat. Controalele runtime de mai jos sunt PROPUSE, nu instalate. Acordul de dezvoltare al proprietarului este consemnat în D07-1; nu este necesară o nouă confirmare pentru publicarea acestui pas.

- [Registrul amenințărilor](threat-register.md): severitate, responsabili, mitigări, aprobări și oracole de test.
- [Politici de acces](access-policies.md): deny by default, matrice de privilegii, aprobări, kill switch și contract policy-as-code.
- [Verificări și dovezi](verification.md): probe documentare efective separate de scenarii runtime NOT_RUN.
- [Predare](handoff.md): blocajul CI și punctul exact de reluare.

## Active, adversari și frontiere

Active: identități/membership, date și memorie tenant, tokenuri OAuth, conținut/artefacte aprobate, bugete, joburi/outbox, registrul ștergerilor, politici/audit și integritatea Git/CI. Repository-ul este public: numai date sintetice în exemple și teste.

Adversari: vizitator anonim; tenant rău intenționat ori cont furat; publisher/site/document extern malițios; provider compromis; contributor sau dependență compromisă; operator intern abuziv; agent/model indus în eroare. Erorile operatorului, retry-urile și restaurările sunt tratate ca surse de incidente chiar fără atacator.

| Frontieră | Intrare neîncrezută | Decizie obligatorie |
|---|---|---|
| B1 client → API/control | sesiune, ID tenant/obiect, request | autentificare, membership curent, autorizare pe obiect; CSRF/origin pentru sesiuni cookie |
| B2 control/executor → DB/queue/cache | job, query, context tenant | context derivat server-side; chei compuse, filtrare și RLS, fencing și lease |
| B3 internet/provider → import/model | URL, redirect, fișier, webhook, text | egress verificat, limite, verificare origine, carantină; conținutul nu devine instrucțiune de sistem |
| B4 agent → unelte/executor/provider | intenție, argumente, conținut generat | allowlist exactă, policy engine determinist, aprobare și buget legate de artefact |
| B5 contributor → Git/CI/release | commit, workflow, pachet | PR, review cerut, pin/lock, CI read-only; fără secrete pentru cod neîncrezut |
| B6 backup/operator → stare restaurată | snapshot vechi, ledger, politici | STOP implicit; replay ledger independent, verificări înainte de repornire |

Agentul nu primește credențiale DB, Git admin sau token OAuth brut. Accesul runtime la repository nu este necesar și rămâne interzis implicit. Uneltele de dezvoltare din această sesiune sunt un context separat de viitorul agent al produsului.

## Severitate și asumarea riscului

Critică: control al infrastructurii, execuție arbitrară ori expunere largă între tenanturi. Ridicată: compromitere cont/token, efect extern neautorizat, pierdere/reapariție de date sau cost necontrolat. Medie: incident limitat de conținut ori indisponibilitate recuperabilă. Probabilitățile nu sunt măsurate; severitățile sunt evaluări de proiectare, nu rezultate de scanare.

Rolurile owner din registru sunt responsabilități propuse, nu persoane deja numite. Implementatorul viitor preia explicit fiecare ID în jurnal, iar reviewerul verifică testele. Fără owner concret, mitigare și probe, funcția afectată rămâne dezactivată înainte de lansare. Riscul rezidual se acceptă explicit de responsabilul de securitate și proprietarul produsului; nicio acceptare nu poate anula segregarea tenanturilor sau autoriza datele altui client.

## Baseline, cost și memorie

Față de [baseline 06](../planning/baseline-kpi.md), detaliem R02/R03/R06/R07/R08/R09 în amenințări verificabile; nu declarăm reducere măsurată a riscului ori KPI comercial îmbunătățit. CI validează doar documentația. Hostingul/API-urile rămân neconfigurate, cost comercial nou activat: zero; consumul Actions nu este convertit în cost monetar fără date de facturare.

Memoria persistentă de dezvoltare este Git (index, sesiuni, decizii). Viitoarea memorie a produsului va avea proveniență, tenant, TTL și ștergere; intrările sugerate de model nu devin politici sau permisiuni. Lecția pentru implementare: orice oracle negativ cere și control pozitiv, altfel un sistem care respinge tot poate părea sigur. STOP înainte de 08.
