# Registre de canvis de PMS

## 16.0.5.1.1 — 2026-10-09

- Corregir la inicialització catalana de Moment perquè els temps relatius
  del xat de les reserves no fallin amb l'error `humanize` quan la
  configuració catalana es crea abans de carregar el fitxer d'idioma.
  Conservar la correcció d'Odoo per analitzar els noms dels mesos.

## 16.0.5.1.0 — 2026-10-08

Millores de filtratge i llegibilitat de la vista timeline de reserves.

- Activar el panell lateral de filtres a la timeline, mantenint-lo també
  a les vistes de llista i kanban.
- Afegir «No cancel·lats» activat per defecte a l'acció de reserves.
  Es pot desactivar per consultar també les reserves cancel·lades.
  L'accés a «Habitacions cancel·lades» des del foli conserva la consulta
  específica de les cancel·lades.
- Filtrar el tipus d'habitació del panell per les habitacions realment
  assignades a les nits de la reserva. Es poden seleccionar diversos tipus.
  Una reserva amb canvi d'habitació apareix en els tipus que té assignats;
  el tipus venut a la reserva es conserva com a dada independent.
- Afegir colors a les barres segons l'estat de la reserva i una llegenda
  amb els noms dels estats traduïts. Els colors representen l'estat de la
  reserva, no l'estat de neteja o manteniment de l'habitació.
- Utilitzar una etiqueta específica per a l'estat de la reserva, traduïda
  com a «Estat» en català i «Estado» en castellà.
- Corregir la clau del bucle Owl del panell de `web_responsive` i la
  referència a `web_timeline.TimelineView` en la plantilla de la llegenda,
  per permetre generar els recursos de la interfície.

### Actualització

El mòdul declara la dependència de `web_responsive`, a més de `web_timeline`.
Cal disposar dels dos mòduls als addons, reiniciar Odoo, actualitzar `pms`
i recarregar el navegador perquè carregui els recursos nous.

L'actualització crea el camp calculat i emmagatzemat
`assigned_room_type_ids`, amb la seva taula de relació, i calcula els tipus
d'habitació assignats de les reserves existents. No requereix un script de
migració específic. Com que afecta l'esquema i dades calculades, s'ha
d'assajar en una còpia de la base de dades abans d'aplicar-la a producció,
segons el criteri del projecte.

Les instruccions d'ús són a [readme/USAGE.rst](readme/USAGE.rst).
