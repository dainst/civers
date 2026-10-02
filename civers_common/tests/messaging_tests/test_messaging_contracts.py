"""Tests for the Command / Result messaging contracts."""

import pytest
from pydantic import ValidationError

from civers_common.messaging import Command, Result, ResultStatus


class _SampleCommand(Command):
    url: str
    priority: int = 1


class TestCommand:
    def test_carries_request_id(self):
        cmd = _SampleCommand(request_id="r1", url="https://example.com")
        assert cmd.request_id == "r1"
        assert cmd.url == "https://example.com"
        assert cmd.priority == 1

    def test_is_frozen(self):
        cmd = _SampleCommand(request_id="r1", url="https://example.com")
        with pytest.raises(ValidationError):
            cmd.url = "https://changed.com"

    def test_request_id_required(self):
        with pytest.raises(ValidationError):
            _SampleCommand(url="https://example.com")
    


class TestResult:
    def test_ok_factory(self):
        result = Result.ok(archive_path="/tmp/a.wacz", artifacts_created=["warc"])
        assert result.success_status is ResultStatus.COMPLETE
        assert result.data["archive_path"] == "/tmp/a.wacz"
        assert result.error is None

    def test_fail_factory(self):
        result = Result.fail("boom", error_type="CrawlError")
        assert result.success_status is ResultStatus.FAILED
        assert result.error == "boom"
        assert result.error_type == "CrawlError"
        assert result.data == {}

    def test_default_data_is_independent(self):
        a = Result.ok()
        b = Result.ok()
        a.data["x"] = 1
        assert b.data == {}


class TestResultStatus:
    """One field carries the outcome, so nothing can contradict anything else.

    A handler can finish its job without doing all of it — an archive that captured
    three of four artifacts is not a failure, but calling it a plain success loses the
    fact that something is absent.
    """

    def test_ok_is_complete(self):
        assert Result.ok().success_status is ResultStatus.COMPLETE

    def test_fail_is_failed(self):
        assert Result.fail("boom").success_status is ResultStatus.FAILED

    def test_partial_is_usable_but_incomplete(self):
        result = Result.partial(artifacts_created=["warc"])

        assert result.success_status is ResultStatus.PARTIAL
        assert result.data["artifacts_created"] == ["warc"]

    def test_the_outcome_must_be_stated(self):
        """There is no default, because no outcome is the obvious one to assume."""
        with pytest.raises(ValidationError):
            Result()

    def test_the_field_is_not_optional(self):
        """The annotation must not promise a None a consumer would have to handle."""
        assert Result.model_fields["success_status"].annotation is ResultStatus
        assert Result.model_fields["success_status"].is_required()

    def test_there_is_no_separate_boolean_to_disagree_with_it(self):
        assert "success" not in Result.model_fields

    def test_an_unknown_outcome_is_refused(self):
        with pytest.raises(ValidationError):
            Result(success_status="mostly fine")

    def test_it_serialises_as_a_plain_string(self):
        assert Result.partial().model_dump(mode="json")["success_status"] == "partial"

    @pytest.mark.parametrize("status", list(ResultStatus))
    def test_every_state_round_trips(self, status):
        assert Result(success_status=status).success_status is status


class TestFailCarriesData:
    """The failure path is the one a consumer most needs facts from — what the work did
    manage to produce before giving up."""

    def test_fail_accepts_data_like_ok_and_partial(self):
        result = Result.fail(
            "no artifacts were produced",
            "archive_generation_failed",
            archive_path="/archives/r1",
            artifacts_created=[],
            failed_artifacts=["warc"],
        )

        assert result.success_status is ResultStatus.FAILED
        assert result.error == "no artifacts were produced"
        assert result.error_type == "archive_generation_failed"
        assert result.data["archive_path"] == "/archives/r1"
        assert result.data["failed_artifacts"] == ["warc"]

    def test_fail_without_data_is_unchanged(self):
        result = Result.fail("boom")
        assert result.data == {}
        assert result.error_type is None
