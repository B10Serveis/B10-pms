# Registre de canvis

## 16.0.3.5.1 — Traduccions al català i castellà

S'actualitza el catàleg de traduccions del mòdul i es completen els 417 textos
en català i castellà, incloent-hi la configuració, la previsualització, els
errors de validació i la generació i l'historial de fitxers de Mossos.

## 16.0.3.5.0 — Generació V24 i historial de fitxers Mossos

L’assistent permet generar un fitxer amb els viatgers seleccionats i obre el
lot des del qual es pot descarregar. Es torna a validar la informació actual
en generar, encara que la previsualització anterior no mostrés errors.
Només s’accepten fitxes de l’establiment amb entrada real en estat onboard o
done, que coincideixin amb el dia seleccionat o amb la revisió explícita
d’entrades anteriors. No cal tenir cap factura.

### Contingut i nom

S’aplica `fitxer_mossos.pdf`, actualització de maig de 2025, pàgines 18–23:
capçalera de set camps amb V24, una línia de 32 camps per viatger, separadors
`|` i camps buits preservats, dates yyyyMMdd, hores HHmm i registres separats
per CRLF, sense un salt final addicional. UTF-8 sense BOM, confirmat per
l’usuari durant aquesta sessió. Les longituds es comproven després de passar
a majúscules; no es retallen dades. Es conserven accents i caràcters d’adreça
com º i ª; es rebutgen separadors, controls i lletres d’altres alfabets.

La capçalera reflecteix el nombre real de viatgers seleccionats. L’entrada i
la data de contracte es converteixen d’UTC a l’hora local de l’establiment;
la sortida és la data i hora prevista de la reserva. El contracte és C i el
número correspon a la reserva. La reserva representa una habitació: un canvi
de la cambra assignada durant l’estada no crea una habitació simultània més.
Les dades personals són les de la fitxa del viatger; pagament i codis postals
utilitzen les correspondències definides als increments anteriors.

Es distingeixen document espanyol i estranger pel tipus i país emissor;
NIE s’informa al camp estranger. S’utilitza O, d’un caràcter, segons la taula
del PDF, encara que les regles descriptives també esmentin OTRO. S’afegeix la
comprovació de la lletra de DNI/NIE i de totes les longituds dels 32 camps,
a més dels controls ja existents de menors, parentiu, suport, adreça i contacte.

El nom és `<identificador>.001.txt`. El PDF mostra exemples acabats en .001
i també indica que l’extensió comuna és .txt: es conserva la seqüència de tres
dígits dins el nom i s’hi afegeix l’extensió .txt. El següent número es pot
configurar a l’establiment; per defecte és 001. Després del 999 torna al 001.
La generació bloqueja la fila de l’establiment mentre reserva el número.
Una validació fallida no consumeix numeració. El format no s’ha presentat ni
validat amb una càrrega real al portal en aquest desenvolupament.

### Lots i comunicació

El menú Reserves → Mossos generated files conserva el fitxer exacte, la data,
l’usuari generador i les instantànies dels viatgers inclosos. Tornar a generar
amb el mateix assistent o recuperar una selecció idèntica amb un lot pendent
reutilitza el fitxer existent. Descarregar no regenera el contingut ni consumeix
una altra seqüència. Els canvis posteriors a les fitxes no alteren el fitxer.

Generar o descarregar deixa el lot pendent de presentació. Només el botó de
confirmació manual, després de presentar el fitxer al portal, marca el lot
com a presentat, amb data i usuari. Es pot adjuntar el comprovant, abans o
després de confirmar. No es contacta amb el portal ni es verifica el comprovant.
Els valors inicials d’estat i codificació són explícits i no poden heretar un
estat de presentació d’altres contextos de la interfície.

Els viatgers que ja són en un lot generat o presentat no es tornen a oferir
com a pendents. El control es fa per fitxa/estada; una nova estada del mateix
contacte crea una nova comunicació. Les presentacions externes anteriors a
B10 no s’importen automàticament.

Per corregir dades abans de presentar, cal cancel·lar el lot amb un motiu i
generar-ne un altre. La cancel·lació conserva el fitxer i els viatgers antics
i allibera aquestes fitxes per al nou lot. Un lot presentat no es pot cancel·lar.
No es permet esborrar l’historial o editar el contingut dels fitxers generats.
Els permisos de lectura i descàrrega es limiten a la societat i als establiments
autoritzats de l’usuari PMS. El comptador tècnic es pot incrementar des de
recepció sense donar permisos generals de configuració de l’establiment.

### Actualització i validació

Cal actualitzar `pms_l10n_es` i reiniciar Odoo per crear els nous models,
regles, camps i vistes. Es manté la correcció visual de la versió 16.0.3.4.1.
No es marca cap fitxa existent com a comunicada durant l’actualització.
Els processos SES es conserven.

69 proves Odoo correctes a `mossos_preview_test`: 19 de generació/historial,
14 de previsualització, 13 de pagaments, 18 de codis INE i 5 dels informes SES.
Inclou format binari UTF-8, CRLF, recompte, camps buits, hores locals,
selecció parcial, DNI/NIE/passaports, menors sense document, longituds,
revalidació, numeració 999→001, recuperació sense duplicats, cancel·lació,
confirmació manual, nou allotjament del mateix contacte, immutabilitat del
fitxer i permisos d’un usuari de recepció i d’un altre establiment.
Sintaxi Python, XML i `git diff --check` correctes. Sense desplegament ni
modificacions de `fasersia` i sense cap presentació real al portal.

## 16.0.3.4.1 — Color de les files de Mossos sense errors

La decoració vermella comprova `bool(errors)` en lloc de comparar el text
amb `False`. Així, un text buit no activa el color d’error; les files amb
errors continuen en vermell. No canvien les validacions ni la selecció dels
viatgers. Cal actualitzar `pms_l10n_es` per carregar la vista corregida.

## 16.0.3.4.0 — Correspondència dels pagaments Mossos

S’afegeix `account.payment.mode.mossos_payment_type` per relacionar manualment
cada mode de pagament amb un dels vuit codis del fitxer: DESTI, EFECT, MOVIL,
OTRO, PLATF, TARJT, TRANS o TREG. A la configuració Mossos de cada establiment
s’afegeix `mossos_default_payment_type`, sense valor inicial automàtic.

Per a cada expedient es tria el cobrament efectiu més antic: primer la data
comptable de cobrament i, per desempatar cobraments del mateix dia, la data i
hora UTC de creació del registre. La data comptable no conté hora; no s’inventa
una hora real de cobrament. En un empat exacte s’utilitzen el model i l’ID per
mantenir un ordre estable. No es tria el pagament de més import ni el primer
que tingui una correspondència configurada.

Si el cobrament seleccionat té un mode amb correspondència Mossos, s’utilitza
el seu codi. Si no té mode, no té correspondència o no hi ha cobrament, es fa
servir el tipus configurat a l’establiment. Si també falta aquest valor,
la previsualització mostra l’error de configuració. Un cobrament més recent
amb correspondència no substitueix el més antic sense correspondència.
No s’infereix el tipus del diari, les condicions de pagament, el proveïdor en
línia, el contacte ni una factura. Configurar el tipus per defecte no crea
cap pagament comptable.

Es consulten `payment_ids`, `statement_line_ids` i `transaction_ids` del foli.
Es consideren els pagaments de clients d’entrada, positius, comptabilitzats
i que no siguin traspassos interns; els apunts de caixa/banc positius i
comptabilitzats; i les transaccions en estat done que no siguin devolucions.
Les transaccions es resolen a través del seu pagament comptable quan existeix;
si no hi ha pagament comptable efectiu, no s’inventa un mode i s’aplica el valor
per defecte. Per a la data d’una transacció sense pagament s’utilitza el seu
últim canvi d’estat, amb conversió a la zona horària de l’establiment.
Un pagament relacionat tant amb una transacció com amb un apunt bancari es
compta una sola vegada. Els esborranys, cancel·lacions, imports no positius i
pagaments de sortida no intervenen en la tria.

S’afegeix dependència de `account_payment_partner` per utilitzar la relació
estàndard `payment_mode_id` de l’assentament, delegada als pagaments i als
apunts bancaris. La fitxa comptable del pagament mostra aquest camp i
l’assistent de cobrament del PMS permet seleccionar-lo de manera opcional.
L’assistent comprova societat, mètode i diari, i conserva el mode escollit en
el cobrament creat. Es mantenen els permisos dels models comptables.

La previsualització Mossos mostra el tipus, l’origen (mode del cobrament o
configuració per defecte) i, opcionalment, la referència del cobrament triat.
Les dades es refresquen en tornar a generar la previsualització; no es crea
ni presenta cap fitxer. Els processos de SES no canvien.

Cal actualitzar `pms_l10n_es` per incorporar la nova dependència, els camps i
les vistes, i configurar manualment les correspondències i els valors per
defecte. No es modifica la classificació de cap mode existent.

Validació a la base temporal `mossos_preview_test`: 50 proves Odoo correctes,
sense errors ni proves omeses a la passada final. Inclou 13 proves de
pagaments reals amb comptes comptables de prova, 14 de previsualització,
18 de codis INE i 5 dels informes SES existents. Verifica cobraments mixtos,
ordre de data i hora, cancel·lacions i devolucions, absència de factura,
caixa, transaccions amb/sense pagament comptable, absència de duplicats i
creació de cobrament des de l’assistent del PMS amb el mode seleccionat.
Sintaxi Python, XML i `git diff --check` correctes. Sense canvis a `fasersia`.

## 16.0.3.3.0 — Municipi INE de sis dígits amb control

`res.city.ine_municipality_code` passa a ser un Char calculat i emmagatzemat.
Es consulta el CSV existent de correspondències exactes ZIP → municipi INE.
Si la població té més d’un ZIP conegut, s’intersecten els candidats; quan queda
un únic municipi compatible amb el prefix provincial, se’n calcula el control
i es desa el codi de sis dígits. Si falten dades, hi ha ambigüitats o els ZIP
apunten a municipis diferents, queda buit amb un error visible a la població.
S’actualitza en editar o reassignar ZIP, país o província.

Els primers cinc dígits són el codi municipal INE, no el codi postal.
Exemples del CSV: ZIP `08001` → Barcelona `080193`; ZIP `25001` → Lleida
`251207`. `08000` i `25000` no tenen correspondència al CSV i no s’inventa cap
codi municipal. Les bases municipals `08019` i `25120` es corresponen amb els
codis de sis dígits anteriors. No es recorre al ZIP de l’establiment quan
falta el del viatger.

S’apliquen les taules en l’ordre doble, triple, identitat, doble, triple
d’esquerra a dreta, segons les implementacions enllaçades a la petició, amb
control `(-suma) % 10`. Es corregeix el cas de suma múltiple de deu perquè
doni `0` i no `10`. La descripció posicional del missatge inicial no coincidia
amb aquestes implementacions. El càlcul coincideix amb els 8.124 municipis
diferents del CSV, que té 11.051 ZIP, dels quals 2.266 són ambigus.

Fonts: [descripció de l’INE](https://www.ine.es/daco/daco42/codmun/codmun00i.htm),
[implementació PHP](https://gist.github.com/ivanramosnet/b604887cbb21e508761cc0d6b3ee4a07)
i [implementació Java](https://gist.github.com/eltabo/e9fa5fc1e5dd8c2140b4).
El CSV és el recurs ja inclòs al repositori; validar-ne el control no en
certifica l’actualitat ni l’associació amb el nom concret de cada població.
No s’ha descarregat ni importat cap nou padró municipal.

La previsualització de Mossos aplica la mateixa correspondència al ZIP del
viatger i mostra el codi resolt o l’error concret. No exigeix una factura ni
pren les dades del titular del foli. Els processos SES es conserven.

Les migracions preserven els valors manuals previs a
`ine_municipality_previous_code`, visible quan té contingut, i recalculen el
camp principal per a les poblacions existents. Cal actualitzar `pms_l10n_es`
i reiniciar Odoo per incorporar models, vistes i migracions.

Validació: 31 proves Odoo correctes a `mossos_preview_test` (9 municipals,
9 provincials i 13 de previsualització). Inclou el control de tots els codis
del CSV, el dígit zero, ZIP ambigus i contradictoris, canvis de ZIP i país,
reassignacions i eliminacions, i el codi mostrat a la previsualització.
La migració des de 16.0.3.2.1 s’ha provat amb dades fictícies: un valor manual
`08019` queda preservat i el ZIP `08001` resol automàticament `080193`.
Sintaxi Python, XML i `git diff --check` correctes.

## 16.0.3.2.1 — Prefix provincial a partir del codi postal

`ine_province_code` ara es calcula amb els dos primers caràcters del primer
codi postal espanyol vàlid de les poblacions vinculades a la província.
S’ordenen les poblacions per ID i els seus codis postals per codi i ID;
s’utilitza el primer vàlid i s’atura la cerca, sense comparar amb els altres.
Per exemple, `25000` → `25` i `08000` → `08`. No es requereix cap codi municipal
INE. El camp `ine_code` conserva el valor i el funcionament actuals.

S’ignoren codis que no tinguin cinc dígits ASCII, prefixos fora de 01–52 i
poblacions d’un país diferent. Si no hi ha cap codi postal vàlid, el resultat
queda buit amb un error visible. Editar, reassignar o eliminar un codi postal
o una població recalcula la província. El camp municipal INE es conserva per
compatibilitat, però no intervé en aquest càlcul.

La migració posterior recalcula tots els valors provincials desats quan
s’actualitza `pms_l10n_es`; canviar només el codi Python no actualitza els
resultats emmagatzemats. Aquesta versió substitueix el criteri de consens
documentat a la versió anterior.

Validació: 21 proves Odoo correctes (9 del càlcul provincial postal i 12 de
Mossos), tant en instal·lació com en actualització a la base temporal
`mossos_preview_test`. Migració provada des de la versió 16.0.3.2.0 amb una
província fictícia que tenia el valor desat `99`: s’ha recalculat a `25` a
partir del ZIP `25000`, s’ha netejat l’error anterior i s’ha preservat
`ine_code`. Sintaxi Python i `git diff --check` correctes.

## 16.0.3.2.0 — Codi provincial INE a partir dels municipis

S’afegeix `res.country.state.ine_province_code`, de tipus Char, calculat i
emmagatzemat. Es conserva `ine_code` i el seu ús actual per als informes INE.
El càlcul recorre totes les poblacions vinculades a la província que tenen
`res.city.ine_municipality_code`. Només desa un prefix si tots coincideixen.
Conserva els zeros inicials (`08`, `01`, etc.). Si falten dades, hi ha codis
mal formats, un país inconsistent o prefixos diferents, el codi queda buit
amb el motiu a `ine_province_error`.

Els canvis de codi o país, les reassignacions de província i les eliminacions
de municipis recalculen els resultats. Les poblacions sense codi es deixen
pendents i no es fan servir per deduir el prefix; un codi informat però mal
format bloqueja l’assignació per evitar ignorar una possible discrepància.

La instal·lació revisada no disposava de codi municipal INE a `res.city`:
`l10n_es_toponyms` importa GeoNames. Per això s’afegeix un camp explícit, sense
copiar identificadors de GeoNames, codis postals ni els valors ES111 de
`ine_code`. Es pot informar a Contactes → Configuració → Localització →
Poblacions. El resultat i els errors es mostren al formulari i al llistat de
províncies, i l’error provincial també apareix a la previsualització de Mossos.

Segons [l’INE](https://www.ine.es/daco/daco42/codmun/codmun00i.htm), el codi
municipal té cinc dígits, amb un sisè dígit de control publicat separadament.
S’accepten codis de cinc o sis dígits per obtenir el prefix, sense retallar ni
completar zeros. Es comproven longitud, dígits ASCII, prefix 01–52 i número
municipal diferent de 000. Això valida l’estructura; no certifica l’existència
oficial del municipi ni comprova el dígit de control. Cal carregar codis INE
verificats; no s’ha fet cap assignació automàtica a partir de noms o ZIP.
Per al futur fitxer Mossos, el municipi continuarà requerint sis dígits.

Validació: actualització del mòdul a `mossos_preview_test`; 19 proves Odoo
correctes (7 del càlcul provincial i 12 de Mossos). Inclou absència de dades,
zeros inicials, codis de cinc/sis dígits, discrepàncies, correcció d’errors,
formats invàlids, canvi de país, reassignació i eliminació. Sintaxi Python,
XML i `git diff --check` correctes. Cal actualitzar `pms_l10n_es` per crear les
columnes i recomputar les províncies existents. Sense dades municipals INE,
quedaran pendents; no es modifica cap valor de `ine_code`.

## 16.0.3.1.1 — Correcció del llistat diari de Mossos

El dia seleccionat filtra exclusivament les entrades reals d’aquell dia en la
zona horària de l’establiment. S’exclouen les entrades de dies anteriors, tant
si el viatger continua allotjat com si ja ha sortit. Un viatger que ha entrat i
sortit el mateix dia continua corresponent a aquell dia d’entrada.

La revisió d’entrades anteriors és una opció explícita, desactivada per defecte,
per recuperar regularitzacions tardanes. Mostra un avís perquè encara no hi ha
historial de presentacions i pot incloure estades ja comunicades manualment.
Els límits de mitjanit es converteixen separadament a UTC per respectar els dies
de 23 o 25 hores. Cal actualitzar `pms_l10n_es` i reiniciar Odoo per incorporar
el camp nou i la vista.

Validació: 12 proves Odoo correctes a `mossos_preview_test`, inclosa l’exclusió
per defecte de viatgers amb entrades anteriors tant allotjats com ja sortits,
límits de mitjanit, canvi a horari d’estiu i recuperació explícita de les
regularitzacions tardanes. Sintaxi Python, XML i `git diff --check` correctes.

## 16.0.3.1.0 — Mossos, primer increment

Configuració independent de SES per establiment: activació, identificador policial
i disponibilitat d'internet. Assistent a Reserves → Mossos: preview arrivals.
Selecciona establiment i dia d’entrada i prem Refresh pending arrivals. Inclou
les fitxes amb entrada real aquell dia, en estat onboard o done. La revisió
explícita d’entrades anteriors permet recuperar les regularitzades tard. No requereix factura. Refrescar substitueix les
línies temporals i no duplica la previsualització.

Mostra viatger, reserva, document, entrada local i errors. No retalla dades.
L'entrada prové de la fitxa individual; la sortida prevista és la de la reserva.
Les dades personals no es recuperen del titular del foli. Es mantenen els camps
i processos existents de SES.

Aquest increment és una previsualització de dades, no un exportador V24 complet.
No genera fitxers, no marca presentacions ni desa lots. Fins a implementar
l'historial, no pot distingir les entrades presentades fora de B10 PMS. El
llistat diari només inclou el dia seleccionat; la revisió d’entrades anteriors
requereix activar expressament l’opció corresponent. El selector no confirma cap presentació.

### Pendents per al següent increment

- Correspondència explícita dels mitjans de pagament dels cobraments del foli
  (`payment_ids`, `statement_line_ids`, `transaction_ids`), inclosos els mixtos.
  Cap inferència a partir de les condicions de pagament o el tipus de diari.
- Correspondències verificades de província de dos dígits i municipi de sis
  dígits. El CSV de codis postals pot donar diversos municipis; `ine_code`
  provincial no és directament el codi requerit. Sense recurs a l'adreça de l'hotel.
- Confirmar la codificació de text: el PDF de maig de 2025 no especifica charset.
- Discrepància documental `OTRO` a les regles i `O` a la taula d'un caràcter.
  El previsualitzador reconeix D/N/P/O; els documents nacionals estrangers D es
  marquen per revisió, no es tracten com a DNI espanyol.
- Validació completa V24, comprovació de dígit de control de DNI/NIE,
  comportament de les reserves amb canvis d'habitació i recompte dels viatgers.
- Lots persistents, recuperació sense duplicats, seqüència 001–999, contingut
  immutable, confirmació manual amb comprovant i exclusió per fitxa/estada
  presentada. Generar o descarregar no equivaldrà a presentar.

Cal actualitzar `pms_l10n_es` en una base de proves abans del desplegament.
S'afegeixen camps i models temporals; no es transforma cap dada existent.

### Validació del primer increment

Instal·lació/recàrrega del mòdul sobre la base aïllada `mossos_preview_test`
(PostgreSQL a `/tmp/mossos_preview_pg`, port 55443). Vuit proves Odoo de
`TestMossosPreview`, sense errors: configuració desactivada, dia local i refresc,
menors i longituds sense retallada, DNI i suport, document nacional estranger,
separació entre establiments, assistent real de regularització després de la
sortida i conversió horària d'estiu independent de la zona de l'usuari.
Sintaxi Python, XML i `git diff --check` correctes.

La prova de regularització ha requerit completar de nou el país de residència
després de l'assignació del contacte: el càlcul actual de `country_id` a
`pms.checkin.partner` pot buidar-lo quan no hi ha província. És un comportament
preexistent del nucli a revisar separadament; la previsualització mostra el
país absent com a error. No s'ha modificat el nucli en aquest increment.
