import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HacsLovelacePackageTests(unittest.TestCase):
    def test_hacs_manifest_points_to_single_dashboard_artifact(self):
        manifest = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "Dynamic Energy Shadow Dashboard")
        self.assertEqual(manifest["content_in_root"], False)
        self.assertEqual(manifest["filename"], "dynamic-energy-dashboard.js")
        self.assertEqual(manifest["homeassistant"], "2024.10.0")
        self.assertTrue((ROOT / "dist" / manifest["filename"]).is_file())

    def test_card_registers_picker_metadata_and_visual_form(self):
        source = (ROOT / "dist" / "dynamic-energy-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('customElements.define("dynamic-energy-shadow-card"', source)
        self.assertIn('type: "dynamic-energy-shadow-card"', source)
        self.assertIn("static getConfigForm()", source)
        self.assertIn('selector: { entity: {} }', source)

    def test_frontend_is_observation_only(self):
        source = (ROOT / "dist" / "dynamic-energy-dashboard.js").read_text(
            encoding="utf-8"
        )
        observer = source.split(
            "export class DynamicEnergyShadowCard", 1
        )[1].split("export function renderBlockedControlConfig", 1)[0]

        forbidden = (
            "callService(",
            ".callWS(",
            "hass.callApi(",
            "service:",
            "perform-action",
            "tap_action",
            "hold_action",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, observer)

    def test_separate_control_card_is_registered_and_hard_blocks_actuator_actions(self):
        source = (ROOT / "dist" / "dynamic-energy-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'customElements.define("dynamic-energy-control-config-card"', source
        )
        self.assertIn('type: "dynamic-energy-control-config-card"', source)
        self.assertIn("execution_allowed = false", source)
        self.assertIn("live actuator execution is not authorized", source)
        self.assertIn('actions: [{ stop: BLOCKED_STOP, error: false }]', source)

    def test_validation_card_is_registered_and_contains_no_write_api(self):
        source = (ROOT / "dist" / "dynamic-energy-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'customElements.define("dynamic-energy-validation-card"', source
        )
        self.assertIn('type: "dynamic-energy-validation-card"', source)
        validation = source.split(
            "export class DynamicEnergyValidationCard", 1
        )[1].split("function formatControlTime", 1)[0]
        for token in ("callService(", ".callWS(", "hass.callApi(", "data-action="):
            with self.subTest(token=token):
                self.assertNotIn(token, validation)

    def test_browser_fixture_includes_the_validation_card(self):
        fixture = (ROOT / "tests" / "browser" / "hacs-card-fixture.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('<dynamic-energy-validation-card id="validation-card"', fixture)
        self.assertIn("DynamicEnergyValidationCard", fixture)
        self.assertIn('validation_summary_entity: "sensor.validation_summary"', fixture)

    def test_card_renders_prospective_price_timeline_from_plan_entity(self):
        source = (ROOT / "dist" / "dynamic-energy-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("renderPriceTimeline(", source)
        self.assertIn("snapshot.prices.intervals", source)
        self.assertIn("snapshot.prices.referenceEurPerKwh", source)
        self.assertIn("Komende kwartierprijzen", source)
        self.assertIn("renderDailyPriceGraph(", source)
        self.assertIn("Kwartierprijzen per dag", source)
        self.assertIn('data-price-scroll-by="1"', source)
        self.assertIn("touch-action: pan-x pan-y", source)

    def test_readme_documents_hacs_and_gui_setup(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("HACS", readme)
        self.assertIn("Add custom repository", readme)
        self.assertIn("visual editor", readme.lower())
        self.assertIn("read-only", readme.lower())
        self.assertIn("EPEX Spot Data", readme)
        self.assertIn("Ecopower Dynamic Prices", readme)
        self.assertIn("integration_price_attribute: data", readme)
        self.assertIn("images/dynamic-energy-shadow-card.png", readme)
        self.assertTrue((ROOT / "images" / "dynamic-energy-shadow-card.png").is_file())

    def test_readme_documents_device_setup_guidance_and_primary_sources(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("SMA batterijconfiguratie", readme)
        self.assertIn("Smappee EV-configuratie", readme)
        self.assertIn("one active controller per actuator", readme)
        self.assertIn("https://manuals.sma.de/HM-20-ennexOS/en-US/12563269899.html", readme)
        self.assertIn("https://support.smappee.com/hc/en-gb/articles/4900468508692", readme)
        self.assertIn("performs no sma- or smappee-setting change", readme.lower())

    def test_package_version_matches_the_alpha_11_candidate(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(package["version"], "0.3.0-alpha.11")
        self.assertTrue(
            (ROOT / "docs" / "releases" / "v0.3.0-alpha.11-checklist.md").is_file()
        )

    def test_comparison_dashboard_view_is_read_only_and_uses_price_entities(self):
        view = json.loads(
            (ROOT / "deploy" / "home-assistant" / "dashboard-vergelijking-view.json")
            .read_text(encoding="utf-8")
        )
        text = json.dumps(view)

        self.assertEqual(view["type"], "sections")
        self.assertEqual(view["path"], "vergelijking")
        for forbidden in ("tap_action", "hold_action", "perform_action", "call-service", "service_data"):
            self.assertNotIn(forbidden, text)
        entities = set(re.findall(r'"((?:binary_)?sensor\.[a-z0-9_]+)"', text))
        self.assertTrue(entities)
        self.assertTrue(
            all(entity.split(".", 1)[1].startswith("ecopower_ecopower_") for entity in entities)
        )

    def test_readme_documents_only_supported_frontend_price_inputs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertNotIn("repository already retrieves", readme)
        self.assertNotIn("shadow-plan-rest-sensor", readme)
        self.assertNotIn("built-in REST integration", readme)
        self.assertIn("two supported frontend price inputs", readme.lower())

    def test_repository_includes_a_license(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

        self.assertIn("MIT License", license_text)

    def test_repository_includes_the_official_hacs_validation_action(self):
        workflow = (
            ROOT / ".github" / "workflows" / "hacs-validate.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "hacs/action@1ebf01c408f29afcb6406bd431bc98fd8cbb15aa", workflow
        )
        self.assertNotIn("hacs/action@main", workflow)
        self.assertIn(
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            workflow,
        )
        self.assertIn("pull_request:", workflow)
        self.assertIn("workflow_dispatch:", workflow)


if __name__ == "__main__":
    unittest.main()
