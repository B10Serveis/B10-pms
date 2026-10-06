"""Isolated regressions for the production methods; no database is required.

Run: python3 -m unittest discover -s pos_pms_link/tests -v
These doubles do not replace an Odoo integration test.
"""
import ast
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]


class Records(list):
    def filtered(self, fn):
        return Records(item for item in self if fn(item))


class UserError(Exception):
    pass


def load_class(filename, name, methods, base):
    tree = ast.parse((ROOT / 'models' / filename).read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    cls.bases = [ast.Name(id='Base', ctx=ast.Load())]
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in methods]
    for node in cls.body:
        node.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    scope = dict(Base=base, UserError=UserError, _=lambda text: text, defaultdict=defaultdict)
    exec(compile(module, str(ROOT / 'models' / filename), 'exec'), scope)
    return scope[name]


class OrderBase:
    def _process_order(self, *args):
        self.processed = True
        return 42

    def _export_for_ui(self, order):
        return {'id': 42}


Order = load_class('pos_order.py', 'PosOrder', ['_process_order', '_export_for_ui'], OrderBase)


class TestOrders(unittest.TestCase):
    def setUp(self):
        self.currency = NS(is_zero=lambda n: abs(n) < .005)
        self.reservation = NS(company_id=1, state='onboard', pms_property_id=5, currency_id=self.currency)
        self.method = NS(id=7, type='pay_later', company_id=1)
        config = NS(pay_on_reservation=True, pay_on_reservation_method_id=self.method,
                    reservation_allowed_propertie_ids=[5])
        self.session = NS(config_id=config, company_id=1,
                          currency_id=self.currency,
                          check_access_rights=lambda op: None, check_access_rule=lambda op: None)
        self.order = Order()
        self.order.processed = False
        self.charges = []
        self.order.browse = lambda id: NS(add_order_lines_to_reservation=self.charges.append)
        session_model = NS(browse=lambda id: NS(exists=lambda: self.session))
        reservation_model = NS(sudo=lambda: NS(browse=lambda id: NS(exists=lambda: self.reservation)))
        self.order.env = {'pos.session': session_model, 'pms.reservation': reservation_model}
        self.data = dict(pos_session_id=1, paid_on_reservation=True, pms_reservation_id=10,
                         amount_total=12, statement_ids=[[0, 0, dict(payment_method_id=7, amount=12)]])

    def process(self, draft=False):
        return self.order._process_order({'data': self.data}, draft, False)

    def test_final_charge_preserves_payload(self):
        self.assertEqual(self.process(), 42)
        self.assertEqual(self.data['pms_reservation_id'], 10)
        self.assertEqual(self.charges, [self.reservation])

    def test_draft_does_not_charge(self):
        self.data['statement_ids'] = []
        self.process(draft=True)
        self.assertEqual(self.charges, [])

    def test_other_company_rejected_before_processing(self):
        self.reservation.company_id = 2
        with self.assertRaises(UserError):
            self.process()
        self.assertFalse(self.order.processed)

    def test_other_property_rejected(self):
        self.reservation.pms_property_id = 6
        with self.assertRaises(UserError):
            self.process()

    def test_missing_reservation_rejected(self):
        self.reservation = False
        with self.assertRaises(UserError):
            self.process()

    def test_cancelled_reservation_rejected(self):
        self.reservation.state = 'cancel'
        with self.assertRaises(UserError):
            self.process()

    def test_partial_payment_rejected(self):
        self.data['statement_ids'][0][2]['amount'] = 6
        with self.assertRaises(UserError):
            self.process()

    def test_mixed_payment_rejected(self):
        self.data['statement_ids'].append([0, 0, dict(payment_method_id=8, amount=0)])
        with self.assertRaises(UserError):
            self.process()

    def test_invoice_rejected(self):
        self.data['to_invoice'] = True
        with self.assertRaises(UserError):
            self.process()

    def test_cash_method_rejected(self):
        self.method.type = 'cash'
        with self.assertRaises(UserError):
            self.process()

    def test_export_keeps_reservation(self):
        result = self.order._export_for_ui(NS(paid_on_reservation=True, pms_reservation_id=NS(id=10)))
        self.assertEqual(result['pms_reservation_id'], 10)
        self.assertTrue(result['paid_on_reservation'])


class SessionBase:
    def _accumulate_amounts(self, data):
        return data


Session = load_class('pos_session.py', 'PosSession', ['_accumulate_amounts'], SessionBase)


class TestAccounting(unittest.TestCase):
    def test_global_tax_rounding_is_per_order(self):
        session = Session()
        method = NS(split_transactions=False)
        session.config_id = NS(pay_on_reservation=True, pay_on_reservation_method_id=method)
        session.company_id = NS(tax_calculation_rounding_method='round_globally')
        tax = dict(id=1, account_id=2, tax_repartition_line_id=3, tag_ids=[],
                   amount=.004, base=.04, date_order='2026-10-06')
        line = dict(income_account_id=2, amount=.04, taxes=[tax], base_tags=(), date_order='2026-10-06')
        session.order_ids = Records([
            NS(paid_on_reservation=True, pms_reservation_id=1, is_invoiced=False, lines=[line], payment_ids=Records()),
            NS(paid_on_reservation=True, pms_reservation_id=1, is_invoiced=False, lines=[line], payment_ids=Records()),
            NS(paid_on_reservation=True, pms_reservation_id=1, is_invoiced=True, lines=[line]),
            NS(paid_on_reservation=False, pms_reservation_id=1, is_invoiced=False, lines=[line], payment_ids=Records()),
        ])
        session._prepare_line = lambda line: line
        def update(target, values, date, round=True):
            for key, value in values.items():
                target[key] += value
                target[key + '_converted'] += value
            return target
        session._update_amounts = update
        session._round_amounts = lambda values: {k: round(v, 2) for k, v in values.items()}
        sale_key = (2, 1, ((1, 2, 3),), ())
        tax_key = (2, 3, 1, ())
        data = dict(taxes={tax_key: dict(amount=.02, amount_converted=.02,
                                       base_amount=.16, base_amount_converted=.16)},
                    sales={sale_key: dict(amount=.16, amount_converted=.16)},
                    combine_receivables_pay_later={})
        result = session._accumulate_amounts(data)
        self.assertAlmostEqual(result['taxes'][tax_key]['amount'], .02)
        self.assertAlmostEqual(result['sales'][sale_key]['amount'], .08)
        self.assertAlmostEqual(result['taxes'][tax_key]['base_amount'], .08)


Loader = load_class('pos_session.py', 'PosSession',
                    ['_get_pos_ui_pms_reservation', '_loader_params_pms_reservation'], SessionBase)
Loader._loader_params_pms_reservation.__globals__['fields'] = NS(
    Date=NS(context_today=lambda record: '2026-10-06'))
Loader._get_pos_ui_pms_reservation.__globals__['expression'] = NS(
    AND=lambda domains: sum(domains, []))


class TestReservationLoader(unittest.TestCase):
    def setUp(self):
        self.loader = Loader()
        self.loader.ensure_one = lambda: None
        self.loader.check_access_rights = lambda operation: None
        self.loader.check_access_rule = lambda operation: None
        self.loader.company_id = NS(id=1)
        self.loader.config_id = NS(pay_on_reservation=True,
                                   reservation_allowed_propertie_ids=NS(ids=[5]))
        self.calls = []
        def search_read(**params):
            self.calls.append(params)
            return []
        model = NS(sudo=lambda: NS(search_read=search_read))
        class Environment(dict):
            user = NS(has_group=lambda group: True)
        self.loader.env = Environment({'pms.reservation': model})

    def test_caller_domain_cannot_replace_scope_or_fields(self):
        params = {'search_params': {'domain': [('id', '=', 99)], 'fields': ['access_token']}}
        self.assertEqual(self.loader._get_pos_ui_pms_reservation(params), [])
        domain = self.calls[0]['domain']
        self.assertIn(('company_id', '=', 1), domain)
        self.assertIn(('pms_property_id', 'in', [5]), domain)
        self.assertIn(('id', '=', 99), domain)
        self.assertNotIn('access_token', self.calls[0]['fields'])
        self.assertEqual(params['search_params']['fields'], ['access_token'])

    def test_non_pos_user_rejected_before_sudo(self):
        self.loader.env.user = NS(has_group=lambda group: False)
        with self.assertRaises(UserError):
            self.loader._get_pos_ui_pms_reservation({'search_params': {}})
        self.assertEqual(self.calls, [])

    def test_record_access_rejected_before_sudo(self):
        def denied(operation):
            raise UserError('Access denied')
        self.loader.check_access_rule = denied
        with self.assertRaises(UserError):
            self.loader._get_pos_ui_pms_reservation({'search_params': {}})
        self.assertEqual(self.calls, [])

    def test_disabled_config_does_not_load(self):
        self.loader.config_id.pay_on_reservation = False
        self.assertEqual(self.loader._get_pos_ui_pms_reservation({'search_params': {}}), [])
        self.assertEqual(self.calls, [])


Config = load_class('pos_config.py', 'PosConfig',
                    ['_check_reservation_configuration'], object)
Config._check_reservation_configuration.__globals__['ValidationError'] = UserError


class TestLegacyConfiguration(unittest.TestCase):
    def config(self, method):
        return NS(pay_on_reservation=True, pay_on_reservation_method_id=method,
                  company_id=1, reservation_allowed_propertie_ids=[])

    def test_legacy_cash_method_does_not_block_pos_opening(self):
        Config._check_reservation_configuration([
            self.config(NS(type='cash', company_id=1))
        ])

    def test_missing_method_does_not_block_pos_opening(self):
        Config._check_reservation_configuration([self.config(False)])

    def test_payment_from_other_company_still_rejected(self):
        with self.assertRaises(UserError):
            Config._check_reservation_configuration([
                self.config(NS(type='pay_later', company_id=2))
            ])
