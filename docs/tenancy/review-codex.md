# Review independent PASUL 11 — Codex

Verdict: **CHANGES_REQUESTED**. Data: 2026-11-07. Reviewer: Codex (familia OpenAI), independent de implementarea Claude Opus 5.5; modelul/efortul exact al acestei sesiuni nu este verificabil. PR #18, **SHA analizat `eaa99e05bf1e5e8387313b25b76dc1c4c4a6eb59`**, bază main `e78ff99`. Acest raport și probele nu schimbă implementarea. Nu integra PR-ul înainte de remediere și re-review pe noul SHA.

## Constatări

### R11-1 — P1 / ridicată: editarea respinsă schimbă conținutul aprobat

Loc: `src/revenuepilot/tenancy.py:247–250`, `TenancyService.update`.
Scenariu reprodus: editorul creează campania r1, alt utilizator o aprobă la versiunea 1. Editorul trimite update cu `title="UNAPPROVED TITLE"` și `body=""`. `_text` pentru body ridică ValueError (HTTP handler îl mapează la 400), dar titlul fusese deja scris în obiect. Citirea ulterioară întoarce noul titlu, `status="approved"`, `version=1`. Aprobarea rămâne asociată unei versiuni al cărei conținut s-a schimbat; încalcă A08/T13 chiar fără efect extern implementat.
Remediere: validează toate câmpurile în variabile temporare înainte de orice mutație; apoi aplică modificarea, incrementarea versiunii și invalidarea aprobării atomic sub lock. Regresie obligatorie: un update invalid după un câmp valid lasă întregul obiect byte-for-byte/semantic neschimbat; un update valid invalidează aprobarea.

### R11-2 — P1 / ridicată: ordine inversă a lockurilor blochează serviciile

Loc: `src/revenuepilot/auth.py:215–217`, în combinație cu `src/revenuepilot/tenancy.py:165–168` și `AuthService.user_exists`.
Login ține `auth._lock` când cheamă `_principal → tenancy.membership`, care cere `tenancy._lock`. Concomitent, `add_member` ține `tenancy._lock` când cheamă `user_exists`, care cere `auth._lock`. Am forțat intercalarea prin Events exact înaintea celor două apeluri: ambele threaduri rămân blocate, iar ambele lockuri sunt deținute. Lockurile sunt globale per serviciu, deci cererile ulterioare pentru toate organizațiile pot rămâne suspendate. ThreadingHTTPServer permite această concurență în utilizare normală.
Remediere: elimină achiziția în ordine inversă (de exemplu construiește principalul după eliberarea lockului auth, păstrând reverificarea membership înainte de operații), documentează ordinea unică pentru apelurile dintre servicii. Regresie deterministă cu bariere și timeout: login concurent cu add_member se termină, cu rezultat permis/refuzat corect; nu doar teste secvențiale.

### R11-3 — P2 / medie: accesul privat refuzat apare numai ca „allow” în audit

Loc: `src/revenuepilot/tenancy.py:155`, `:201–205` (`_find`) și `:225–228` (`get`).
Scenariu reprodus: viewer cere r1 privat al editorului. Primește NotFound, dar singurul eveniment nou în audit este `resource.read / allow`, emis înainte de verificarea vizibilității. `_find` nu înregistrează refuzul. Similar, `last_admin` ridică AccessDenied după un allow fără audit de deny. Contrazice contractul „fiecare decizie allow și deny”, ascunzând probele încercărilor de acces la obiecte private.
Remediere: distinge verificările intermediare de decizia finală; înregistrează rezultatul final pentru vizibilitate, ownership și regulile membership, inclusiv refuzul „negăsit/invizibil” fără divulgarea existenței. Regresie: acces privat sau ID absent → eveniment deny generic, fără conținut, fără allow final fals; operația reușită → allow final.

### R11-4 — P2 / medie: JSON de tip greșit închide conexiunea fără răspuns controlat

Loc: `src/revenuepilot/tenancy.py:211–213` și `src/revenuepilot/app.py:226–231`.
Reproducere pe HTTP real, autentificat ca editor: POST `/api/resources` cu `{"kind":[],"title":"t","body":"b"}`. JSON este valid, dar verificarea `kind not in KINDS` ridică TypeError (`unhashable type: list`), necapturat de handler. Clientul primește RemoteDisconnected în loc de 400. Aceeași categorie afectează `role` la add_member și `user_id` la grant/remove.
Remediere: validare explicită de tip/schema înainte de lookup/set membership și înainte de mutații; răspuns 400 stabil, fără traceback/disconnect. Teste HTTP parametrizate pentru list/dict/null/număr pe fiecare câmp relevant, plus control pozitiv. Nu ascunde generic toate excepțiile ca „invalid_request”.

## Răspunsuri la „Pentru reviewer”

1. `_require`: accesul la resurse și schimbările membership țin același RLock; versiunea membership este recitită sub acel lock. Contextul vechi după downgrade este respins (probă independentă PASS). Nu am găsit o fereastră între `_require` și operație pentru metodele publice actuale. Problema de concurență găsită este R11-2 la interacțiunea cu auth.
2. `switch_organization` versus `remove_member`: am injectat eliminarea imediat după verificarea membership și înaintea rotirii. Switch poate întoarce o sesiune cu tenant None; următoarea operație protejată este refuzată. Nu am reprodus acces tenant după revocare. Ar fi util un răspuns explicit de switch refuzat în această cursă, dar fără blocaj de securitate demonstrat.
3. Login și organizație cerută: parola este verificată înainte de alegerea organizației. 403 pentru o organizație nepermisă după parolă corectă nu divulgă parola unui atacator care nu o știe; nu este constatare blocantă. Testele existente verifică alegerea explicită și refuzul organizației străine.
4. Exportul adminului fără obiectele private ale altora este **acceptat**: urmează regula de vizibilitate și nu transformă rolul admin în superuser de conținut. Probă independentă PASS. Un eventual export de conformitate cere capabilitate separată, nu extindere tacită aici.
5. Granturile emise înainte de retrogradarea proprietarului persistă: **acceptabil pentru modelul actual** de grant persistent al resursei; proprietarul retrogradat nu mai poate emite granturi/update-uri, iar eliminarea beneficiarului retrage accesul. Probă independentă PASS. Documentați explicit că downgrade nu revocă granturile deja emise; un mecanism de revocare individuală/lifecycle este de planificat, fără a susține că există acum.
6. Auditul este o listă nelimitată, confirmat prin inspecția `_log`; fiecare citire/denegare adaugă un obiect, fără plafon sau retenție. **C11-1, risc mediu rezidual**, declarat în limitele pasului in-memory; nu am provocat OOM. Înainte de expunere reală: limită configurată, comportament la saturare, rate-limit și audit durabil/retentie; nu se poate afirma disponibilitate robustă în prezent. Separat de lipsa evenimentelor deny (R11-3), care necesită remediere acum.

## Dovezi efective

Pe Python 3.12.14:
- `python3 -B -I -m unittest discover -s tests -v`: **34/34 PASS**, 21.536 s. Aceste teste nu detectează R11-1..4.
- `python3 -B -I docs/tenancy/review-probes.py`: **4 defecte reproduse**, inclusiv disconnect HTTP și deadlock cu intercalare deterministă; controale pentru context învechit/export/grant/switch-revocare PASS. Scriptul afirmă comportamentul defect al SHA-ului revizuit; NU este suită de acceptare și trebuie transformat în teste de regresie după remediere.
- `python3 -B -I scripts/build_skeleton.py`: PASS, zipapp 14511 bytes.
- `python3 -B -I docs/architecture/check_contract.py`: PASS, graf/control pozitiv și zece mutații; validator conceptual, nu dovadă de izolare runtime.
- `python3 -B -I scripts/verify_docs.py`: PASS, 14 fișiere. Legăturile noului raport nu pretind fișiere inexistente.
- `(cd docs/canonical && sha256sum -c SHA256SUMS)`: 4/4 PASS.
- `git diff --check origin/main...HEAD`: PASS.

CI remote, DB/RLS/cache/workeri, audit persistent, browser și Python 3.13 în această sesiune: NOT_RUN. Nicio cheltuială externă nouă, nicio schimbare în codul produsului sau în fabrica-autonoma. Starea persistentă devine CHANGES_REQUESTED; Claude primește R11-1..4, remediază și solicită re-review pe noul SHA. STOP înainte de 12.

## Publicare GitHub

Raport/probe/index publicate pe branchul PR #18 în `5f00836`. GitHub a refuzat evenimentul formal REQUEST_CHANGES pe SHA-ul analizat cu HTTP 422: `Review Can not request changes on your own pull request` (aceeași identitate GitHub pentru autor și reviewer). Verdictul independent Codex este publicat ca un comentariu pe PR și în acest raport; nu se pretinde o aprobare sau un review formal GitHub acceptat. PR-ul rămâne deschis, fără merge.


---

# Re-review independent PASUL 11 — Codex (a doua rundă)

**Verdict: APPROVED** pentru remedierile R11-1..R11-4, cu limitele de mai jos. Commit revizuit: `d0c078dd972a9261225ba66d05eebc00d2540c3a` (HEAD verificat egal cu `origin/step-11/tenancy` înainte de apel). Data: 2026-11-07.

**Cum a fost produs acest review (transparență):** a fost pornit de Claude Sonnet 5.5 din containerul sesiunii Claude, folosind Codex CLI 0.167.0 logat cu abonamentul ChatGPT Plus al proprietarului, model `gpt-6-astra`, efort `medium`, `--sandbox read-only --ephemeral`. Independența constă în modelul diferit (familia OpenAI); orchestratorul și autorul pachetului de intrare este Claude, deci Codex a văzut materialul ales de Claude (constatările sale originale, documentul de remediere și diff-ul `eaa99e0..d0c078d`) și nu a explorat liber repository-ul. Review-ul nu este un review formal GitHub (aceeași identitate de cont pentru autor și reviewer).

**Limită declarată de Codex:** sandbox-ul `read-only` interzice crearea de socketuri, deci 18 din cele 40 de teste (cele HTTP) au dat `PermissionError`; Codex raportează 22 PASS / 18 ERROR și **nu confirmă „40 PASS”**. Pentru R11-4, partea HTTP nu a fost executată de Codex. Cele 40 de teste au fost rulate de Claude (autor) local, fără sandbox: 40 PASS pe Python 3.12 și 3.13 (vezi remediation-r11.md); aceasta este verificare a autorului, nu a reviewerului. Codex nu a verificat restul repository-ului, CI, concurența exhaustivă sau defecte preexistente din afara diff-ului. Observație Codex: `_decision` nu face rollback pentru excepții interne neașteptate (neblocant; operațiile validează înainte de mutație).

## Promptul exact trimis lui Codex

```text
Ești reviewer independent (familia OpenAI) pentru PASUL 11 (clasă H, multi-tenant/RBAC). Citește DOAR fișierul /tmp/claude-0/r11-bundle.md (constatările tale originale R11-1..R11-4, documentul de remediere al implementatorului Claude și diff-ul eaa99e0..d0c078d). Directorul curent este checkout-ul commitului d0c078d.
Sarcină strict limitată: (1) pentru fiecare R11-1..4 decide dacă remedierea este corectă și completă; (2) caută regresii sau defecte noi introduse DE ACEST DIFF (în special tenancy.py: _decision, update, add_member; auth.py: ordinea lock-urilor, switch_organization; app.py: plasa 500); (3) rulează doar `python3 -B -I -m unittest discover -s tests`. Nu re-citi tot repo-ul, nu modifica fișiere.
Răspuns: verdict final APPROVED sau CHANGES_REQUESTED, apoi pentru fiecare constatare: ID, severitate, locație, scenariu reproductibil, remediere. Dacă APPROVED, spune explicit ce ai verificat și ce NU ai verificat.
```
(Pachetul `/tmp/claude-0/r11-bundle.md` = secțiunile R11-1..4 din acest raport, `docs/tenancy/remediation-r11.md` și `git diff eaa99e0..d0c078d -- src tests`, conținutul exact reconstruibil din Git.)

## Răspunsul Codex (integral)

**APPROVED** — pentru remedierile R11-1..R11-4 și diff-ul furnizat. Nu am identificat un defect nou blocant demonstrabil în acest diff. Validarea HTTP locală rămâne incompletă din cauza sandboxului.

| ID / severitate inițială | Locație | Scenariu verificat | Evaluarea remedierii |
|---|---|---|---|
| **R11-1 / P1** | `tenancy.py`, `update` | Resursă aprobată; update cu titlu valid și corp invalid. | **Corectă și completă pentru constatare.** Toate câmpurile sunt validate înaintea mutației, sub același lock. Respingerea păstrează obiectul; update-ul valid incrementează versiunea și invalidează aprobarea. Testul de regresie trece. |
| **R11-2 / P1** | `auth.py`, `login`; `tenancy.py`, `add_member` | Login concurent cu adăugarea unui membru, în intercalarea care producea deadlock. | **Corectă și completă pentru constatare.** Apelurile între servicii implicate sunt scoase din lockurile proprii; autorizarea în `add_member` se reverifică sub lockul tenancy. Ambele teste de lockuri, inclusiv intercalarea deterministă, trec. |
| **R11-3 / P2** | `tenancy.py`, `_decision` și operațiile migrate | Citire privată/ID absent, modificare de către alt proprietar, eliminarea ultimului administrator. | **Corectă și completă pentru constatare.** Refuzurile așteptate produc decizia finală corespunzătoare; `allow` apare după reușită. Absent și invizibil au același cod. Testul de regresie trece. |
| **R11-4 / P2** | `tenancy.py`, validările de intrare; `app.py`, handlerul de excepții | Tipuri JSON necorespunzătoare pentru câmpurile vizate. | **Corectă și completă pentru defectul raportat, prin inspecție și testele de serviciu.** Validările evită lookupurile cu tipuri incompatibile. Plasa generică răspunde cu `500 internal_error`, fără a reclasifica defectele interne drept 400. Testul HTTP nu a putut executa cererile. |

Am verificat și modificările din `switch_organization`: construirea principalului rămâne în afara lockului auth, iar lipsa membershipului constatată ulterior produce refuz explicit. `_decision` serializează operația și auditarea rezultatului; nu reprezintă însă un mecanism de rollback pentru excepții interne neașteptate.

Am rulat exclusiv comanda solicitată:

```text
python3 -B -I -m unittest discover -s tests
40 teste: 22 reușite, 18 erori; exit code 1.
```

Toate cele 18 erori provin din interdicția de creare a socketurilor: `PermissionError: [Errno 1] Operation not permitted`. Prin urmare, **nu confirm „40 PASS”**.

Am citit doar bundle-ul indicat și nu am modificat fișiere. Nu am verificat independent restul repository-ului, concordanța bundle–checkout, CI, HTTP funcțional, concurența exhaustivă sau defectele preexistente din afara diff-ului.
