import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSER_SPEC = importlib.util.spec_from_file_location(
    "parse_dsmr_contract_export", ROOT / "scripts" / "parse_dsmr_contract_export.py"
)
assert PARSER_SPEC is not None
PARSER = importlib.util.module_from_spec(PARSER_SPEC)
assert PARSER_SPEC.loader is not None
PARSER_SPEC.loader.exec_module(PARSER)

SPEC = importlib.util.spec_from_file_location(
    "reconcile_dsmr_contract_export_invoice",
    ROOT / "scripts" / "reconcile_dsmr_contract_export_invoice.py",
)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DsmrInvoiceReconciliationTests(unittest.TestCase):
    def test_invoice_overlap_exposes_offsetting_variable_and_fixed_differences(self):
        report = PARSER.parse_contract_export(
            ROOT / "docs" / "information" / "energy_contracts_export_dsmr.txt",
            "2025-06-01",
            "2026-06-01",
        )
        invoice = MODULE.load_json(
            ROOT
            / "docs"
            / "evidence"
            / "ecopower-invoice-baseline-2025-06-01_2026-05-31.json"
        )

        result = MODULE.build_reconciliation(report, invoice)

        self.assertEqual(result["period"]["calendar_day_count"], 365)
        self.assertEqual(result["dsmr"]["stored_day_count"], 364)
        self.assertAlmostEqual(result["dsmr"]["total_eur_incl_vat"], 2828.84)
        self.assertAlmostEqual(result["invoice"]["total_eur_incl_vat"], 2853.21)
        self.assertAlmostEqual(result["difference_dsmr_minus_invoice"]["total_eur"], -24.37)
        self.assertLess(result["difference_dsmr_minus_invoice"]["variable_eur"], -100.0)
        self.assertGreater(result["difference_dsmr_minus_invoice"]["fixed_eur"], 75.0)
        self.assertEqual(result["assessment"], "TOTAL_CLOSE_COMPONENT_MISMATCH")
        self.assertFalse(result["independent_component_validation"])

    def test_safety_boundary_remains_read_only(self):
        report = PARSER.parse_contract_export(
            ROOT / "docs" / "information" / "energy_contracts_export_dsmr.txt",
            "2025-06-01",
            "2026-06-01",
        )
        invoice = MODULE.load_json(
            ROOT
            / "docs"
            / "evidence"
            / "ecopower-invoice-baseline-2025-06-01_2026-05-31.json"
        )
        result = MODULE.build_reconciliation(report, invoice)

        self.assertTrue(result["safety"]["read_only"])
        self.assertFalse(result["safety"]["contract_change_allowed"])
        self.assertFalse(result["safety"]["physical_writes_allowed"])


if __name__ == "__main__":
    unittest.main()
