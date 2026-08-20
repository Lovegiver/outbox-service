import pytest

from app.metrics_engine.prometheus_renderer import (
    PrometheusMetricStateSample,
    PrometheusRenderingError,
    escape_prometheus_label_value,
    merge_prometheus_labels,
    normalize_business_labels,
    normalize_prometheus_metric_name,
    render_prometheus_metric_states,
)


def _sample(
    *,
    metric_code: str = "products.sold-total",
    value: float = 1,
    labels: dict | None = None,
    project_name: str = "shop",
    event_type_code: str = "product.sold",
) -> PrometheusMetricStateSample:
    return PrometheusMetricStateSample(
        metric_code=metric_code,
        value=value,
        business_labels=labels or {},
        project_name=project_name,
        event_type_code=event_type_code,
    )


def test_normalize_metric_name_replaces_invalid_characters() -> None:
    assert (
        normalize_prometheus_metric_name("9products.sold-total")
        == "ob1_9products_sold_total"
    )


def test_normalize_metric_name_does_not_duplicate_ob1_prefix() -> None:
    assert (
        normalize_prometheus_metric_name("ob1_products.sold")
        == "ob1_products_sold"
    )


def test_merge_labels_adds_platform_labels_and_sorts_all_labels() -> None:
    labels = merge_prometheus_labels(
        business_labels={"region": "west", "country": "FR"},
        project_name="shop",
        event_type_code="product.sold",
    )

    assert list(labels.items()) == [
        ("country", "FR"),
        ("ob1_event_type", "product.sold"),
        ("ob1_project", "shop"),
        ("region", "west"),
    ]


def test_reject_business_label_using_reserved_prefix() -> None:
    with pytest.raises(PrometheusRenderingError, match="reserved prefix"):
        normalize_business_labels({"ob1_project": "forged"})


def test_reject_invalid_business_label_name() -> None:
    with pytest.raises(PrometheusRenderingError, match="valid Prometheus"):
        normalize_business_labels({"sales-region": "west"})


def test_escape_label_value_handles_backslash_quote_and_newline() -> None:
    assert escape_prometheus_label_value('a\\b"c\nd') == 'a\\\\b\\"c\\nd'


def test_renderer_groups_series_and_emits_one_type_line_per_family() -> None:
    document = render_prometheus_metric_states(
        [
            _sample(value=12, labels={"country": "FR"}),
            _sample(value=4, labels={"country": "BE"}),
        ]
    )

    assert document.count("# TYPE ob1_products_sold_total counter") == 1
    assert (
        'ob1_products_sold_total{country="BE",'
        'ob1_event_type="product.sold",ob1_project="shop"} 4'
    ) in document
    assert (
        'ob1_products_sold_total{country="FR",'
        'ob1_event_type="product.sold",ob1_project="shop"} 12'
    ) in document


def test_renderer_returns_empty_body_without_state() -> None:
    assert render_prometheus_metric_states([]) == ""


def test_non_empty_document_has_final_newline() -> None:
    assert render_prometheus_metric_states([_sample()]).endswith("\n")


def test_renderer_rejects_negative_counter_value() -> None:
    with pytest.raises(PrometheusRenderingError, match="negative"):
        render_prometheus_metric_states([_sample(value=-1)])


def test_renderer_rejects_metric_codes_colliding_after_normalization() -> None:
    with pytest.raises(PrometheusRenderingError, match="normalize to the same"):
        render_prometheus_metric_states(
            [
                _sample(metric_code="sales-total", labels={"country": "FR"}),
                _sample(metric_code="sales.total", labels={"country": "BE"}),
            ]
        )


def test_renderer_orders_families_and_series_deterministically() -> None:
    samples = [
        _sample(metric_code="z.metric", labels={"country": "FR"}),
        _sample(metric_code="a.metric", labels={"country": "FR"}),
        _sample(metric_code="a.metric", labels={"country": "BE"}),
    ]

    forward = render_prometheus_metric_states(samples)
    reverse = render_prometheus_metric_states(list(reversed(samples)))

    assert forward == reverse
    assert forward.index("# TYPE ob1_a_metric") < forward.index(
        "# TYPE ob1_z_metric"
    )
    assert forward.index('country="BE"') < forward.index('country="FR"')
