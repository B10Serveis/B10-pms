# Revisió general — 2026-10-06

Revisió del codi del mòdul, de la integració amb els camps relacionals d'Odoo 16,
dels punts d'ús a `pms`, dels tests i de les instruccions d'instal·lació.

## Errors corregits

1. La comprovació retornava immediatament si no trobava relacions marcades.
   Això permetia crear o modificar registres amb una empresa diferent de la
   de la propietat. Ara es comprova l'empresa independentment de les relacions.
2. Les propietats dels registres relacionats s'agregaven abans de validar.
   En many2many, un registre compatible podia amagar-ne un d'incompatible.
   Ara es valida cada registre individualment, mantenint les regles de
   solapament i de subconjunt segons el tipus de relació.
3. La comprovació d'empresa indexava una llista d'identificadors que podia ser
   buida si les propietats no tenien empresa. Es comparen recordsets i es
   retorna un error de coherència en aquest cas.

## Manteniment

- El pedaç global dels dominis conserva el comportament estàndard delegant al
  mètode original d'Odoo, en comptes de duplicar-ne el codi.
- Els models sense validació automàtica eviten el recorregut dels camps en
  cada `write`, ja que el mòdul hereta el model base de tot Odoo.
- Les instruccions de càrrega conserven `base,web` a `server_wide_modules`.
- S'inicia la versió del fork a `16.0.2.0.0`, amb registre de canvis propi.

## Validació i abast

Nou proves de regressió executades amb Odoo 16 i PostgreSQL 15 en una base
de dades temporal: coherència d'empresa sense relacions marcades, múltiples
empreses, many2one, one2many, many2many, registres compartits, canvis de
propietat i dominis automàtics, explícits i dinàmics. Resultat: zero errors
i zero proves fallides.

La validació cobreix el mòdul tècnic amb models de prova aïllats. No s'ha
actualitzat ni auditat la base de dades de producció, ni executat tota la
suite de `pms`.

La validació automàtica s'aplica als models amb
`_check_pms_properties_auto=True` i a les relacions amb
`check_pms_properties=True`. No és un mecanisme de permisos: les regles
d'accés i de registre dels mòduls funcionals continuen sent necessàries.
Els canvis en un registre relacionat no revisen automàticament totes les
referències entrants si no hi ha una relació inversa marcada. La comprovació
tampoc audita retrospectivament tots els registres existents.

Cal conservar la càrrega global del mòdul i la disponibilitat dels camps
`pms_property_id(s)` a les vistes que utilitzen dominis automàtics, tal com
s'explica a les instruccions d'ús.
