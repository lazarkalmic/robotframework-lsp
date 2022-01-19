import pytest


def test_keyword_completions_builtin(workspace, libspec_manager):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case1", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case1.robot")
    doc = workspace.put_doc("case1.robot", doc.source + "\n    should be")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    assert sorted([comp["label"] for comp in completions]) == [
        "Length Should Be (BuiltIn)",
        "Should Be Empty (BuiltIn)",
        "Should Be Equal (BuiltIn)",
        "Should Be Equal As Integers (BuiltIn)",
        "Should Be Equal As Numbers (BuiltIn)",
        "Should Be Equal As Strings (BuiltIn)",
        "Should Be True (BuiltIn)",
    ]


def test_keyword_completions_format(workspace, libspec_manager):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.robot_config import RobotConfig
    from robotframework_ls.impl.robot_lsp_constants import (
        OPTION_ROBOT_COMPLETION_KEYWORDS_FORMAT,
        OPTION_ROBOT_COMPLETION_KEYWORDS_FORMAT_FIRST_UPPER,
    )

    workspace.set_root("case1", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case1.robot")
    doc = workspace.put_doc("case1.robot", doc.source + "\n    should be")

    config = RobotConfig()
    config.update(
        {
            OPTION_ROBOT_COMPLETION_KEYWORDS_FORMAT: OPTION_ROBOT_COMPLETION_KEYWORDS_FORMAT_FIRST_UPPER
        }
    )
    assert (
        config.get_setting(OPTION_ROBOT_COMPLETION_KEYWORDS_FORMAT, str, "")
        == OPTION_ROBOT_COMPLETION_KEYWORDS_FORMAT_FIRST_UPPER
    )

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws, config=config)
    )
    assert sorted([comp["label"] for comp in completions]) == [
        "Length should be (BuiltIn)",
        "Should be empty (BuiltIn)",
        "Should be equal (BuiltIn)",
        "Should be equal as integers (BuiltIn)",
        "Should be equal as numbers (BuiltIn)",
        "Should be equal as strings (BuiltIn)",
        "Should be true (BuiltIn)",
    ]


@pytest.mark.parametrize("separator", ("${/}", "/", "\\"))
@pytest.mark.parametrize("use_config", (True, False))
def test_keyword_completions_directory_separator(
    workspace, libspec_manager, use_config, separator
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.robot_config import RobotConfig
    import sys

    if sys.platform != "win32" and separator == "\\":
        return

    workspace.set_root("case_inner_keywords", libspec_manager=libspec_manager)
    doc = workspace.put_doc("case_root.robot")
    doc.source = f"""
*** Settings ***
Resource    inner{separator}case_inner.robot


*** Test Cases ***
Testing Completion Here
    Check with ke"""

    if use_config:
        config = RobotConfig()
    else:
        config = None

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws, config=config)
    )
    assert sorted([comp["label"] for comp in completions]) == [
        "Check with keyword at inner (case_inner)"
    ]


def test_keyword_completions_builtin_after_space(workspace, libspec_manager):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robocorp_ls_core.protocols import IDocument

    workspace.set_root("case1", libspec_manager=libspec_manager)
    doc: IDocument = workspace.get_doc("case1.robot")
    doc = workspace.put_doc("case1.robot", doc.source + "\n    should be ")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    assert sorted([comp["label"] for comp in completions]) == [
        "Length Should Be (BuiltIn)",
        "Should Be Empty (BuiltIn)",
        "Should Be Equal (BuiltIn)",
        "Should Be Equal As Integers (BuiltIn)",
        "Should Be Equal As Numbers (BuiltIn)",
        "Should Be Equal As Strings (BuiltIn)",
        "Should Be True (BuiltIn)",
    ]


def test_keyword_completions_builtin_after_space_before_newline(
    workspace, libspec_manager
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case1", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case1.robot")
    doc = workspace.put_doc("case1.robot", doc.source + "\n    should be \n")

    line, _col = doc.get_last_line_col()
    line_contents = doc.get_line(line - 1)

    completions = keyword_completions.complete(
        CompletionContext(
            doc, workspace=workspace.ws, line=line - 1, col=len(line_contents)
        )
    )

    assert sorted([comp["label"] for comp in completions]) == [
        "Length Should Be (BuiltIn)",
        "Should Be Empty (BuiltIn)",
        "Should Be Equal (BuiltIn)",
        "Should Be Equal As Integers (BuiltIn)",
        "Should Be Equal As Numbers (BuiltIn)",
        "Should Be Equal As Strings (BuiltIn)",
        "Should Be True (BuiltIn)",
    ]


def test_keyword_completions_changes_user_library(
    data_regression, workspace, cases, libspec_manager, workspace_dir
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    import time
    from os.path import os

    cases.copy_to("case1", workspace_dir)

    workspace.set_root(workspace_dir, libspec_manager=libspec_manager)
    doc = workspace.get_doc("case1.robot")
    doc = workspace.put_doc("case1.robot", doc.source + "\n    verify")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    data_regression.check(completions, basename="keyword_completions_1")

    time.sleep(1)  # Make sure that the mtime changes enough in the filesystem

    library_py = os.path.join(workspace_dir, "case1_library.py")
    with open(library_py, "r") as stream:
        contents = stream.read()

    contents += """
def verify_changes(model=10):
    pass
"""
    with open(library_py, "w") as stream:
        stream.write(contents)
    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    assert sorted(completion["label"] for completion in completions) == [
        "Verify Another Model (case1_library)",
        "Verify Changes (case1_library)",
        "Verify Model (case1_library)",
    ]


@pytest.mark.parametrize(
    "library_import", ["case1_library", "case1_library.py", "__FULL_PATH__"]
)
def test_keyword_completions_user_library(
    data_regression, workspace, cases, libspec_manager, library_import, workspace_dir
):
    import os.path
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls_tests.fixtures import LIBSPEC_1
    from robocorp_ls_core import uris

    cases.copy_to("case1", workspace_dir)

    workspace.set_root(workspace_dir, libspec_manager=libspec_manager)
    doc = workspace.get_doc("case1.robot")

    if library_import == "__FULL_PATH__":
        case1_robot_path = uris.to_fs_path(doc.uri)
        case1_py_path = os.path.join(
            os.path.dirname(case1_robot_path), "case1_library.py"
        )
        library_import = case1_py_path

    new_source = doc.source.replace("case1_library", library_import)
    new_source = new_source + "\n    verify"
    doc = workspace.put_doc("case1.robot", new_source)

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    data_regression.check(completions, basename="keyword_completions_1")

    # Now, let's put a .libspec file in the workspace and check whether
    # it has priority over the auto-generated spec file.
    with open(os.path.join(workspace_dir, "new_spec.libspec"), "w") as stream:
        stream.write(LIBSPEC_1)
    libspec_manager.synchronize_workspace_folders()

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    data_regression.check(completions, basename="keyword_completions_2_new")


def test_keyword_completions_case1(
    data_regression, workspace, cases, libspec_manager, workspace_dir
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    cases.copy_to("case1", workspace_dir)

    workspace.set_root(workspace_dir, libspec_manager=libspec_manager)
    doc = workspace.get_doc("case1.robot")
    doc = workspace.put_doc("case1.robot", doc.source + "\n    case1_library.")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    data_regression.check(completions, basename="keyword_completions_1_all")


def test_keyword_completions_user_in_robot_file(
    data_regression, workspace, cases, libspec_manager
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root(cases.get_path("case2"), libspec_manager=libspec_manager)
    doc = workspace.get_doc("case2.robot")
    doc = workspace.put_doc("case2.robot", doc.source + "\n    my equ")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    data_regression.check(
        completions, basename="keyword_completions_user_in_robot_file"
    )


def test_keyword_completions_from_resource_files(
    data_regression, workspace, tmpdir, cases, libspec_manager
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.impl.robot_lsp_constants import OPTION_ROBOT_VARIABLES
    from robotframework_ls.robot_config import RobotConfig

    config = RobotConfig()
    config.update({"robot": {"variables": {"ext_folder": cases.get_path("ext")}}})
    assert config.get_setting(OPTION_ROBOT_VARIABLES, dict, {}) == {
        "ext_folder": cases.get_path("ext")
    }

    workspace.set_root(cases.get_path("case3"), libspec_manager=libspec_manager)
    doc = workspace.get_doc("case3.robot")
    doc = workspace.put_doc("case3.robot", doc.source + "\n    equal redef")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws, config=config)
    )
    data_regression.check(
        completions, basename="keyword_completions_from_resource_files"
    )


def test_keyword_completions_from_recursively_included_resource_files(
    data_regression, workspace, cases, libspec_manager
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root(cases.get_path("case4"), libspec_manager=libspec_manager)
    doc = workspace.get_doc("case4.robot")
    doc = workspace.put_doc("case4.robot", doc.source + "\n    equal redef")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    data_regression.check(
        completions, basename="keyword_completions_from_recursively_resource_files"
    )


def test_keyword_completions_builtin_duplicated(workspace, cases, libspec_manager):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root(cases.get_path("case4"), libspec_manager=libspec_manager)
    doc = workspace.get_doc("case4.robot")
    doc = workspace.put_doc("case4.robot", doc.source + "\n    should be equal")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    found = [
        completion["label"]
        for completion in completions
        if completion["label"].lower() == "should be equal (builtin)"
    ]

    assert len(found) == 1, f'Found: {[x["label"] for x in completions]}'


def test_keyword_completions_fixture(workspace, libspec_manager):
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.impl import keyword_completions

    workspace.set_root("case2", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case2.robot")
    doc = workspace.put_doc(
        "case2.robot", doc.source + "\n    [Teardown]    my_Equal red"
    )

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    found = [
        completion["label"]
        for completion in completions
        if completion["label"].lower() == "my equal redefined (case2)"
    ]

    assert len(found) == 1, f'Found: {[x["label"] for x in completions]}'


def test_keyword_completions_settings_fixture(workspace, libspec_manager):
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.impl import keyword_completions

    workspace.set_root("case2", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case2.robot")
    doc = workspace.put_doc(
        "case2.robot", doc.source + "\n*** Keywords ***\nTeardown    my_Equal red"
    )

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    found = [
        completion["label"]
        for completion in completions
        if completion["label"].lower() == "my equal redefined (case2)"
    ]

    assert len(found) == 1, f'Found: {[x["label"] for x in completions]}'


def test_keyword_completions_bdd_prefix(workspace, libspec_manager, data_regression):
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.impl import keyword_completions

    workspace.set_root("case2", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case2.robot")
    doc = workspace.put_doc(
        "case2.robot", doc.source + "\n*** Keywords ***\nTeardown    WHEN my_Equal red"
    )

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    found = [
        completion
        for completion in completions
        if completion["label"].lower() == "my equal redefined (case2)"
    ]
    assert len(found) == 1, f'Found: {[x["label"] for x in completions]}'
    data_regression.check(found)


def test_keyword_completions_template(workspace, libspec_manager):
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.impl import keyword_completions

    workspace.set_root("case2", libspec_manager=libspec_manager)
    doc = workspace.put_doc("case2.robot")
    doc.source = """
*** Keywords ***
My Equal Redefined
    [Arguments]         ${arg1}     ${arg2}
    Should Be Equal     ${arg1}     ${arg2}

*** Settings ***
Test Template    my eq"""

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    found = [
        completion["label"]
        for completion in completions
        if completion["label"].lower() == "my equal redefined (case2)"
    ]

    assert len(found) == 1, f'Found: {[x["label"] for x in completions]}'


def test_keyword_completions_resource_does_not_exist(
    workspace, libspec_manager, data_regression
):
    from robotframework_ls.robot_config import RobotConfig
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case4", libspec_manager=libspec_manager)
    doc = workspace.put_doc("case4.robot")

    doc.source = """*** Settings ***
Library    DoesNotExist
Library    .
Library    ..
Library    ../
Resource    does_not_exist.txt
Resource    ${foo}/does_not_exist.txt
Resource    ../does_not_exist.txt
Resource    .
Resource    ..
Resource    ../
Resource    ../../does_not_exist.txt
Resource    case4resource.txt

*** Test Cases ***
Test
    case4resource3."""

    config = RobotConfig()
    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws, config=config)
    )

    data_regression.check(completions)


def test_keyword_completions_library_prefix(
    workspace, libspec_manager, data_regression
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case4", libspec_manager=libspec_manager)
    doc = workspace.put_doc("case4.robot")

    doc.source = """*** Settings ***
Library    String
Library    Collections
Resource    case4resource.txt

*** Test Cases ***
Test
    case4resource3."""

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    data_regression.check(
        completions, basename="test_keyword_completions_library_prefix_1"
    )

    doc.source = """*** Settings ***
Library    String
Library    Collections
Resource    case4resource.txt

*** Test Cases ***
Test
    case4resource3.Another"""

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    data_regression.check(
        completions, basename="test_keyword_completions_library_prefix_2"
    )

    doc.source = """*** Settings ***
Library    Collections

*** Test Cases ***
Test
    Collections.Append To Lis"""

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    assert [completion["label"] for completion in completions] == [
        "Append To List (Collections)"
    ]


def test_keyword_completions_with_stmt(workspace, libspec_manager):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case4", libspec_manager=libspec_manager)
    doc = workspace.put_doc("case4.robot")

    doc.source = """*** Settings ***
Library    Collections    WITH NAME    Col1

*** Test Cases ***
Test
    Col1.Append To Lis"""

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    assert [completion["label"] for completion in completions] == [
        "Append To List (Collections)"
    ]


def test_keyword_completions_respect_pythonpath(
    workspace, cases, libspec_manager, data_regression
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.robot_config import RobotConfig
    from robotframework_ls.impl.robot_lsp_constants import OPTION_ROBOT_PYTHONPATH

    case4_path = cases.get_path("case4")

    # Note how we are accessing case4resource.txt while the workspace is set for case3.

    config = RobotConfig()
    config.update({"robot": {"pythonpath": [case4_path]}})
    assert config.get_setting(OPTION_ROBOT_PYTHONPATH, list, []) == [case4_path]
    libspec_manager.config = config

    workspace.set_root(cases.get_path("case3"), libspec_manager=libspec_manager)
    doc = workspace.put_doc("case3.robot")
    doc.source = """*** Settings ***
Resource    case4resource.txt

*** Test Cases ***
Can use resource keywords
    [Documentation]      Checks that we can have a resource
    ...                  including another resource.
    My Equal Redefined   2   2
    Yet Another Equ"""

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws, config=config)
    )

    data_regression.check(completions)


def test_typing_not_shown(libspec_manager, workspace, data_regression, workspace_dir):
    from robocorp_ls_core import uris
    from os.path import os
    from robotframework_ls_tests.fixtures import LIBSPEC_3
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robocorp_ls_core.lsp import TextDocumentItem

    workspace_dir_a = os.path.join(workspace_dir, "workspace_dir_a")
    os.makedirs(workspace_dir_a)
    with open(os.path.join(workspace_dir_a, "my.libspec"), "w") as stream:
        stream.write(LIBSPEC_3)
    libspec_manager.add_workspace_folder(uris.from_fs_path(workspace_dir_a))
    assert (
        libspec_manager.get_library_info(
            "case3_library",
            False,
            uris.from_fs_path(os.path.join(workspace_dir_a, "my.robot")),
        )
        is not None
    )

    workspace.set_root(workspace_dir, libspec_manager=libspec_manager)

    doc = workspace.ws.put_document(TextDocumentItem("temp_doc.robot", text=""))
    doc.source = """*** Settings ***
Library    case3_library

*** Test Cases ***
Can use resource keywords
    Case Verify"""

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )

    data_regression.check(completions)


def test_keyword_completions_circular_imports(workspace, libspec_manager):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case_circular", libspec_manager=libspec_manager)
    doc = workspace.get_doc("main.robot")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    assert sorted([comp["label"] for comp in completions]) == [
        "My Keyword 1 (keywords1)",
        "My Keyword 2 (keywords2)",
    ]


def test_keyword_completions_lib_with_params(workspace, libspec_manager, cases):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.robot_config import RobotConfig
    from robotframework_ls.impl.robot_lsp_constants import OPTION_ROBOT_PYTHONPATH

    workspace.set_root("case_params_on_lib", libspec_manager=libspec_manager)

    caseroot = cases.get_path("case_params_on_lib")
    config = RobotConfig()
    config.update(
        {
            "robot": {
                "pythonpath": [caseroot],
                "libraries": {"libdoc": {"needsArgs": ["*"]}},
            }
        }
    )
    assert config.get_setting(OPTION_ROBOT_PYTHONPATH, list, []) == [caseroot]
    libspec_manager.config = config

    doc = workspace.get_doc("case_params_on_lib.robot")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    assert sorted([comp["label"] for comp in completions]) == [
        "Foo Method (LibWithParams)"
    ]


def test_simple_with_params(workspace, libspec_manager, cases):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.robot_config import RobotConfig
    from robotframework_ls.impl.robot_lsp_constants import OPTION_ROBOT_PYTHONPATH

    workspace.set_root("case_params_on_lib", libspec_manager=libspec_manager)

    caseroot = cases.get_path("case_params_on_lib")
    config = RobotConfig()
    config.update(
        {
            "robot": {
                "pythonpath": [caseroot],
                "libraries": {"libdoc": {"needsArgs": ["*"]}},
            }
        }
    )
    assert config.get_setting(OPTION_ROBOT_PYTHONPATH, list, []) == [caseroot]
    libspec_manager.config = config

    doc = workspace.get_doc("case_params_on_lib.robot")

    completions = keyword_completions.complete(
        CompletionContext(doc, workspace=workspace.ws)
    )
    assert sorted([comp["label"] for comp in completions]) == [
        "Foo Method (LibWithParams)"
    ]


def test_keyword_completions_on_keyword_arguments(workspace, libspec_manager):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case1", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case1.robot")
    doc = workspace.put_doc(
        "case1.robot", doc.source + "\n    Run keyword if    ${var}    Should Be"
    )

    completion_context = CompletionContext(doc, workspace=workspace.ws)

    completions = keyword_completions.complete(completion_context)
    assert sorted([comp["label"] for comp in completions]) == [
        "Length Should Be (BuiltIn)",
        "Should Be Empty (BuiltIn)",
        "Should Be Equal (BuiltIn)",
        "Should Be Equal As Integers (BuiltIn)",
        "Should Be Equal As Numbers (BuiltIn)",
        "Should Be Equal As Strings (BuiltIn)",
        "Should Be True (BuiltIn)",
    ]


def test_keyword_completions_on_template_name(workspace, libspec_manager):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case1", libspec_manager=libspec_manager)
    doc = workspace.put_doc("case1.robot")
    doc.source = """
*** Keyword ***
Example Keyword

*** Test Cases **
Normal test case
    Example keyword    first argument    second argument

Templated test case
    [Template]    Example ke"""
    completion_context = CompletionContext(doc, workspace=workspace.ws)

    completions = keyword_completions.complete(completion_context)
    assert [comp["label"] for comp in completions] == ["Example Keyword (case1)"]


@pytest.mark.parametrize(
    "server_port",
    [
        8270,  # default port
        0,  # let OS decide port
    ],
)
def test_keyword_completions_remote_library(workspace, libspec_manager, remote_library):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case_remote_library", libspec_manager=libspec_manager)
    doc = workspace.get_doc("case_remote.robot")
    doc = workspace.put_doc(
        "case_remote.robot",
        doc.source.replace("${PORT}", str(remote_library)) + "\n    a.V",
    )

    completion_context = CompletionContext(doc, workspace=workspace.ws)

    completions = keyword_completions.complete(completion_context)
    assert sorted([comp["label"] for comp in completions]) == [
        "Stop Remote Server (Remote)",
        "Validate String (Remote)",
        "Verify That Remote Is Running (Remote)",
    ]


@pytest.mark.parametrize("needs_args", ["LibWithParams", "*", "none"])
def test_keyword_completions_library_with_params_with_space(
    workspace, libspec_manager, needs_args
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.robot_config import RobotConfig

    config = RobotConfig()
    config.update({"robot": {"libraries": {"libdoc": {"needsArgs": [needs_args]}}}})
    libspec_manager.config = config

    workspace.set_root("case_params_on_lib", libspec_manager=libspec_manager)
    doc = workspace.put_doc("case_params_on_lib.robot")

    doc.source = """
*** Settings ***
Library    LibWithParams    some_param=foo    WITH NAME    Lib

*** Test Case  ***
My Test
    Lib.Foo"""

    completion_context = CompletionContext(doc, workspace=workspace.ws, config=config)
    completions = keyword_completions.complete(completion_context)

    if needs_args == "none":
        assert not completions
    else:
        assert len(completions) == 1
        assert sorted([comp["label"] for comp in completions]) == [
            "Foo Method (LibWithParams)"
        ]


def test_keyword_completions_library_with_params_resolves_var(
    workspace, libspec_manager
):
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext
    from robotframework_ls.robot_config import RobotConfig

    config = RobotConfig()
    config.update(
        {
            "robot.libraries": {"libdoc": {"needsArgs": ["LibWithParams"]}},
            "robot.variables": {"param_val": "foo"},
        }
    )
    libspec_manager.config = config

    workspace.set_root("case_params_on_lib", libspec_manager=libspec_manager)
    doc = workspace.put_doc("case_params_on_lib.robot")

    doc.source = """
*** Settings ***
Library    LibWithParams    some_param=${param_val}    WITH NAME    Lib

*** Test Case  ***
My Test
    Lib.Foo"""

    completion_context = CompletionContext(doc, workspace=workspace.ws, config=config)
    completions = keyword_completions.complete(completion_context)

    assert len(completions) == 1
    assert sorted([comp["label"] for comp in completions]) == [
        "Foo Method (LibWithParams)"
    ]


@pytest.mark.parametrize("lib_param", ["bar", "foo"])
def test_code_analysis_same_lib_with_alias_with_params(
    workspace, libspec_manager, cases, lib_param
):
    from robotframework_ls.robot_config import RobotConfig
    from robotframework_ls.impl.robot_lsp_constants import OPTION_ROBOT_PYTHONPATH
    from robotframework_ls.impl import keyword_completions
    from robotframework_ls.impl.completion_context import CompletionContext

    workspace.set_root("case_params_on_lib", libspec_manager=libspec_manager)

    caseroot = cases.get_path("case_params_on_lib")
    config = RobotConfig()
    config.update(
        {
            "robot": {
                "pythonpath": [caseroot],
                "libraries": {"libdoc": {"needsArgs": ["*"]}},
            }
        }
    )
    assert config.get_setting(OPTION_ROBOT_PYTHONPATH, list, []) == [caseroot]
    libspec_manager.config = config

    doc = workspace.put_doc("case_params_on_lib.robot")
    doc.source = f"""
*** Settings ***
Library   LibWithParams    some_param=foo    WITH NAME   LibFoo
Library   LibWithParams    some_param=bar    WITH NAME   LibBar

*** Test Case ***
My Test
    Lib{lib_param.title()}.{lib_param}"""

    completion_context = CompletionContext(doc, workspace=workspace.ws, config=config)
    completions = keyword_completions.complete(completion_context)
    assert len(completions) == 1
    assert sorted([comp["label"] for comp in completions]) == [
        f"{lib_param.title()} Method (LibWithParams)"
    ]
