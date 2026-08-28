"""HTTP model validation tests for Metrics Builder inputs."""

import pytest
from pydantic import ValidationError

from app.schemas.metric_builder_schema import MetricBuilderPreviewRequest


def test_preview_request_forbids_unknown_properties() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MetricBuilderPreviewRequest(
            metric_code="events",
            intent="count_event",
            unknown=True,
        )


def test_preview_request_rejects_unknown_intent() -> None:
    with pytest.raises(ValidationError, match="Input should be"):
        MetricBuilderPreviewRequest(metric_code="events", intent="median")


def test_preview_request_rejects_control_characters() -> None:
    with pytest.raises(ValidationError, match="control characters"):
        MetricBuilderPreviewRequest(
            metric_code="events\nforged",
            intent="count_event",
        )


def test_preview_request_rejects_silent_derived_label_collision() -> None:
    with pytest.raises(ValidationError, match="Duplicate derived label"):
        MetricBuilderPreviewRequest(
            metric_code="events",
            intent="count_by_label",
            labels={"status": "$.other"},
            label_fields=["$.status"],
        )


def test_effective_labels_enforces_the_configured_collection_limit() -> None:
    request = MetricBuilderPreviewRequest(
        metric_code="events",
        intent="sum_value",
        value_path="$.amount",
        labels={"first": "$.first", "second": "$.second"},
    )

    with pytest.raises(ValueError, match="At most 1"):
        request.effective_labels(max_labels=1)
