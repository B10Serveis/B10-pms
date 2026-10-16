# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

MOSSOS_PAYMENT_TYPES = [
    ("DESTI", "DESTI - Payment at destination"),
    ("EFECT", "EFECT - Cash"),
    ("MOVIL", "MOVIL - Mobile payment"),
    ("OTRO", "OTRO - Other means of payment"),
    ("PLATF", "PLATF - Payment platform"),
    ("TARJT", "TARJT - Credit card"),
    ("TRANS", "TRANS - Bank transfer"),
    ("TREG", "TREG - Gift card"),
]

MOSSOS_PAYMENT_SOURCES = [
    ("payment", "Payment mode of the oldest receipt"),
    ("default", "Establishment default"),
]
