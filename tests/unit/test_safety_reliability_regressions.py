from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

import pytest

import origin_com_automation.com.origin_api as origin_api
from origin_com_automation.com.origin_api import OriginController


class InlineWorker:
    def submit(self, fn, *, timeout=None):
        return fn()


class ProjectApp:
    Version = "10.1.0.178"
    IsModified = False

    def __init__(self):
        self.Visible = None
        self.exit_calls = 0
        self.execute_scripts: list[str] = []
        self.loads: list[tuple[str, bool]] = []
        self.saves: list[str] = []
        self.new_project_calls = 0

    def Exit(self):
        self.exit_calls += 1
        return True

    def Execute(self, script):
        self.execute_scripts.append(script)
        return True

    def Load(self, path, readonly):
        self.loads.append((str(Path(path).resolve()), readonly))
        return True

    def Run(self):
        return True

    def Save(self, path):
        candidate = Path(path)
        self.saves.append(str(candidate.resolve()))
        candidate.write_bytes(b"validated-candidate-project" + b"x" * 128)
        return True

    def NewProject(self):
        self.new_project_calls += 1
        return True


class CandidateLoadFailureApp(ProjectApp):
    def Load(self, path, readonly):
        resolved = str(Path(path).resolve())
        self.loads.append((resolved, readonly))
        return ".codex-candidate-" not in Path(path).name


class MutatingSourceApp(ProjectApp):
    def __init__(self, source: Path, replacement: bytes):
        super().__init__()
        self.source = source
        self.replacement = replacement

    def NewProject(self):
        self.new_project_calls += 1
        if self.new_project_calls == 2:
            self.source.write_bytes(self.replacement)
        return True


def _started_controller(app: ProjectApp) -> OriginController:
    snapshots = iter([set(), {101}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
        sleep_fn=lambda _: None,
    )
    assert controller.start(progid="Origin.Application", attach=False).success
    return controller


def _open_source(controller: OriginController, source: Path, content: bytes) -> None:
    source.write_bytes(content)
    working = source.with_name("working.opju")
    result = controller.open_project(
        source_path=str(source),
        working_copy_path=str(working),
    )
    assert result.success, result.to_dict()


def _replace_source(controller: OriginController, source: Path, expected: bytes):
    return controller.save_and_replace_source(
        source_path=str(source),
        overwrite=True,
        allow_source_overwrite=True,
        expected_source_sha256=sha256(expected).hexdigest(),
    )


def test_source_replace_sha_mismatch_does_not_create_a_candidate(tmp_path):
    app = ProjectApp()
    controller = _started_controller(app)
    source = tmp_path / "source.opju"
    original = b"original-project" + b"o" * 128
    _open_source(controller, source, original)

    result = controller.save_and_replace_source(
        source_path=str(source),
        overwrite=True,
        allow_source_overwrite=True,
        expected_source_sha256=sha256(b"different-authorized-version").hexdigest(),
    )

    assert result.success is False
    assert result.error_code == "SOURCE_CHANGED"
    assert result.data["actual"]["sha256"] == sha256(original).hexdigest()
    assert source.read_bytes() == original
    assert app.saves == []
    assert not list(tmp_path.glob(".source.codex-candidate-*.opju"))
    assert not list(tmp_path.glob(".source.codex-backup-*.opju"))


def test_source_change_after_candidate_verification_cancels_commit(tmp_path, monkeypatch):
    source = tmp_path / "source.opju"
    original = b"original-project" + b"o" * 128
    external_update = b"external-update" + b"e" * 128
    app = MutatingSourceApp(source, external_update)
    controller = _started_controller(app)
    _open_source(controller, source, original)
    replace_calls = []

    monkeypatch.setattr(
        origin_api.os,
        "replace",
        lambda old, new: replace_calls.append((Path(old), Path(new))),
    )
    result = _replace_source(controller, source, original)

    assert result.success is False
    assert result.error_code == "SOURCE_CHANGED"
    assert source.read_bytes() == external_update
    assert replace_calls == []
    assert len(list(tmp_path.glob(".source.codex-candidate-*.opju"))) == 1
    assert not list(tmp_path.glob(".source.codex-backup-*.opju"))


def test_candidate_reopen_failure_never_replaces_the_source(tmp_path, monkeypatch):
    app = CandidateLoadFailureApp()
    controller = _started_controller(app)
    source = tmp_path / "source.opju"
    original = b"original-project" + b"o" * 128
    _open_source(controller, source, original)
    replace_calls = []

    monkeypatch.setattr(
        origin_api.os,
        "replace",
        lambda old, new: replace_calls.append((Path(old), Path(new))),
    )
    result = _replace_source(controller, source, original)

    assert result.success is False
    assert result.error_code == "PROJECT_SAVE_UNCONFIRMED"
    assert "could not reopen" in result.error_message
    assert source.read_bytes() == original
    assert replace_calls == []
    assert len(result.artifacts) == 1
    assert result.artifacts[0].kind == "origin_project_candidate"
    assert Path(result.artifacts[0].path).is_file()
    assert not list(tmp_path.glob(".source.codex-backup-*.opju"))


class LockedFileError(PermissionError):
    winerror = 32


def test_locked_source_reports_file_locked_and_preserves_recovery_files(tmp_path, monkeypatch):
    app = ProjectApp()
    controller = _started_controller(app)
    source = tmp_path / "source.opju"
    original = b"original-project" + b"o" * 128
    _open_source(controller, source, original)

    def locked_replace(old, new):
        raise LockedFileError("The source is open without delete sharing")

    monkeypatch.setattr(origin_api.os, "replace", locked_replace)
    result = _replace_source(controller, source, original)

    assert result.success is False
    assert result.error_code == "FILE_LOCKED"
    assert source.read_bytes() == original
    artifact_paths = {artifact.kind: Path(artifact.path) for artifact in result.artifacts}
    assert artifact_paths["origin_project_candidate"].is_file()
    assert artifact_paths["origin_project_backup"].read_bytes() == original


def test_atomic_replace_os_error_preserves_source_candidate_and_backup(tmp_path, monkeypatch):
    app = ProjectApp()
    controller = _started_controller(app)
    source = tmp_path / "source.opju"
    original = b"original-project" + b"o" * 128
    _open_source(controller, source, original)

    def failed_replace(old, new):
        raise OSError("atomic replacement failed")

    monkeypatch.setattr(origin_api.os, "replace", failed_replace)
    result = _replace_source(controller, source, original)

    assert result.success is False
    assert result.error_message == "atomic replacement failed"
    assert source.read_bytes() == original
    artifact_paths = {artifact.kind: Path(artifact.path) for artifact in result.artifacts}
    assert artifact_paths["origin_project_candidate"].is_file()
    assert artifact_paths["origin_project_backup"].read_bytes() == original


class MissingBeginSessionApp:
    Version = "10.1.0.178"

    def __init__(self):
        self.Visible = None
        self.exit_calls = 0

    def Exit(self):
        self.exit_calls += 1
        return True


class RejectedBeginSessionApp(MissingBeginSessionApp):
    def __init__(self):
        super().__init__()
        self.begin_session_calls = 0

    def BeginSession(self):
        self.begin_session_calls += 1
        return False


@pytest.mark.parametrize("app_type", [MissingBeginSessionApp, RejectedBeginSessionApp])
def test_owned_si_activation_is_rejected_before_dispatch(app_type):
    app = app_type()
    dispatch_calls = []

    def dispatch(progid, attach):
        dispatch_calls.append((progid, attach))
        return app

    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=dispatch,
        process_snapshot=lambda: set(),
        sleep_fn=lambda _: None,
    )

    result = controller.start(
        progid="Origin.ApplicationSI",
        attach=False,
        exclusive=True,
    )

    assert result.success is False
    assert result.error_code == "EXCLUSIVE_REQUIRES_ATTACH"
    assert dispatch_calls == []
    assert app.exit_calls == 0
    assert controller.session_id is None
    assert controller._exclusive is False


@pytest.mark.parametrize("app_type", [MissingBeginSessionApp, RejectedBeginSessionApp])
def test_failed_attached_si_lock_never_exits_the_user_instance(app_type):
    app = app_type()
    snapshots = iter([{55}, {55}])
    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=lambda progid, attach: app,
        process_snapshot=lambda: next(snapshots),
        sleep_fn=lambda _: None,
    )

    result = controller.start(
        progid="Origin.ApplicationSI",
        attach=True,
        exclusive=True,
    )

    assert result.success is False
    assert result.error_code == "OWNERSHIP_UNVERIFIED"
    assert app.exit_calls == 0
    assert controller.session_id is None


def test_shutdown_fails_when_the_confirmed_owned_pid_does_not_exit():
    app = ProjectApp()
    state = {"activated": False}

    def dispatch(progid, attach):
        state["activated"] = True
        return app

    def snapshot():
        return {55, 101} if state["activated"] else {55}

    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=dispatch,
        process_snapshot=snapshot,
        sleep_fn=lambda _: None,
    )
    started = controller.start(progid="Origin.Application", attach=False)
    assert started.success is True
    assert started.data["observed_new_pid"] == 101
    assert started.data["pid_binding_confirmed"] is False

    result = controller.shutdown()

    assert app.exit_calls == 0
    assert app.execute_scripts[-2:] == [
        "doc -s;",
        "def timerproc { exit; } timer 1;",
    ]
    assert result.success is False
    assert result.error_code == "SHUTDOWN_UNCONFIRMED"
    assert result.data["pid"] == 101
    assert result.data["pids_after"] == [55, 101]


class PartialSwitchLoadFailureApp(ProjectApp):
    def __init__(self):
        super().__init__()
        self.load_calls = 0

    def Load(self, path, readonly):
        self.load_calls += 1
        self.loads.append((str(Path(path).resolve()), readonly))
        if self.load_calls == 2:
            raise RuntimeError("load failed after Origin switched projects")
        return True


def test_failed_project_switch_invalidates_the_previous_source_authorization(tmp_path):
    app = PartialSwitchLoadFailureApp()
    controller = _started_controller(app)
    source_a = tmp_path / "source-a.opju"
    source_b = tmp_path / "source-b.opju"
    content_a = b"source-a-project" + b"a" * 128
    content_b = b"source-b-project" + b"b" * 128
    source_a.write_bytes(content_a)
    source_b.write_bytes(content_b)

    first = controller.open_project(
        source_path=str(source_a),
        working_copy_path=str(tmp_path / "working-a.opju"),
    )
    failed_switch = controller.open_project(
        source_path=str(source_b),
        working_copy_path=str(tmp_path / "working-b.opju"),
    )
    replace_old_source = controller.save_and_replace_source(
        source_path=str(source_a),
        overwrite=True,
        allow_source_overwrite=True,
        expected_source_sha256=sha256(content_a).hexdigest(),
    )

    assert first.success is True
    assert failed_switch.success is False
    assert controller._source_path is None
    assert controller._project_path is None
    assert replace_old_source.error_code == "NO_PROTECTED_SOURCE"
    assert source_a.read_bytes() == content_a
    assert app.saves == []


def test_post_commit_metadata_error_rolls_back_the_authorized_source(tmp_path, monkeypatch):
    app = ProjectApp()
    controller = _started_controller(app)
    source = tmp_path / "source.opju"
    original = b"original-project" + b"o" * 128
    _open_source(controller, source, original)
    original_digest = sha256(original).hexdigest()
    real_metadata = origin_api._project_file_metadata
    raised = False

    def fail_once_after_commit(path):
        nonlocal raised
        metadata = real_metadata(path)
        if (
            Path(path).resolve() == source.resolve()
            and metadata["sha256"] != original_digest
            and not raised
        ):
            raised = True
            raise PermissionError("post-commit metadata read denied")
        return metadata

    monkeypatch.setattr(origin_api, "_project_file_metadata", fail_once_after_commit)

    result = _replace_source(controller, source, original)

    assert raised is True
    assert result.success is False
    assert result.error_code == "SOURCE_REPLACE_VALIDATION_FAILED"
    assert source.read_bytes() == original
    candidate_artifacts = [
        Path(artifact.path)
        for artifact in result.artifacts
        if artifact.kind == "origin_project_candidate"
    ]
    assert candidate_artifacts and candidate_artifacts[0].is_file()


class BrokenFingerprintApp(ProjectApp):
    @property
    def WorksheetPages(self):
        raise RuntimeError("project page audit failed")


def test_source_replace_fails_closed_when_project_fingerprint_cannot_be_read(tmp_path):
    app = BrokenFingerprintApp()
    controller = _started_controller(app)
    source = tmp_path / "source.opju"
    original = b"original-project" + b"o" * 128
    _open_source(controller, source, original)

    result = _replace_source(controller, source, original)

    assert result.success is False
    assert result.error_code == "COM_ERROR"
    assert "project page audit failed" in result.error_message
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".source.codex-backup-*.opju"))


class ServerExecutionFailure(RuntimeError):
    hresult = -2146959355


def test_failed_com_activation_reports_unbound_new_pid_without_terminating_it():
    state = {"activated": False}
    terminated_pids = []

    def dispatch(progid, attach):
        state["activated"] = True
        raise ServerExecutionFailure("COM server execution failed")

    def snapshot():
        if state["activated"]:
            return {101}
        return set()

    def terminate(pid):
        terminated_pids.append(pid)

    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=dispatch,
        process_snapshot=snapshot,
        process_terminator=terminate,
        sleep_fn=lambda _: None,
    )

    result = controller.start(progid="Origin.Application", attach=False)

    assert result.success is False
    assert result.error_code == "CO_E_SERVER_EXEC_FAILURE"
    assert result.data["pids_before"] == []
    assert result.data["pids_after"] == [101]
    assert result.data["new_pids"] == [101]
    assert result.data["activation_cleanup_attempted"] is False
    assert result.data["activation_cleanup_confirmed"] is False
    assert result.data["pids_after_cleanup"] == [101]
    assert result.data["pid_binding_confirmed"] is False
    assert terminated_pids == []
    assert any("not terminated" in warning for warning in result.warnings)
    assert controller.session_id is None


def test_failed_attach_activation_never_terminates_an_ambiguous_new_pid():
    state = {"dispatched": False}
    terminated_pids = []

    def dispatch(progid, attach):
        state["dispatched"] = True
        raise ServerExecutionFailure("SI activation failed")

    def snapshot():
        return {55, 101} if state["dispatched"] else {55}

    controller = OriginController(
        worker=InlineWorker(),
        dispatch_factory=dispatch,
        process_snapshot=snapshot,
        process_terminator=terminated_pids.append,
        sleep_fn=lambda _: None,
    )

    result = controller.start(progid="Origin.ApplicationSI", attach=True)

    assert result.success is False
    assert result.data["new_pids"] == [101]
    assert result.data["activation_cleanup_attempted"] is False
    assert result.data["activation_cleanup_confirmed"] is False
    assert result.data["pids_after_cleanup"] == [55, 101]
    assert terminated_pids == []


class StructureCollection:
    def __init__(self, items=()):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        if isinstance(index, str):
            return next((item for item in self.items if item.Name == index), None)
        return self.items[index]


class StructureColumn:
    Units = ""
    Comments = ""

    def __init__(self, index, name, long_name, designation):
        self.Index = index
        self.Name = name
        self.LongName = long_name
        self.PlotDesignation = designation
        self.Range = f"[WSe2Benchmark]Data!Col({name})"

    def GetDatasetName(self):
        return f"WSe2Benchmark_{self.Name}"


class StructureWorksheet:
    Name = "Data"
    LongName = "Data"
    Index = 0

    def __init__(self, *, rows=26, cols=13, ion_long_name="Ion"):
        self.Rows = rows
        self.Cols = cols
        self.Columns = StructureCollection(
            [
                StructureColumn(0, "A", "Lch", 3),
                StructureColumn(1, "B", ion_long_name, 0),
                StructureColumn(2, "C", "Plot label", 4),
                StructureColumn(3, "D", "Alternate label", 4),
            ]
        )
        self.DataObjectBases = self.Columns


class StructurePlot:
    Name = "WSe2Benchmark_B"
    TypeName = "Unknow"
    Range = "[Ion_vs_Lch]1!Plot(1)"

    def __init__(self, label_column):
        self.label_column = label_column

    def GetDatasetName(self):
        return self.Name

    def GetNumProp(self, name):
        return 1 if name == "label.show" else 0

    def GetStrProp(self, name):
        return f"WSe2Benchmark_{self.label_column}" if name == "label.form" else ""


class StructureGraphLayer:
    Name = "Layer1"
    LongName = ""
    Index = 0

    def __init__(self, label_column):
        self.DataPlots = StructureCollection([StructurePlot(label_column)])
        self.variables = {}
        self.substitutions = {
            "%(1,@W)": "WSe2Benchmark",
            "%(1,@WS)": "Data",
            "%(1X,@D)": "WSe2Benchmark_A",
            "%(1X,@R)": "A",
            "%(1X,@L)": "Lch",
            "%(1Y,@D)": "WSe2Benchmark_B",
            "%(1Y,@R)": "B",
            "%(1Y,@L)": "Ion",
            "%(1L,@D)": f"WSe2Benchmark_{label_column}",
            "%(1L,@R)": label_column,
            "%(1L,@L)": "Plot label" if label_column == "C" else "Alternate label",
        }

    def Execute(self, command):
        for variable, token in re.findall(r'(cx[0-9a-f]+\d+)\$="([^"]*)";', command):
            self.variables[variable] = self.substitutions.get(token, token)
        return True

    def LTStr(self, name):
        return self.variables.get(name, "")


class StructureMatrixLayer:
    Name = "MData"
    LongName = "MData"
    Index = 0

    def __init__(self, rows, cols):
        self.Rows = rows
        self.Cols = cols


class StructurePage:
    def __init__(self, name, layers):
        self.Name = name
        self.LongName = name
        self.Layers = StructureCollection(layers)


class StructureApp:
    def __init__(
        self,
        *,
        rows=26,
        cols=13,
        ion_long_name="Ion",
        label_column="C",
        matrix_rows=4,
        matrix_cols=5,
    ):
        self.sheet = StructureWorksheet(
            rows=rows,
            cols=cols,
            ion_long_name=ion_long_name,
        )
        self.graph_layer = StructureGraphLayer(label_column)
        self.matrix_layer = StructureMatrixLayer(matrix_rows, matrix_cols)
        self.WorksheetPages = StructureCollection(
            [StructurePage("WSe2Benchmark", [self.sheet])]
        )
        self.GraphPages = StructureCollection(
            [StructurePage("Ion_vs_Lch", [self.graph_layer])]
        )
        self.MatrixPages = StructureCollection(
            [StructurePage("MatrixBook", [self.matrix_layer])]
        )

    def FindWorksheet(self, name):
        return self.sheet


def test_project_fingerprint_includes_worksheet_dimensions_and_column_labels():
    baseline = origin_api._project_structure_fingerprint(StructureApp())

    assert baseline != origin_api._project_structure_fingerprint(StructureApp(rows=0, cols=0))
    assert baseline != origin_api._project_structure_fingerprint(
        StructureApp(ion_long_name="Ion changed")
    )


def test_project_fingerprint_includes_dataplot_role_sources():
    baseline = origin_api._project_structure_fingerprint(StructureApp(label_column="C"))

    assert baseline != origin_api._project_structure_fingerprint(StructureApp(label_column="D"))


def test_project_fingerprint_includes_matrix_dimensions():
    baseline = origin_api._project_structure_fingerprint(StructureApp())

    assert baseline != origin_api._project_structure_fingerprint(
        StructureApp(matrix_rows=0, matrix_cols=0)
    )
