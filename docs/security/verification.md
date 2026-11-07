# Verificări PASUL 07

## Scope și acoperire

| Cerință canonică | Acoperire |
|---|---|
| adversari, OAuth | README; T01–T02 |
| SSRF, deschidere linkuri | T03, T06 |
| prompt injection, upload neîncrezut | T04–T05 |
| Git, supply chain | T07–T08 |
| privilegii agent, leakage cross-tenant | T09–T11 |
| policy-as-code, human approval | access-policies; T09, T13 |
| kill switch, deny by default | access-policies; T15, T18 |
| severitate, owner, mitigare, aprobare, caz negativ | fiecare T01–T18 |
| retry/buget, ștergere/restore, memorie | T12, T14, T16–T18 |

## Probe de executat pentru livrarea documentară

Comenzi reproductibile din rădăcina repository-ului:

```sh
(cd docs/canonical && sha256sum -c SHA256SUMS)
python3 -B -I docs/architecture/check_contract.py
python3 -B -I scripts/verify_docs.py
git diff --check
```

Workflowul existent verifică aceleași contracte și include acum linkurile documentelor de securitate. Aceste verificări pot detecta modificări de surse, încălcări ale grafului conceptual și linkuri rupte; **nu certifică mitigările de securitate sau accesul runtime**. Rezultatele efectiv observate și SHA-urile/run-urile se adaugă în jurnalul de sesiuni și handoff după execuție.

Review documentar autor: verifică toate cele 18 intrări, fiecare cu owner/approver, severitate, mitigare, negativ+oracle, control pozitiv și gate de implementare; compară frontierele și politicile cu arhitectura aprobată. Review-ul autorului nu este review independent.

## Rezultate locale observate — 2026-11-07

Cele patru comenzi de mai sus: PASS (4 hashuri; graf valid, control pozitiv și 10 mutații respinse; linkuri în 12 fișiere; whitespace). Inspecția documentară a autorului a parcurs T01–T18 pentru domeniile canonice și concordanța cu arhitectura. O verificare Python suplimentară a confirmat identificatorii consecutivi, toate cele șase câmpuri obligatorii ale fiecărei intrări și păstrarea byte-for-byte a prefixului jurnalelor față de `63ac761`; `git diff 63ac761 -- docs/canonical` este gol. Aceasta validează structura și conservarea istoricului, nu conținutul securității. Review independent: NOT_RUN.

## Testele viitoare

T01–T18: NOT_RUN pe produs, fiindcă nu există runtime. Se preiau ca teste de acceptare când capabilitatea este implementată; niciuna nu se activează doar pe baza acestui document. Fixture comun: tenanturi A/B, date sintetice, transport/provider simulat, ceas controlabil, observare a apelurilor externe, audit și starea persistentă. Pentru T10/T13–T16 se testează și concurența, crash/restart și interleaving-ul precizat; documentarea unui test nu echivalează cu executarea lui.

Completarea viitoare cere comanda, SHA-ul, rezultatul real și dovada oracle-ului, inclusiv controlul pozitiv. Testele live necesită mediu și credențiale autorizate; nu există în această sesiune. Fără cost nou, fără scanarea domeniilor/rețelelor externe și fără trimitere de mesaje. Aprobarea/review-ul independent pentru 07 rămâne NOT_RUN până la raportul real Claude.
