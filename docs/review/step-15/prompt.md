Ești revizor independent de securitate/arhitectură (clasa H, PASUL 15). Nu ai scris acest cod.
Fișierul `bundle.txt` din directorul curent conține: sursele `src/revenuepilot/*.py`, testele `tests/*.py`,
registrul de amenințări, politicile de acces și DECISIONS.md. Citește-le integral.

Sarcină: caută defecte REALE, demonstrabile, în ordinea gravității, în aceste arii:
1. izolare între tenanți (auth, tenancy, storage), IDOR, escaladare de rol, sesiuni/CSRF/cookie;
2. integritate/redactare evenimente (observability), scurgeri de date sensibile;
3. buget/kill switch/permit unic (guardrails): TOCTOU, dublă cheltuire, bypass al `Dispatcher.run`;
4. concurență (lock ordering, deadlock, race), validarea intrărilor, erori care deschid accesul (fail-open);
5. acoperire: amenințări T01–T18 fără test sau cu test care nu ar eșua pe cod stricat.

Reguli: pentru fiecare constatare dă fișier:linie, scenariu concret de exploatare, severitate
(CRITIC/RIDICAT/MEDIU/SCĂZUT), remediere minimă. Nu inventa: dacă nu poți demonstra, marchează „IPOTEZĂ".
Nu raporta stil. Încheie cu EXACT una din liniile: `VERDICT: APPROVED` sau `VERDICT: CHANGES_REQUIRED`
(APPROVED doar dacă nu există constatări CRITIC/RIDICAT nerezolvate).
Răspunde în română, concis.
