import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DashboardControlConfigurationTests(unittest.TestCase):
    def test_dashboard_exposes_mode_selector_and_configuration_view(self):
        index = (ROOT / "web-dashboard" / "index.html").read_text(encoding="utf-8")

        self.assertIn('data-view="configuration"', index)
        self.assertIn('data-operating-mode="monitor"', index)
        self.assertIn('data-operating-mode="simulation"', index)
        self.assertIn('data-operating-mode="active"', index)
        self.assertIn('id="operating-mode-status"', index)

    def test_configuration_ui_uses_non_executable_control_contract(self):
        app = (ROOT / "web-dashboard" / "app.js").read_text(encoding="utf-8")
        contract = (ROOT / "web-dashboard" / "control-config.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('configuration: "Configuratie"', app)
        self.assertIn("renderConfiguration", app)
        self.assertIn("requestOperatingMode", app)
        self.assertIn("serializeAutomationBundle", app)
        self.assertIn("live_activation_allowed: false", contract)
        self.assertIn('mode: "DRY_RUN_CONFIGURATION"', contract)
        self.assertIn("execution_allowed: false", contract)

    def test_configuration_frontend_has_no_mutating_transport(self):
        source = "\n".join(
            [
                (ROOT / "web-dashboard" / "app.js").read_text(encoding="utf-8"),
                (ROOT / "web-dashboard" / "control-config.js").read_text(
                    encoding="utf-8"
                ),
            ]
        )

        for token in (
            "callService",
            "callWS",
            'method: "POST"',
            'method: "PUT"',
            'method: "PATCH"',
            'method: "DELETE"',
            "new WebSocket",
            "mqtt.publish",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
