"""Compatibility adapters from legacy FigureSpec to the workflow kernel."""

from __future__ import annotations

from pathlib import Path

from .figurespec import FigureSpec
from .spec import (
    AnalysisStep,
    PlotStep,
    RowRange,
    RowSelection,
    ScientificContract,
    SourceSpec,
    WorkflowOutputs,
    WorkflowQA,
    WorkflowSpec,
    ExecutionPolicy,
)


def figure_to_workflow_spec(spec: FigureSpec) -> WorkflowSpec:
    """Convert a legacy FigureSpec without changing its public digest or semantics."""

    source_path = str(Path(spec.input.path).expanduser().resolve())
    import_mode = "project" if spec.route == "restyle_project" else spec.input.source_mode
    source = SourceSpec(
        id="input",
        path=source_path,
        worksheet_ref=spec.input.worksheet_ref,
        sheet_name=spec.input.sheet_name,
        has_header=spec.input.has_header,
        import_mode=import_mode,
    )
    analyses = []
    for item in spec.analyses:
        selection = RowSelection()
        if item.row_end >= item.row_start:
            selection = RowSelection(
                ranges=[RowRange(start=item.row_start, end=item.row_end)]
            )
        analyses.append(
            AnalysisStep(
                id=item.id,
                method=item.method,
                worksheet_ref=item.worksheet_ref,
                x_column=item.x_column,
                y_columns=[item.y_column],
                options=dict(item.options),
                selection=selection,
                backend_policy=(
                    "external_explicit" if item.backend == "python" else "origin_native_preferred"
                ),
                create_operation=item.create_operation,
                recalculate_mode=item.recalculate_mode,
            )
        )
    plots = [
        PlotStep(
            id=item.id,
            graph_type=item.graph_type,
            roles=dict(item.roles),
            graph_name=item.graph_name,
            allow_unverified=item.allow_unverified,
        )
        for item in spec.plots
    ]
    derivative = next(
        (item for item in spec.analyses if item.method.strip().lower() == "derivative"),
        None,
    )
    has_fit = any(
        item.method.strip().lower() in {"linear_fit", "polynomial_fit", "nonlinear_fit"}
        for item in spec.analyses
    )
    science = ScientificContract(
        input_units={"x": "unspecified", "y": "unspecified"},
        fit_method="origin_default" if has_fit else None,
        derivative_method=(
            str(derivative.options.get("derivative_method", "origin_default"))
            if derivative is not None
            else None
        ),
        derivative_order=(
            int(derivative.options.get("order", 1)) if derivative is not None else None
        ),
    )
    return WorkflowSpec(
        # FigureSpec historically accepts analysis without a separate scientific
        # unit/branch contract; keep that compatibility while using WorkflowSpec.
        intent="custom",
        sources=[source],
        scientific_contract=science,
        analyses=analyses,
        plots=plots,
        outputs=WorkflowOutputs(
            project_path=str(Path(spec.outputs.project_path).expanduser().resolve()),
            overwrite=spec.outputs.overwrite,
            exports=[item.model_copy(deep=True) for item in spec.outputs.exports],
        ),
        execution=ExecutionPolicy(
            backend_policy=(
                "external_explicit"
                if any(item.backend == "python" for item in spec.analyses)
                else "origin_native_preferred"
            ),
            fail_fast=True,
            checkpoint_policy="none",
        ),
        qa=WorkflowQA(
            critical_columns=list(spec.qa.critical_columns),
            minimum_rows=spec.qa.minimum_rows,
            expected_colors=list(spec.qa.expected_colors),
            reopen_project=spec.qa.reopen_project,
            require_connector=spec.route == "data_to_project" and spec.input.source_mode == "linked",
        ),
        visible=spec.visible,
    )
