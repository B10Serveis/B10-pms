# Revisió del fork B10 — 2026-10-06

Revisió dels models, dels loaders del TPV, del codi JavaScript, de les vistes
i de la compatibilitat amb el codi local d'Odoo 16.

## Errors greus corregits

- **Salt de permisos:** `pos_user_force=True` activava `sudo()` en
  `search_read` de reserves, serveis, línies, contactes, tarifes i configuracions.
  Qualsevol client podia enviar aquest context. S'elimina aquesta elevació
  global; la lectura elevada queda dins del loader específic, que comprova
  l'accés a la sessió i el grup TPV, limita els camps i intersecta sempre el
  domini amb l'empresa, les propietats i les dates permeses del servidor.
- **Càrrecs indeguts:** el servidor acceptava reserves d'altres empreses o
  propietats, cancel·lades o inexistents (`browse()` no comprova existència).
  Ara valida existència, empresa, propietat i moneda, exigeix cobrament íntegre
  amb el mètode diferit configurat i rebutja la facturació simultània al TPV.
  La configuració valida l'empresa del mètode; el tipus diferit s'exigeix
  en carregar la comanda a la reserva, sense bloquejar l'obertura del TPV.
- **Càrrecs prematurs:** desar un esborrany ja generava serveis a la reserva.
  Ara només els genera en finalitzar, conservant el payload original.
- **Comptabilitat:** s'eliminaven vendes de qualsevol comanda vinculada,
  incloses les facturades, i els impostos globals s'arrodonien conjuntament
  per tota la sessió. Ara només es resten els càrrecs a reserva no facturats,
  amb arrodoniment per comanda, igual que Odoo. Es resten els seus cobraments
  diferits concrets, en lloc d'anul·lar tot el saldo del mètode de pagament.
- **Fiscalitat del servei:** els serveis generats conserven els impostos
  efectivament aplicats a la línia TPV, després de la posició fiscal.
- **Recuperació de comandes:** els hooks antics no exportaven els camps
  d'enllaç en el circuit real d'Odoo 16. S'utilitza `_export_for_ui` tant
  per a la comanda com per a les línies.
- **Frontend:** l'addició de productes sense `options` podia fallar; la
  recàrrega de reserves tenia `lenght` i cridava un endpoint inexistent.
  Es corregeixen tots dos punts. Les línies PMS no es fusionen i les
  quantitats locals s'identifiquen per línia, conserven decimals i s'eliminen
  sense modificar les d'altres comandes. El cobrament utilitza el mètode real
  carregat per Odoo i comprova que s'ha pogut afegir el pagament.

## Versió i ús

S'inicia la branca B10 amb `16.0.2.0.0`, autoria i URL del fork, i registre
propi de canvis. Per habilitar el cobrament a reserva cal un mètode de tipus
`pay_later` de la mateixa empresa. Si no es configuren propietats, s'admeten
les de l'empresa del TPV. El loader continua limitant les reserves a les
estades vigents; la càrrega d'una comanda pendent pot referir-se a una reserva
fora d'aquest interval, però ha de superar les altres validacions.

## Validació i límits

- 19 proves Python aïllades executades sobre els mètodes de producció amb
  dobles de sessió/ORM: càrrecs, esborranys, exportació, permisos i dominis,
  i comptabilitat amb arrodoniment global per comanda.
- Comprovacions JavaScript executades amb Node sobre les extensions reals:
  productes, recàrrega i quantitats decimals de múltiples línies.
- Sintaxi Python/XML i `git diff --check` correctes.

Aquestes proves no carreguen el registre complet d'Odoo ni una base de dades.
No s'ha executat un navegador ni una prova integral de tancament, devolucions,
recuperació offline o concurrència entre terminals. Cal validar aquests
circuits en una base de proves abans de desplegar el mòdul. La revisió no
certifica l'absència de qualsevol altre error; queden fora l'auditoria
completa de permisos de PMS i la coherència de les dades preexistents.
No s'ha actualitzat producció ni s'ha creat cap commit.

Ordres reproduïbles:

```sh
python3 -m unittest discover -s pos_pms_link/tests -v
node pos_pms_link/tests/test_frontend.cjs
```

## Correcció de compatibilitat en obrir el TPV

Odoo 16 executa `self._validate_fields(self._fields)` dins de `open_ui`.
La primera versió de la nova constraint exigia un mètode diferit fins i tot
per obrir un TPV amb configuració antiga o incompleta. Es retira aquesta
exigència de la constraint i es conserva en `_process_order`, on també
es comprova l'empresa del mètode. Les vendes ordinàries poden continuar;
els càrrecs a reserva requereixen configurar el mètode correctament.
Tres regressions addicionals cobreixen mètode antic d'efectiu, mètode absent
i rebuig de mètodes d'una altra empresa.

## Actualització del selector de reserves

El selector només cercava dins de la fotografia carregada en iniciar el TPV.
Ara consulta el loader segur en obrir-se i sincronitza la memòria local i els
índexs de cerca. La recàrrega conserva les quantitats de línies locals pendents.
La pantalla explica quan no hi ha reserves vigents dins de l'empresa i les
propietats permeses. Es mantenen els filtres de dates del loader original.
Les regressions Node executen ara també el patch real de `PosDB` i el hook
d'obertura de `ReservationListScreen`, comprovant llistat, cerca per hoste
sense accents i per habitació, recàrrega i conservació de quantitats.
No s'ha comprovat la configuració ni les reserves de la base de l'usuari.

## Selector bloquejat durant la recàrrega

La recàrrega ja no s'espera dins d'`onWillStart`: s'inicia amb la pantalla
muntada. El selector conserva el botó de sortir mentre consulta el servidor.
Els errors RPC o de processament es mostren a la pantalla amb opció de tornar
ho a provar, i una petició sense resposta té un límit de deu segons. Es
comprova també que la resposta sigui una llista abans de modificar la memòria.
Les regressions Node cobreixen resposta correcta, rebuig RPC, resposta de
format incorrecte i timeout, sense bloquejar la inicialització de la pantalla.
El log HTTP 200 facilitat no confirma per si sol si hi havia un error RPC o
JavaScript; aquesta causa concreta requereix la resposta o la consola del
navegador. La sortida del worker amb `request_count` no prova que la consulta
hagi fallat.
