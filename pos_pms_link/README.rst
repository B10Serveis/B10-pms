TPV i reserves: enllaç amb el PMS
=========================================

El mòdul ``pos_pms_link`` connecta el punt de venda d'Odoo amb les reserves
hotel·leres del PMS. Permet registrar al TPV serveis que ja formen part d'una
reserva i carregar-hi consums nous perquè es facturin posteriorment des del PMS.

Aquesta documentació correspon al fork B10 per a Odoo 16.

.. contents:: Contingut
   :local:
   :depth: 2

Què fa cada botó de reserva?
------------------------------------

Hi ha dues operacions diferents, segons la pantalla on es prem el botó.

**A la pantalla de productes: afegir serveis de la reserva al tiquet.**

El botó «Reserva núm.» incorpora els serveis de la reserva corresponents a
avui que encara tenen quantitat pendent de registrar al TPV. Les línies
s'afegeixen amb **preu zero**, perquè el servei ja existeix al PMS.
Aquesta operació registra el servei al TPV; no és un nou cobrament del seu
import ni crea un altre càrrec a la reserva.

Exemple: una reserva té dos esmorzars per a avui i ja se n'ha registrat un
al TPV. En seleccionar-la, s'afegeix una línia d'un esmorzar a preu zero.
L'import del servei continua formant part de la reserva al PMS.

**A la pantalla de pagament: carregar el tiquet a la reserva.**

El botó «Reserva» permet finalitzar un tiquet amb consums nous i traslladar-los
a una reserva. Utilitza el mètode de pagament configurat per a aquest ús;
**no cobra efectiu ni targeta en aquell moment**. Les línies que encara no
estan vinculades a un servei del PMS generen serveis nous a la reserva.

Exemple: un hoste consumeix dos cafès per un total de 4 €. Es crea el tiquet
amb els cafès i es finalitza amb «Reserva». Els consums es carreguen a la
reserva i es cobraran i facturaran des del PMS.

Configuració inicial
----------------------------

El mòdul necessita els mòduls de punt de venda, PMS i empleats del TPV.
Els noms dels menús poden variar lleugerament segons les traduccions d'Odoo.

Mètode «Càrrec Hotel» creat automàticament
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

En instal·lar o actualitzar el mòdul, es crea un mètode **«Càrrec Hotel» per
cada empresa existent**, amb **«Fraccionar transaccions» activat** i el
**diari buit**. Per tant, és de tipus «Compte de client» i està preparat
per al càrrec a reserva.

Si l'empresa ja té un mètode actiu amb aquest nom i aquesta configuració,
s'utilitza l'existent. No es modifiquen els mètodes que ja teniu ni
s'assigna automàticament el mètode als TPV: aquesta elecció és manual.
Si existeix un «Càrrec Hotel» amb una configuració incompatible o arxivat,
es crea un altre mètode vàlid; comproveu quin seleccioneu al TPV.

Per a una empresa creada després d'instal·lar el mòdul, actualitzeu el
mòdul per generar-ne el mètode o creeu-lo manualment a
**TPV > Configuració > Formes de pagament**: mateixa empresa que el TPV,
«Fraccionar transaccions» marcat i diari buit. En Odoo 16, el diari és
obligatori quan aquesta casella està desmarcada.

Manteniu els mètodes de targeta i efectiu amb els seus diaris corresponents.
Odoo no permet modificar un mètode utilitzat en sessions obertes.

Activar l'enllaç al TPV
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Obriu la configuració del TPV a **TPV > Configuració > Configuració**.
#. Activeu **«Càrrec a la reserva»**.
#. Al camp **«Mètode de pagament per carregar a la reserva»**, seleccioneu
   «Càrrec Hotel».
#. Indiqueu els **establiments permesos per a les reserves**, si voleu
   limitar-ne la selecció. Han de pertànyer a l'empresa del TPV.
#. Deseu la configuració i torneu a carregar la interfície del TPV.

Si no s'indiquen establiments, es consideren els de l'empresa del TPV.
Activar «Càrrec a la reserva» habilita tant el selector de serveis a la
pantalla de productes com el cobrament a reserva a la pantalla de pagament.

Preparar els productes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Reviseu els productes dels serveis del PMS que utilitzareu al TPV. És
recomanable marcar-los com a disponibles al punt de venda i configurar-ne
correctament els impostos.

Si un producte no està carregat, el mòdul intenta obtenir-lo del servidor
abans d'afegir els serveis. Aquesta càrrega no modifica la seva configuració
de disponibilitat. Si no el pot obtenir, mostra un error amb el producte
afectat i no afegeix parcialment els serveis seleccionats.

Quines reserves apareixen?
----------------------------------

El selector mostra les reserves que compleixen totes aquestes condicions:

* Pertanyen a l'empresa del TPV.
* Pertanyen als establiments permesos, si s'han especificat.
* No estan cancel·lades.
* La data d'entrada és anterior o igual a avui.
* La data de sortida és posterior o igual a avui.

No es limita exclusivament a l'estat «Allotjada»: la condició d'estat
exclou les cancel·lades, i les dates determinen si la reserva és vigent.
Una reserva encara allotjada però amb data de sortida passada no apareix.
Els càrrecs d'aquestes reserves es poden gestionar des del PMS abans de
registrar-ne la sortida.

La llista s'actualitza en obrir el selector. La cerca permet trobar les
reserves carregades per nom de reserva, client o habitació; no amplia
els filtres de dates, empresa o establiment.

Registrar serveis ja inclosos en una reserva
----------------------------------------------------

#. Obriu un tiquet a la pantalla de productes i premeu **«Reserva núm.»**.
#. Cerqueu la reserva, seleccioneu-la i confirmeu la selecció.
#. Reviseu les línies afegides: només es tenen en compte els serveis
   d'avui, restant les quantitats ja registrades o pendents al TPV.
#. Finalitzeu el tiquet segons correspongui. Les línies dels serveis
   incorporats mantenen el preu zero; altres productes afegits al mateix
   tiquet poden tenir un import a cobrar.

La vinculació amb la línia de servei permet registrar les quantitats
sense tornar a crear el servei al PMS.

Carregar consums nous a una reserva
-------------------------------------------

#. Afegiu els productes consumits al tiquet amb els seus preus habituals.
#. El tiquet necessita un client per al mètode amb «Fraccionar transaccions»
   activat. Si encara no en té, en seleccionar la reserva s'hi assigna
   automàticament el contacte associat. Si la reserva només té un nom i
   cap contacte, el TPV us demanarà que en seleccioneu un. Un client ja
   seleccionat al tiquet es conserva.
#. Aneu a la pantalla de pagament. Deixeu desactivada l'opció **«Factura»**:
   la facturació del càrrec es farà des del PMS.
#. Sense cap altra línia de pagament al tiquet, premeu **«Reserva»**.
#. Seleccioneu la reserva, comproveu-ne el client i l'habitació i confirmeu
   el càrrec.
#. El TPV afegeix el mètode «Càrrec Hotel» i intenta validar el tiquet.
   Un cop desat correctament, les línies noves generen serveis a la reserva
   amb les quantitats, preus, descomptes i impostos del tiquet.

Cal carregar **tot el tiquet** a la reserva: aquest circuit no admet dividir
el pagament entre reserva, targeta o efectiu. Tampoc permet emetre una
factura directa des del TPV per al mateix càrrec. La reserva i el TPV han
de tenir la mateixa moneda.

Desar un esborrany no genera els serveis nous: es creen en finalitzar
la comanda. El rebut de càrrec a reserva inclou un espai de signatura.
Comproveu el càrrec al PMS abans de continuar amb la facturació de la reserva.

Altres opcions del mòdul
--------------------------------

* **Permet tancar la sessió:** amplia la disponibilitat del botó de
  tancament. Les comprovacions d'Odoo per tancar i validar la sessió
  continuen aplicant-se.
* **Permet entrades i sortides d'efectiu:** amplia la disponibilitat
  d'aquestes operacions per als empleats quan hi ha control d'efectiu.
* **Utilitza un client en els moviments d'efectiu:** permet associar un
  client al moviment. Si s'escull «Sense client», cal indicar-ne el motiu.

El mòdul també registra el nom del caixer en les operacions d'obertura,
tancament i moviment d'efectiu que passen pels circuits ampliats del TPV.

Problemes habituals
---------------------------

**El mètode «Càrrec Hotel» exigeix un diari.**

Marqueu «Fraccionar transaccions» abans de deixar el diari buit. Si té un
diari bancari o d'efectiu, no és un mètode diferit de càrrec a reserva.

**No apareix cap reserva o no trobo la que busco.**

Reviseu les dates, l'estat, l'empresa del TPV i els establiments permesos.
La cerca no mostra reserves fora d'aquest àmbit.

**Odoo demana un client en validar.**

El mòdul assigna el contacte de la reserva si el tiquet encara no té client.
Si la reserva no té cap contacte associat, seleccioneu el client manualment.
Un nom de client escrit a la reserva no equival a un contacte d'Odoo.

**Apareix un error relacionat amb la factura o el pagament.**

Desactiveu «Factura» i comproveu que tot l'import utilitza el mètode
configurat per carregar a la reserva. Per cobrar directament amb targeta
o efectiu, utilitzeu el circuit ordinari de pagament del TPV.

**La càrrega de reserves o productes falla.**

Reviseu el missatge que mostra la pantalla. El selector permet reintentar
la consulta. Si hi ha hagut canvis de codi o traduccions, actualitzeu el
mòdul i recarregueu completament el navegador; els canvis Python també
requereixen reiniciar Odoo.

Informació tècnica
------------------

La revisió tècnica, les proves executades i els seus límits es documenten
a `REVIEW.md <REVIEW.md>`_. El registre de versions és a
`readme/HISTORY.rst <readme/HISTORY.rst>`_.

Llicència: AGPL-3. Autoria original: Comunitea Servicios Tecnológicos S.L.
i Odoo Community Association (OCA). Manteniment del fork: Batista10.
