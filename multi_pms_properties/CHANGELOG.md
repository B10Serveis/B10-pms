# Registre de canvis de B10 PMS

## 16.0.2.0.0 — 2026-10-06

Primera versió pròpia del fork, posterior a la versió d'origen `16.0.1.0.1`.
Es mantenen el nom tècnic, els identificadors i la llicència AGPL-3.

- Comprovar la coherència entre empresa i propietats també quan el model no
  té camps relacionals amb `check_pms_properties=True`.
- Validar cada registre relacionat per evitar que una propietat compatible
  amagui registres incompatibles en relacions múltiples.
- Delegar els dominis estàndard al comportament original d'Odoo.
- Afegir proves de regressió de creació, escriptura, relacions i dominis.

No hi ha canvis d'esquema ni migració de dades. Les comprovacions més estrictes
poden detectar incoherències preexistents en modificar registres. Cal assajar
l'actualització en una còpia de la base de dades. Després d'actualitzar el codi,
cal reiniciar Odoo i actualitzar el mòdul; s'ha de mantenir
`multi_pms_properties` a `server_wide_modules`, juntament amb els mòduls
habituals (per exemple, `base,web,multi_pms_properties`).
