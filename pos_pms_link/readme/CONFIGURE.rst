Configuració del càrrec a reserva
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

En instal·lar o actualitzar el mòdul es crea «Càrrec Hotel» per a cada
empresa existent, amb «Fraccionar transaccions» activat i sense diari.
Es reutilitza un mètode actiu amb el mateix nom i configuració; no es
modifiquen mètodes existents ni s'assigna automàticament a cap TPV.

#. Seleccioneu el mètode de l’empresa del TPV al camp de mètode de pagament per
   carregar a la reserva de la configuració del TPV.
#. El tiquet necessita un client. Si encara no en té, el mòdul assigna
   el contacte de la reserva en seleccionar-la. Si no té contacte associat,
   cal seleccionar-lo manualment. Per carregar a reserva, deixeu desactivada
   l'opció «Factura»; la reserva es facturarà des del PMS.

Manteniu els mètodes de targeta i efectiu amb els seus diaris corresponents.
Odoo impedeix modificar un mètode utilitzat per sessions obertes; en aquest
cas cal tancar i validar les sessions afectades abans de modificar-lo.
