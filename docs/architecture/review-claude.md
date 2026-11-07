# Review independent PASUL 04 — Claude

Reviewer: Claude Opus 5.5 (selectat de utilizator prin `/model`; efort neexpus). Familie opusă autorului (Codex).
Data: 2026-11-07. Commit examinat: `fd2ebbe7480f4022f3a4e35d28edf38d6cf43265` (HEAD PR #6).
Fișiere examinate integral: `docs/architecture/README.md`, `handoff.md`, `test-plan.md`, `dependencies.json`, `check_contract.py`, `evidence.txt`.

**Verdict: CHANGES_REQUESTED.** Arhitectura este solidă în esență; două lipsuri de fond (R04-1, R04-2) trebuie rezolvate înainte de DONE. Restul sunt corecții minore.

## Verificări rulate de reviewer (în acest mediu)

| Verificare | Rezultat |
|---|---|
| `python3 -I docs/architecture/check_contract.py` | PASS: graf + 7 mutații respinse (reprodus identic cu `evidence.txt`) |
| `sha256sum -c docs/canonical/SHA256SUMS` | PASS, 4/4 |
| `git diff --check` față de baza PR | PASS; `docs/canonical` nemodificat (0 linii diff) |
| Mutații suplimentare ale reviewerului pe validator | 3 grafuri invalide **acceptate** (vezi R04-3) |
| Teste de runtime, DB, worker, tenant | NOT_RUN (nu există cod de produs) |

## Ce este corect și trebuie păstrat

- Monolit modular cu porturi; worker extras doar la măsurători; microservicii amânate. Corespunde Meta §7.2 și §11.3.
- Outbox în aceeași tranzacție, lease + fencing token, at-least-once explicit, `UNKNOWN_OUTCOME` + reconciliere, fără promisiune exactly-once pentru efecte externe.
- Rezervare atomică de buget care include rezervările; aprobare legată de hash-ul artefactului și revalidare înainte de efect.
- Tenant din sesiune server-side, chei compuse `(tenant_id, id)`, RLS doar ca apărare suplimentară, cu avertismentul corect despre pooling.
- Adaptere dezactivate care resping explicit, nu simulează succes. Costuri marcate UNKNOWN, nu inventate.

## Constatări

| ID | Severitate | Secțiune | Problemă și scenariu | Remediere cerută |
|---|---|---|---|---|
| R04-1 | MEDIUM | README §5 (ultimul punct), test-plan A10 | „La restore se reaplică tombstones” nu spune **unde** trăiesc tombstones. Scenariu: backup luat la T0, ștergere tenant/DSAR la T1, restore din backupul T0. Dacă registrul de ștergeri e în aceeași DB, restore-ul îl pierde și datele șterse revin (încălcare GDPR, Meta §8.4/§10.5). | Registru de ștergeri (deletion ledger) stocat și backup-uit **separat** de DB-ul restaurat, cu retenție ≥ retenția backupurilor; procedura de restore îl aplică înainte de reactivarea accesului. A10 trebuie să restaureze explicit un backup luat **înainte** de ștergere. |
| R04-2 | MEDIUM | README §2, §6, §8 | Lipsesc componentele operaționale obligatorii din Meta §7.5 și §11.2: kill switch (global și per tenant/integrare), limită de concurență a workerilor, backpressure, degradare controlată în mod manual. De asemenea, constrângerea de resurse (un singur host mic, servicii gratuite) nu apare: variantele serverless/DB managed sunt listate fără a spune că probabil încalcă constrângerea „doar gratuit”. | Adaugă un ADR scurt: țintă inițială = un singur host (app + worker + PostgreSQL în același VPS), buget RAM/CPU de măsurat, concurență configurabilă (implicit mică), kill switch persistent verificat de executor înainte de fiecare efect extern, mod manual ca fallback. Marchează opțiunile plătite ca „necesită aprobare, nu țintă”. Adaugă test de kill switch în test-plan. |
| R04-3 | LOW | `check_contract.py` | Validatorul acceptă `adapters → application`, `adapters → executor`, `adapters → policy` (verificat de reviewer). Un adapter care importă policy/application inversează dependențele și poate ocoli politica. Mutațiile existente nu acoperă direcția adapter → nucleu. | Limitează `adapters` la `{ports, domain}` și adaugă mutația negativă corespunzătoare. |
| R04-4 | LOW | README l.6–7, l.28; `evidence.txt` ultima linie | Text contradictoriu: antetul spune 03 DONE, dar l.6–7 „dependența deschisă / Nu declară închise 02/03”, l.28 „repo privat”, `evidence.txt` „step 03 not DONE”. Nota „Actualizare” de la final nu repară corpul; un model nou poate citi greșit starea (Meta §17.3). | Corectează corpul cu o notă de corecție inline (păstrând istoria în SESSION_LOG), regenerează `evidence.txt`. |
| R04-5 | INFO | `check_contract.py` | Unele verificări sunt egalități fixe (`graph['ui'] == ['application']`), deci validatorul confirmă acest graf, nu reguli generale. Acceptabil la nivel conceptual; la PASUL 08 trebuie înlocuit cu verificare reală a importurilor (A01). | Fără acțiune acum. |

## Răspunsuri la întrebările din test-plan

1. Ocolire tenant: nicio cale găsită în design, cu excepția R04-1 (restore). Cache și search sunt menționate; trebuie testate concret la 11–12.
2. Rezultate ambigue și revocare: tratate corect (reconciliere, fără retrimitere oarbă, revalidare înainte de efect).
3. Monolit + PostgreSQL: justificate pentru volum mic și un singur host. Ipoteza care le-ar invalida: host fără proces persistent (doar serverless) — atunci outbox/worker trebuie regândit. Asta întărește R04-2.
4. Test negativ absent: kill switch (R04-2), restore din backup anterior ștergerii (R04-1), adapter care importă nucleu (R04-3).
5. Costuri: corect etichetate UNKNOWN; migrare reversibilă cu limite explicite.
6. Separare audit/PII și invalidare memorie: implementabile; depind de R04-1 pentru restore.

## Condiție de DONE

R04-1 și R04-2 rezolvate de autor (sau respinse argumentat), R04-3 și R04-4 corectate, apoi re-review pe noul SHA. Până atunci PASUL 04: CHANGES_REQUESTED.


---

# Re-review PASUL 04 — Claude

Reviewer: Claude Opus 5.5. Data: 2026-11-07. Commit examinat: `5dc5e2708b24ba9802283b6c312c8d05063d2ed4` (remedierea Codex, `remediation-r04.md`).

**Verdict: APPROVED.** Toate constatările R04-1..R04-4 sunt rezolvate; R04-5 rămâne corect amânat la PASUL 08 (A01).

| ID | Rezolvare | Verificat de reviewer |
|---|---|---|
| R04-1 | Ledger de ștergeri separat de DB și de snapshoturile ei, copie într-un alt domeniu de pierdere, retenție ≥ backupuri + fereastra de replay, doar ID-uri opace; intenție durabilă înainte de finalizarea DSAR; restore izolat, fail closed dacă ledgerul lipsește/e incomplet. A10 restaurează explicit un backup anterior ștergerii. | Citit integral §5 și A10. Corect. Limită acceptată: copia independentă poate cere un serviciu încă neales; documentul blochează restore-ul în lipsa ei, nu presupune unul gratuit. |
| R04-2 | ADR-04-4: un singur host, fără VPS presupus; buget RAM/CPU de măsurat; concurență implicită 1 prin lease în DB; coadă finită cu DEFERRED/429; kill switch persistent global/tenant/integrare, verificat înainte de fiecare efect extern, fail closed, STOP implicit după restore; mod manual fără retry dublu. Opțiunile plătite cer aprobare. Teste A15–A17. | Citit integral §7a și A15–A17. Corect și proporționat. |
| R04-3 | `adapters` limitat la `{ports, domain}`; 3 mutații noi + control pozitiv. | `python3 -B -I check_contract.py`: PASS, 10 mutații respinse. Mutațiile mele reluate: `application`, `executor`, `policy`, `ui` respinse; `['domain']` acceptat (corect). |
| R04-4 | Antet și §1 corectate; `evidence.txt` regenerat. | Corect. |

Alte verificări: SHA-256 canonice OK; `git diff --check` față de `main` OK; `review-claude.md` original neschimbat; bytecode-ul `__pycache__` (introdus din greșeală de commitul de review `c377257`) eliminat de autor, cu `.gitignore`.

Corecție mecanică făcută de reviewer în același commit cu acest re-review: o linie goală în `test-plan.md` despărțea rândurile A15–A17 de tabel (nu se randau ca tabel). Doar linia goală a fost ștearsă; conținutul nu s-a schimbat.

NOT_RUN: orice test de runtime (restore, kill switch, worker, tenant, CI). Acestea sunt contracte pentru pașii 08–77, nu dovezi.
