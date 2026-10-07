"""Isolated regressions for the module-data payment provisioning method."""
import unittest
from types import SimpleNamespace as NS

from test_regressions import load_class


Method = load_class('pos_payment_method.py', 'PosPaymentMethod',
                    ['_create_default_hotel_payment_methods'], object)


class Methods:
    def __init__(self, values=None):
        self.values = list(values or [])

    def search(self, domain, limit=None):
        return [value for value in self.values
                if all(value.get(key, False) == expected
                       for key, operator, expected in domain)][:limit]

    def create(self, values):
        self.values.append(dict(values, active=True))


class TestDefaultPaymentMethod(unittest.TestCase):
    def provisioner(self, values=None):
        record = Method()
        methods = Methods(values)
        companies = NS(sudo=lambda: NS(search=lambda domain: [NS(id=1), NS(id=2)]))
        record.env = {'res.company': companies}
        record.sudo = lambda: NS(with_context=lambda **kwargs: methods)
        return record, methods

    def test_install_creates_one_per_company(self):
        record, methods = self.provisioner()
        record._create_default_hotel_payment_methods()
        self.assertEqual([value['company_id'] for value in methods.values], [1, 2])
        for value in methods.values:
            self.assertEqual(value['name'], 'Càrrec Hotel')
            self.assertTrue(value['split_transactions'])
            self.assertFalse(value['journal_id'])
            self.assertNotIn('config_ids', value)

    def test_upgrade_does_not_duplicate(self):
        record, methods = self.provisioner()
        record._create_default_hotel_payment_methods()
        record._create_default_hotel_payment_methods()
        self.assertEqual(len(methods.values), 2)

    def test_reuses_existing_valid_method(self):
        value = dict(name='Càrrec Hotel', company_id=1, split_transactions=True,
                     journal_id=False, active=True)
        record, methods = self.provisioner([value])
        record._create_default_hotel_payment_methods()
        self.assertEqual(len(methods.values), 2)
        self.assertEqual(methods.values[0], value)

    def test_does_not_modify_incompatible_or_archived_methods(self):
        values = [dict(name='Càrrec Hotel', company_id=1, split_transactions=False,
                       journal_id=7, active=True),
                  dict(name='Càrrec Hotel', company_id=2, split_transactions=True,
                       journal_id=False, active=False)]
        record, methods = self.provisioner(values)
        record._create_default_hotel_payment_methods()
        self.assertEqual(methods.values[:2], values)
        self.assertEqual(len(methods.values), 4)
