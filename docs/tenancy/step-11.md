# PASUL 11 — multi-tenant, RBAC și izolare

Autor: Claude Opus 5.5 (selectat de utilizator; recomandat de plan pentru clasa H). Data: 2026-11-07. Bază: `e78ff99` (`main`, 10 DONE). Branch `step-11/tenancy`.
**Status: REVIEW_PENDING.** Clasa H cere review independent din familia opusă (Codex) înainte de DONE și merge (D10-2).

Dependență conform planului canonic: doar 10. Backlog-ul de la pasul 06 afirma greșit „10 și 12”; corectat aici și în `PROGRESS.md`.

## Model

| Concept | Implementare (`src/revenuepilot/tenancy.py`) |
|---|---|
| Utilizator | identitate globală în `auth.py`; nu mai are tenant/rol propriu (schimbare față de 10) |
| Organizație | `create_organization` doar la bootstrap de platformă (nu prin HTTP); fondatorul devine admin |
| Membership | `(org_id, user_id) → rol + versiune`; versiunea crește la orice schimbare sau eliminare |
| Roluri | conjunctive, fără moștenire: viewer = citire; editor = citire, creare, editare/ștergere/partajare **proprii**; approver = citire, aprobare (nu pe propriile obiecte); admin = citire, export, administrare membri |
| Resurse | cheie `(tenant_id, local_id)`, ID-uri locale per tenant (`r1` există în fiecare tenant); tipuri brief/campaign/memory; vizibilitate tenant sau private + granturi de citire |
| Context | `AccessContext` construit pe server din sesiune + membership curent la **fiecare** cerere; clientul nu poate trimite tenantul |

## Căi de acces acoperite (inclusiv indirecte)
Citire după ID, listare, căutare, memorie (același drum filtrat), creare cu `parent_id`, editare, ștergere, grant, aprobare, export, administrare membri, schimbarea organizației active, login cu organizație cerută. Fiecare decizie (allow și deny) este auditată fără conținut. „Negăsit” și „invizibil” dau același răspuns (404), deci ID-urile altor tenanturi nu pot fi enumerate.

Reguli suplimentare: ultimul admin nu poate fi eliminat sau retrogradat; granturile doar către membri ai aceluiași tenant; eliminarea unui membru îi retrage granturile; ștergerea cu copii este refuzată; o editare anulează aprobarea (aprobarea e legată de versiune, A08); schimbarea organizației rotește tokenul de sesiune; un utilizator cu mai multe organizații trebuie să aleagă explicit.

## Dovezi rulate efectiv
- `python3 -B -I -m unittest discover -s tests`: **34 teste PASS** pe Python 3.12.3 și 3.13.18 (16 de autentificare din pasul 10 adaptate la noul model, 1 smoke, 17 noi în `tests/test_tenancy.py`).
- 3 organizații sintetice din 3 industrii (agenție, clinică, brutărie), fiecare cu admin, 2 editori, approver, viewer; un utilizator membru în 2 organizații cu roluri diferite.
- **Teste de mutație** (cod stricat intenționat, apoi restaurat): căutare în toate tenanturile → 4 eșecuri; membership vechi acceptat → 1; grant către alt tenant → 1; tenant din sesiune fără recitirea membership-ului → 2; căutarea ignoră obiectele private → inițial **0 eșecuri (lacună)**, test adăugat, acum 1. Concluzie: testele detectează aceste scurgeri; nu dovedește absența altora.
- Rulare manuală pe procesul real: login dev → creare resursă 201 → căutare 200 → export ca editor 403.
- Build zipapp, hash-uri canonice, linkuri, contract arhitectură: PASS.

## Limite
- **In-memory**: fără DB, deci fără FK compuse, RLS, reutilizare de conexiuni (A03/T10 la nivel de stocare rămân pentru 12). Regulile de aici trebuie păstrate de stratul de persistență.
- Nu există cache, joburi, cozi sau index vectorial; T10 pentru acestea nu e testat pentru că nu există încă.
- Fără operator de platformă, acces de suport, invitații, UI de administrare. Auditul e în memorie și nu are retenție.
- Exportul adminului include doar ce adminul poate citi (nu obiectele private ale altora). E o alegere de confidențialitate, de confirmat de reviewer.
- Utilizator dev: implicit editor într-o organizație sintetică, cu un admin de bootstrap a cărui parolă aleatoare e aruncată (`REVENUEPILOT_DEV_ROLE` pentru alt rol).
- CI remote NOT_RUN (Actions dezactivat pe cont). Cost: zero.

## Pentru reviewer (Codex)
Examinează SHA-ul din PR. Atacă: (1) `_require` — fereastra dintre construirea contextului și operație; (2) `switch_organization` — cursa cu `remove_member`; (3) `login` cu `organization_id` după parola corectă (dezvăluie că parola e corectă unui deținător al parolei); (4) exportul fără obiecte private; (5) granturile rămase după retrogradarea unui proprietar; (6) audit în memorie nelimitat (risc de memorie). Pentru fiecare constatare: ID, severitate, scenariu, remediere.
