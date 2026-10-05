"""Check combined publication results and CIVERS snapshot ID selection."""

import json
from dataclasses import asdict

import pytest

from storage_layer.storage_strategy import MultiStorageResult, StorageResult

pytestmark = [pytest.mark.unit]


def _rest(success=True, location="snap-rest-42"):
    return StorageResult(
        success=success, storage_type="civers_rest_api", storage_location=location
    )


def _other(success=True, location="somewhere-else"):
    return StorageResult(success=success, storage_type="s3", storage_location=location)


def _result(*results):
    return MultiStorageResult(
        overall_success=any(r.success for r in results), results=list(results)
    )


class TestSnapshotId:
    def test_comes_from_a_successful_rest_upload(self):
        """The web interface mints the id it can later serve against."""
        assert _result(_rest()).snapshot_id() == "snap-rest-42"

    def test_is_none_when_the_rest_backend_did_not_run(self):
        assert _result(_other()).snapshot_id() is None

    def test_is_none_when_the_rest_upload_failed(self):
        """A failed upload has no id to offer, so the caller keeps its own."""
        assert _result(_rest(success=False)).snapshot_id() is None

    def test_is_none_when_nothing_was_published(self):
        assert _result().snapshot_id() is None

    def test_ignores_other_backends_that_did_succeed(self):
        assert _result(_other(), _rest(success=False)).snapshot_id() is None

    def test_picks_the_rest_result_out_of_several(self):
        assert _result(_other(), _rest(), _other()).snapshot_id() == "snap-rest-42"


class TestItAlreadyAnswersWhatStorageOutcomeUsedTo:
    def test_which_backends_succeeded_and_failed(self):
        result = _result(_rest(), _other(success=False))

        assert result.get_successful_backends() == ["civers_rest_api"]
        assert result.get_failed_backends() == ["s3"]

    def test_it_flattens_to_json(self):
        """It travels in the result dict, so it has to survive serialisation."""
        json.dumps(asdict(_result(_rest(), _other(success=False))))
