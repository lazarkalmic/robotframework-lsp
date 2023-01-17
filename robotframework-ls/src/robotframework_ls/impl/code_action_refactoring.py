from typing import Set, Iterable, Any, List

from robotframework_ls.impl.protocols import (
    ICompletionContext,
    IRobotDocument,
    IRobotToken,
)
from robocorp_ls_core.lsp import (
    CommandTypedDict,
    Range,
    TextEditTypedDict,
    WorkspaceEditTypedDict,
    WorkspaceEditParamsTypedDict,
    CodeActionTypedDict,
)


def _wrap_edits_in_snippet(
    completion_context: ICompletionContext,
    title,
    text_edits: List[TextEditTypedDict],
    kind: str,
) -> CodeActionTypedDict:
    changes = {completion_context.doc.uri: text_edits}
    edit: WorkspaceEditTypedDict = {"changes": changes}
    edit_params: WorkspaceEditParamsTypedDict = {"edit": edit, "label": title}
    command: CommandTypedDict = {
        "title": title,
        "command": "robot.applyCodeAction",
        "arguments": [{"apply_snippet": edit_params}],
    }
    return {"title": title, "kind": kind, "command": command}


def _create_local_variable_refactoring(
    completion_context: ICompletionContext,
    select_range: Range,
) -> Iterable[CodeActionTypedDict]:
    doc: IRobotDocument = completion_context.doc

    line = select_range.start.line
    col = select_range.start.character
    endline = select_range.end.line
    endcol = select_range.end.character

    if line == endline and col != endcol:
        contents = doc.get_range(line, col, endline, endcol)

        token_info = completion_context.get_current_token()
        if token_info:
            curr_node_line_0_based = token_info.node.lineno - 1
            from robotframework_ls.robot_config import get_arguments_separator
            from robotframework_ls.robot_config import (
                create_convert_keyword_format_func,
            )
            import re

            format_name = create_convert_keyword_format_func(completion_context.config)
            set_var_name = format_name("Set Variable")
            indent = "    "
            line_contents = completion_context.doc.get_line(curr_node_line_0_based)
            found = re.match("[\s]+", line_contents)
            if found:
                indent = found.group()

            sep = get_arguments_separator(completion_context)

            tok: IRobotToken = token_info.token
            changes: List[TextEditTypedDict] = [
                {
                    "range": {
                        "start": {"line": curr_node_line_0_based, "character": 0},
                        "end": {"line": curr_node_line_0_based, "character": 0},
                    },
                    "newText": "%s${${0:variable}}=%s%s%s%s\n"
                    % (indent, sep, set_var_name, sep, contents),
                },
                {
                    "range": {
                        "start": {"line": tok.lineno - 1, "character": col},
                        "end": {
                            "line": tok.lineno - 1,
                            "character": endcol,
                        },
                    },
                    "newText": "${${0:variable}}",
                },
            ]
            yield _wrap_edits_in_snippet(
                completion_context,
                "Extract to local variable",
                changes,
                "refactor.extract",
            )


def code_action_refactoring(
    completion_context: ICompletionContext,
    select_range: Range,
    only: Set[str],
) -> Iterable[CodeActionTypedDict]:
    """
    Used to do refactorings.
    """
    from robotframework_ls.impl import ast_utils

    current_section: Any = completion_context.get_ast_current_section()
    if ast_utils.is_keyword_section(current_section) or ast_utils.is_testcase_section(
        current_section
    ):
        if only and (
            "refactor" in only
            or "refactor.extract" in only
            or "refactor.extract.local" in only
        ):
            yield from _create_local_variable_refactoring(
                completion_context, select_range
            )