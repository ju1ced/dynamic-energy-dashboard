import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HacsLovelacePackageTests(unittest.TestCase):
    def test_hacs_manifest_points_to_single_dashboard_artifact(self):
        manifest = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "Dynamic Energy Shadow Dashboard")
        self.assertEqual(manifest["content_in_root"], False)
        self.assertEqual(manifest["filename"], "dynamic-energy-dashboard.js")
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
                self.assertNotIn(token, source)

    def test_card_renders_prospective_price_timeline_from_plan_entity(self):
        source = (ROOT / "dist" / "dynamic-energy-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("renderPriceTimeline(", source)
        self.assertIn("snapshot.prices.intervals", source)
        self.assertIn("snapshot.prices.referenceEurPerKwh", source)
        self.assertIn("Komende kwartierprijzen", source)

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
