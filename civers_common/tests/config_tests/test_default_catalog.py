"""Deployment environments preserve the shared catalog and configured ME profiles."""

from pathlib import Path

from civers_common.configs.loaders import BaseYamlConfigLoader


NAMES = [
    "viamus2.gbv.de",
    "viamus.uni-goettingen.de",
    "sempub.ub.uni-heidelberg.de",
    "*.museum-digital.de",
    "arachne.dainst.org",
    "arachne.test.dainst.org",
    "field.idai.world",
]


def test_default_catalog_inherits_consistently_in_deployment_environments(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    monkeypatch.setenv("KAFKA_CONSUMER_GROUP_ID", "catalog-test")
    monkeypatch.setenv("CIVERS_API_URL", "http://localhost:8000")
    root = Path(__file__).resolve().parents[3] / "configs/data"
    for environment in ("development", "docker", "production"):
        for component in (
            "web_interface", "orchestrator", "archive_generator", "metadata_extractor",
            "change_detection",
        ):
            directory = root / component
            if not (directory / "environments" / f"{environment}.yaml").is_file():
                continue
            config = BaseYamlConfigLoader(directory, environment).load_raw()
            if component == "metadata_extractor":
                assert {d["name"] for d in config["domains"]} == {
                    *NAMES, "publications.dainst.org"
                }
                enabled = [d for d in config["domains"] if d.get("enabled", True)]
                assert {d["name"] for d in enabled} == {
                    "publications.dainst.org", "viamus2.gbv.de",
                    "field.idai.world", "arachne.dainst.org",
                }
                assert all(d.get("pipeline") for d in enabled)
            else:
                expected = list(NAMES)
                if environment == "docker" and component in {
                    "web_interface", "archive_generator", "orchestrator"
                }:
                    expected.append("example.com")
                assert [d["name"] for d in config["domains"]] == expected
            if component == "orchestrator":
                for domain in config["domains"]:
                    assert domain["workflow"] == (
                        "archive_and_metadata_workflow"
                        if domain["name"] == "arachne.test.dainst.org"
                        else "archive_generation_only_workflow"
                    )
