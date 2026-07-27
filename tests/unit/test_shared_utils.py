from hashlib import sha256

from pydantic import BaseModel

from origin_com_automation.utils.hashing import canonical_digest, sha256_file
from origin_com_automation.utils.runtime import StrictModel, controller_origin_version
from origin_com_automation.workflows.figurespec import FigureSpec, figure_spec_digest
from origin_com_automation.workflows.spec import WorkflowSpec, workflow_spec_digest


class SampleModel(BaseModel):
    name: str
    value: int


def test_sha256_file_streams_the_exact_file_content(tmp_path):
    path = tmp_path / "large.bin"
    content = (b"origin-com-automation" * 100_000) + b"tail"
    path.write_bytes(content)
    assert sha256_file(path, chunk_size=4096) == sha256(content).hexdigest()


def test_canonical_digest_is_stable_for_models_and_mapping_order():
    model = SampleModel(name="Ion", value=2260)
    assert canonical_digest(model) == canonical_digest({"value": 2260, "name": "Ion"})


def test_historical_workflow_digest_entry_points_use_canonical_digest(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    workflow = WorkflowSpec.model_validate(
        {
            "intent": "custom",
            "sources": [{"id": "data", "path": str(source)}],
            "outputs": {"project_path": str(tmp_path / "result.opju")},
        }
    )
    figure = FigureSpec.model_validate(
        {
            "route": "data_to_project",
            "input": {"path": str(source)},
            "outputs": {"project_path": str(tmp_path / "figure.opju")},
        }
    )
    assert workflow_spec_digest(workflow) == canonical_digest(workflow)
    assert figure_spec_digest(figure) == canonical_digest(figure)


def test_runtime_helpers_enforce_strict_models_and_version_fallback():
    class Input(StrictModel):
        value: int

    assert Input(value=1).value == 1
    assert controller_origin_version(type("Controller", (), {"origin_version": "10.1"})()) == "10.1"
    assert controller_origin_version(type("Controller", (), {"_origin_version": "10.0"})()) == "10.0"
    assert controller_origin_version(None, default="unknown") == "unknown"
