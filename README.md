
# B10 PMS

Sistema de gestió d'establiments per a Odoo 16.

Aquest repositori és un projecte independent que parteix del codi de la branca
16.0 d'[OCA/pms](https://github.com/OCA/pms). A partir d'aquesta separació,
el desenvolupament, l'arquitectura i les versions es gestionen segons les
necessitats pròpies de B10 PMS.

## Criteri de desenvolupament

- La separació d'OCA és total: no es preveu sincronitzar el repositori,
  recuperar-ne canvis ni mantenir compatibilitat amb la seva evolució futura.
- Els desenvolupaments es fan directament a `pms` o al mòdul corresponent
  d'aquest repositori. Es poden modificar i refactoritzar parts importants
  del nucli quan les necessitats del projecte ho requereixin.
- No es creen mòduls auxiliars per evitar modificar el nucli. Els mòduls
  existents es mantenen segons la seva funció dins del projecte.
- Es conserven els noms tècnics dels mòduls i els identificadors XML per
  mantenir la compatibilitat amb les instal·lacions existents. Qualsevol canvi
  que l'afecti ha d'incloure la migració corresponent.
- Les versions i el registre de canvis són propis del projecte i han de
  permetre identificar què s'ha desplegat.
- Els canvis es treballen en branques de desenvolupament i es revisen i
  validen abans d'integrar-los a la branca estable.
- Les actualitzacions que afectin models, camps, restriccions o processos de
  reserves i facturació s'assagen en una còpia de la base de dades abans
  d'aplicar-les a producció.

L'historial, els avisos de copyright i les atribucions originals es conserven
com a reconeixement de la procedència del codi.

La versió `16.0.5.0.0` de `pms` marca l'inici de l'etapa independent de B10 PMS,
posterior a la versió `16.0.4.24.0` de partida. Les versions següents seguiran
una numeració pròpia dins de la sèrie d'Odoo 16.

La versió `16.0.5.1.0` millora els filtres i la llegibilitat de la timeline
de reserves. Els canvis i les condicions d'actualització es documenten al
[registre de canvis de PMS](pms/CHANGELOG.md).

La versió `16.0.3.0.0` de `pms_l10n_es` marca l'inici de la seva etapa
independent, posterior a la versió `16.0.2.4.0` de partida. Inclou els canvis
locals ja incorporats als formularis de propietats i a la classificació
turística i les reparacions dels informes SES: enviament manual, filtres de
dates i habitacions i conservació dels accents als noms. No requereix migració
de dades.

La versió `16.0.2.0.0` de `multi_pms_properties` inicia la seva etapa
independent, posterior a `16.0.1.0.1`. El registre de canvis del mòdul
explica les correccions i les condicions d'actualització.

<!-- prettier-ignore-start -->

[//]: # (addons)

Available addons
----------------
addon | version | maintainers | summary
--- | --- | --- | ---
[multi_pms_properties](multi_pms_properties/) | 16.0.2.0.0 |  | Multi Properties Manager
[pms](pms/) | 16.0.5.1.0 |  | A property management system
[pms_account_move_budget](pms_account_move_budget/) | 16.0.1.0.0 |  | Add Property Field in Account Move Budget
[pms_hr_property](pms_hr_property/) | 16.0.1.0.0 |  | Adds to the employee the property on which he works.
[pms_l10n_es](pms_l10n_es/) | 16.0.3.0.0 |  | PMS Spanish Adaptation
[pms_l10n_es_sii](pms_l10n_es_sii/) | 16.0.1.2.0 |  | PMS AEAT SII Integration
[pms_l10n_es_tbai](pms_l10n_es_tbai/) | 16.0.1.1.0 |  | PMS TicketBAI Integration
[pms_partner_identification](pms_partner_identification/) | 16.0.2.3.0 |  | Add identification models in pms
[pms_partner_second_lastname](pms_partner_second_lastname/) | 16.0.2.2.0 |  | Add lastname2 in pms models
[pos_pms_link](pos_pms_link/) | 16.0.1.1.0 |  | Allows to use PMS reservations on the POS interface

[//]: # (end addons)

<!-- prettier-ignore-end -->

## Llicències

Aquest repositori es distribueix sota la llicència [AGPL-3.0](LICENSE).

Consulteu la clau `license` del fitxer `__manifest__.py` de cada mòdul per
conèixer la seva llicència específica. La separació del projecte no modifica
les llicències ni elimina les atribucions del codi original.
