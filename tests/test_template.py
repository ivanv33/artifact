import pytest

from artifact.template import TemplateError, render


def test_render_params_substitution():
    body = "Hello {{ params.user }}!"
    assert render(body, params={"user": "alice"}, inputs={}) == "Hello alice!"


def test_render_inputs_substitution():
    body = "Read {{ inputs.events.json }}"
    assert render(body, params={}, inputs={"events.json": "/abs/path"}) == "Read /abs/path"


def test_render_multiple_substitutions():
    body = "{{ params.a }}/{{ params.b }}/{{ inputs.x }}"
    out = render(body, params={"a": "1", "b": "2"}, inputs={"x": "/x"})
    assert out == "1/2//x"


def test_render_tolerates_whitespace():
    body = "{{params.user}} and {{  params.user  }}"
    assert render(body, params={"user": "a"}, inputs={}) == "a and a"


def test_render_unknown_param_raises():
    with pytest.raises(TemplateError, match="params.missing"):
        render("{{ params.missing }}", params={}, inputs={})


def test_render_unknown_input_raises():
    with pytest.raises(TemplateError, match="inputs.missing"):
        render("{{ inputs.missing }}", params={}, inputs={})


def test_render_leaves_non_placeholder_braces_alone():
    body = "{ not a placeholder } and { {single braces} }"
    assert render(body, params={}, inputs={}) == body


def test_render_coerces_scalar_params_to_string():
    body = "{{ params.n }} {{ params.ok }}"
    assert render(body, params={"n": 42, "ok": True}, inputs={}) == "42 True"
