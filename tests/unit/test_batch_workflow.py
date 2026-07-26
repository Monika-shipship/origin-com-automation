from pathlib import Path

import pytest

from origin_com_automation.workflows.batch import BatchPlanError, build_batch_plan, execute_batch


def test_batch_plan_is_sorted_explicit_and_collision_free(tmp_path):
    for name in ["b.csv", "a.csv"]:
        (tmp_path / name).write_text("x,y\n1,2\n", encoding="utf-8")
    plan = build_batch_plan(
        files=[str(tmp_path / "b.csv"), str(tmp_path / "a.csv")],
        output_root=str(tmp_path / "out"),
        preserve_order=False,
    )
    assert [Path(item.input_path).name for item in plan.items] == ["a.csv", "b.csv"]
    assert len({item.output_dir for item in plan.items}) == 2


def test_batch_plan_rejects_duplicate_files(tmp_path):
    source = tmp_path / "a.csv"
    source.write_text("x,y\n1,2\n", encoding="utf-8")
    with pytest.raises(BatchPlanError, match="unique"):
        build_batch_plan(files=[str(source), str(source)], output_root=str(tmp_path / "out"))


def test_batch_execution_is_serial_and_honors_stop_policy(tmp_path):
    files = []
    for name in ["a.csv", "b.csv", "c.csv"]:
        path = tmp_path / name
        path.write_text("x,y\n1,2\n", encoding="utf-8")
        files.append(str(path))
    plan = build_batch_plan(files=files, output_root=str(tmp_path / "out"))
    calls = []

    def executor(item):
        calls.append(Path(item.input_path).name)
        return {"success": len(calls) < 2}

    result = execute_batch(plan, executor, on_error="stop")
    assert calls == ["a.csv", "b.csv"]
    assert result["completed"] == 2
    assert result["stopped_early"] is True
