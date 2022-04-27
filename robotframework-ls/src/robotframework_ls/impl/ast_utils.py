import sys
from typing import (
    Iterator,
    Optional,
    List,
    Tuple,
    Any,
    Union,
    Hashable,
    Callable,
    Dict,
    Iterable,
    Sequence,
)

import ast as ast_module
from robocorp_ls_core.lsp import Error, RangeTypedDict, PositionTypedDict
from robocorp_ls_core.robotframework_log import get_logger
from robotframework_ls.impl.protocols import (
    TokenInfo,
    NodeInfo,
    KeywordUsageInfo,
    ILibraryImportNode,
    IRobotToken,
    INode,
    IRobotVariableMatch,
    VarTokenInfo,
    IKeywordArg,
    VariableKind,
)
from robotframework_ls.impl.text_utilities import normalize_robot_name
from robocorp_ls_core.basic import isinstance_name
from robotframework_ls.impl.keywords_in_args import (
    KEYWORD_NAME_TO_KEYWORD_INDEX,
    KEYWORD_NAME_TO_CONDITION_INDEX,
)
import functools
import weakref
import threading
import typing


log = get_logger(__name__)


class _NodesProviderVisitor(ast_module.NodeVisitor):
    def __init__(self, on_node=lambda node: None):
        ast_module.NodeVisitor.__init__(self)
        self._stack = []
        self.on_node = on_node

    def generic_visit(self, node):
        self._stack.append(node)
        self.on_node(self._stack, node)
        ast_module.NodeVisitor.generic_visit(self, node)
        self._stack.pop()


class _PrinterVisitor(ast_module.NodeVisitor):
    def __init__(self, stream):
        ast_module.NodeVisitor.__init__(self)
        self._level = 0
        self._stream = stream

    def _replace_spacing(self, txt):
        curr_len = len(txt)
        delta = 80 - curr_len
        return txt.replace("*SPACING*", " " * delta)

    def generic_visit(self, node):
        # Note: prints line and col offsets 0-based (even if the ast is 1-based for
        # lines and 0-based for columns).
        self._level += 1
        try:
            indent = "  " * self._level
            node_lineno = node.lineno
            if node_lineno != -1:
                # Make 0-based
                node_lineno -= 1
            node_end_lineno = node.end_lineno
            if node_end_lineno != -1:
                # Make 0-based
                node_end_lineno -= 1
            self._stream.write(
                self._replace_spacing(
                    "%s%s *SPACING* (%s, %s) -> (%s, %s)\n"
                    % (
                        indent,
                        node.__class__.__name__,
                        node_lineno,
                        node.col_offset,
                        node_end_lineno,
                        node.end_col_offset,
                    )
                )
            )
            tokens = getattr(node, "tokens", [])
            for token in tokens:

                token_lineno = token.lineno
                if token_lineno != -1:
                    # Make 0-based
                    token_lineno -= 1

                self._stream.write(
                    self._replace_spacing(
                        "%s- %s, '%s' *SPACING* (%s, %s->%s)\n"
                        % (
                            indent,
                            token.type,
                            token.value.replace("\n", "\\n").replace("\r", "\\r"),
                            token_lineno,
                            token.col_offset,
                            token.end_col_offset,
                        )
                    )
                )

            ast_module.NodeVisitor.generic_visit(self, node)
        finally:
            self._level -= 1


MAX_ERRORS = 100


class _AbstractIndexer:
    def iter_indexed(self, clsname):
        pass

    @property
    def ast(self):
        return self._weak_ast()


class _FullIndexer(_AbstractIndexer):
    def __init__(self, weak_ast: "weakref.ref[ast_module.AST]"):
        self._weak_ast = weak_ast
        self._lock = threading.Lock()
        self._name_to_node_info_lst: Dict[str, List[NodeInfo]] = {}
        self._indexed_full = False

    def _index(self):
        with self._lock:
            if self._indexed_full:
                return

            ast = self._weak_ast()
            if ast is None:
                raise RuntimeError("AST already garbage collected.")

            for stack, node in _iter_nodes(ast):
                lst = self._name_to_node_info_lst.get(node.__class__.__name__)
                if lst is None:
                    lst = self._name_to_node_info_lst[node.__class__.__name__] = []

                lst.append(NodeInfo(tuple(stack), node))
            self._indexed_full = True

    def iter_indexed(self, clsname: str) -> Iterator[NodeInfo]:
        if not self._indexed_full:
            self._index()

        yield from iter(self._name_to_node_info_lst.get(clsname, ()))


class _SectionIndexer(_AbstractIndexer):
    """
    This is a bit smarter in that it can index only the parts we're interested
    in (so, to get the LibraryImport it won't iterate over the keywords to
    do the indexing).
    """

    INNER_INSIDE_TOP_LEVEL = {
        "LibraryImport": "SettingSection",
        "ResourceImport": "SettingSection",
        "VariablesImport": "SettingSection",
        "SuiteSetup": "SettingSection",
        "SuiteTeardown": "SettingSection",
        "TestTemplate": "SettingSection",
        # Not settings:
        "Keyword": "KeywordSection",
        "TestCase": "TestCaseSection",
        "Variable": "VariableSection",
    }

    TOP_LEVEL = {
        "SettingSection",
        "VariableSection",
        "TestCaseSection",
        "KeywordSection",
        "CommentSection",
    }

    def __init__(self, weak_ast):
        self._weak_ast = weak_ast
        self._lock = threading.Lock()
        self._first_level_name_to_node_info_lst: Dict[str, List[NodeInfo]] = {}

        # We always start by indexing the first level in this case (to get the sections
        # such as 'CommentSection', 'SettingSection', etc), which should be fast.

        ast = self._weak_ast()
        if ast is None:
            raise RuntimeError("AST already garbage collected.")

        for stack, node in _iter_nodes(ast, recursive=False):
            lst = self._first_level_name_to_node_info_lst.get(node.__class__.__name__)
            if lst is None:
                lst = self._first_level_name_to_node_info_lst[
                    node.__class__.__name__
                ] = []

            lst.append(NodeInfo(tuple(stack), node))

    def iter_indexed(self, clsname: str) -> Iterator[NodeInfo]:
        top_level = self.INNER_INSIDE_TOP_LEVEL.get(clsname)
        if top_level is not None:
            lst = self._first_level_name_to_node_info_lst.get(top_level)
            if lst is not None:
                for node_info in lst:
                    indexer = _obtain_ast_indexer(node_info.node)
                    yield from indexer.iter_indexed(clsname)
        else:
            if clsname in self.TOP_LEVEL:
                yield from iter(
                    self._first_level_name_to_node_info_lst.get(clsname, ())
                )
            else:
                # i.e.: We don't know what we should be getting, so, just check
                # everything...
                for lst in self._first_level_name_to_node_info_lst.values():
                    for node_info in lst:
                        indexer = _obtain_ast_indexer(node_info.node)
                        yield from indexer.iter_indexed(clsname)


class _ASTIndexer(_AbstractIndexer):
    def __init__(self, ast: ast_module.AST):
        self._weak_ast = weakref.ref(ast)
        self._is_root = ast.__class__.__name__ == "File"

        self._indexer: _AbstractIndexer
        if self._is_root:
            # Cache by sections
            self._indexer = _SectionIndexer(self._weak_ast)
        else:
            # Always cache fully
            self._indexer = _FullIndexer(self._weak_ast)

        self._additional_caches: Dict[Hashable, Tuple[Any, ...]] = {}

    def iter_cached(
        self, cache_key: Hashable, compute: Callable, *args
    ) -> Iterator[Any]:
        try:
            cached = self._additional_caches[cache_key]
        except KeyError:
            cached = tuple(compute(self, *args))
            self._additional_caches[cache_key] = cached

        yield from iter(cached)

    def iter_indexed(self, clsname: str) -> Iterator[NodeInfo]:
        return self._indexer.iter_indexed(clsname)


def _get_errors_from_tokens(node):
    for token in node.tokens:
        if token.type in (token.ERROR, token.FATAL_ERROR):
            start = (token.lineno - 1, token.col_offset)
            end = (token.lineno - 1, token.end_col_offset)
            error = Error(token.error, start, end)
            yield error


def _obtain_ast_indexer(ast):
    try:
        indexer = ast.__ast_indexer__
    except:
        indexer = ast.__ast_indexer__ = _ASTIndexer(ast)
    return indexer


def _convert_ast_to_indexer(func):
    @functools.wraps(func)
    def new_func(ast, *args, **kwargs):
        try:
            indexer = ast.__ast_indexer__
        except:
            indexer = ast.__ast_indexer__ = _ASTIndexer(ast)

        return func(indexer, *args, **kwargs)

    return new_func


def collect_errors(node) -> List[Error]:
    errors = []

    use_errors_attribute = "errors" in node.__class__._attributes

    for _stack, node in _iter_nodes(node, recursive=True):
        if node.__class__.__name__ == "Error":
            errors.extend(_get_errors_from_tokens(node))

        elif use_errors_attribute:
            node_errors = getattr(node, "errors", ())
            if node_errors:
                for error in node_errors:
                    errors.append(create_error_from_node(node, error, tokens=[node]))

        if len(errors) >= MAX_ERRORS:
            break

    return errors


def create_error_from_node(node, msg, tokens=None) -> Error:
    if tokens is None:
        tokens = node.tokens

    if not tokens:
        log.info("No tokens found when visiting: %s.", node.__class__)
        start = (0, 0)
        end = (0, 0)
    else:
        # line is 1-based and col is 0-based (make both 0-based for the error).
        start = (tokens[0].lineno - 1, tokens[0].col_offset)
        end = (tokens[-1].lineno - 1, tokens[-1].end_col_offset)

    error = Error(msg, start, end)
    return error


def print_ast(node, stream=None):
    if stream is None:
        stream = sys.stderr
    errors_visitor = _PrinterVisitor(stream)
    errors_visitor.visit(node)


def find_section(node, line: int) -> Optional[INode]:
    """
    :param line:
        0-based
    """
    last_section = None
    for section in node.sections:
        # section.lineno is 1-based.
        if (section.lineno - 1) <= line:
            last_section = section

        else:
            return last_section

    return last_section


if typing.TYPE_CHECKING:
    # The INode has Robot Framework specific methods, but at runtime
    # we can just check the actual ast class.
    from typing import runtime_checkable, Protocol

    @runtime_checkable
    class _AST_CLASS(INode, Protocol):
        pass


else:
    # We know that the AST we're dealing with is the INode.
    # We can't use runtime_checkable on Python 3.7 though.
    _AST_CLASS = ast_module.AST


def get_local_variable_stack_and_node(
    stack: Sequence[INode],
) -> Tuple[Tuple[INode, ...], INode]:
    """
    Provides the stack to search local variables in (i.e.: the keyword/test case).

    Note that this requires a valid stack.
    """
    assert stack, "This method requires a valid stack."

    stack_lst: List[INode] = []
    for local_stack_node in reversed(stack):
        stack_lst.append(local_stack_node)
        if local_stack_node.__class__.__name__ in ("Keyword", "TestCase"):
            stack = tuple(stack_lst)
            break
    else:
        stack = (local_stack_node,)
        local_stack_node = stack[0]
    return stack, local_stack_node


def matches_stack(
    def_stack: Optional[Sequence[INode]], stack: Optional[Sequence[INode]]
) -> bool:
    """
    Note: just checks the stack, the source must be already validated at this point.
    """
    if stack is not None:
        if def_stack is None:
            return False

        if stack:
            if not def_stack:
                return False

            if stack[-1].lineno == def_stack[-1].lineno:
                return True

            # Not directly the same (we could be inside some for/while, so, let's
            # see if we can get the keyword/testcase from the stack).
            _, node1 = get_local_variable_stack_and_node(stack)
            _, node2 = get_local_variable_stack_and_node(def_stack)
            return node1.lineno == node2.lineno

    return True


def _iter_nodes(
    node, internal_stack: Optional[List[INode]] = None, recursive=True
) -> Iterator[Tuple[List[INode], INode]]:
    """
    :note: the yielded stack is actually always the same (mutable) list, so,
    clients that want to return it somewhere else should create a copy.
    """
    stack: List[INode]
    if internal_stack is None:
        stack = []
        if node.__class__.__name__ != "File":
            stack.append(node)
    else:
        stack = internal_stack

    if recursive:
        for _field, value in ast_module.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, _AST_CLASS):
                        yield stack, item
                        stack.append(item)
                        yield from _iter_nodes(item, stack, recursive=True)
                        stack.pop()

            elif isinstance(value, _AST_CLASS):
                yield stack, value
                stack.append(value)

                yield from _iter_nodes(value, stack, recursive=True)

                stack.pop()
    else:
        # Not recursive
        for _field, value in ast_module.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, _AST_CLASS):
                        yield stack, item

            elif isinstance(value, _AST_CLASS):
                yield stack, value


def iter_all_nodes_recursive(node: INode) -> Iterator[Tuple[List[INode], INode]]:
    """
    This function will iterate over all the nodes. Use only if there's no
    other way to implement it as iterating over all the nodes is slow...
    """
    yield from _iter_nodes(node)


def _iter_nodes_filtered_not_recursive(
    ast, accept_class: Union[Tuple[str, ...], str]
) -> Iterator[Tuple[list, Any]]:
    if not isinstance(accept_class, (list, tuple, set)):
        accept_class = (accept_class,)
    for stack, node in _iter_nodes(ast, recursive=False):
        if node.__class__.__name__ in accept_class:
            yield stack, node


def find_token(section, line, col) -> Optional[TokenInfo]:
    """
    :param section:
        The result from find_section(line, col), to pre-filter the nodes we may match.
    """
    for stack, node in _iter_nodes(section):
        try:
            tokens = node.tokens
        except AttributeError:
            continue

        if not tokens:
            continue

        if (tokens[-1].lineno - 1) < line:
            # i.e.: if the last node in the token is still before the
            # line we're searching, keep on going
            continue

        last_token = None
        for token in tokens:
            lineno = token.lineno - 1
            if lineno != line:
                continue

            if token.type == token.SEPARATOR:
                # For separator tokens, it must be entirely within the section
                # i.e.: if it's in the boundary for a word, we want the word,
                # not the separator.
                if token.col_offset < col < token.end_col_offset:
                    return TokenInfo(tuple(stack), node, token)

            elif token.type == token.EOL:
                # A trailing whitespace after a keyword should be part of
                # the keyword, not EOL.
                if token.col_offset <= col <= token.end_col_offset:
                    diff = col - token.col_offset
                    if last_token is not None and not token.value.strip():
                        eol_contents = token.value[:diff]
                        if len(eol_contents) <= 1:
                            token = _append_eol_to_prev_token(last_token, eol_contents)

                    return TokenInfo(tuple(stack), node, token)

            else:
                if token.col_offset <= col <= token.end_col_offset:
                    return TokenInfo(tuple(stack), node, token)

            last_token = token

    return None


def _find_subvar(stack, node, initial_token, col) -> Optional[VarTokenInfo]:
    for token, var_identifier in _tokenize_subvars(initial_token):
        if token.type == token.ARGUMENT:
            continue

        if token.col_offset <= col <= token.end_col_offset:
            if initial_token.type == initial_token.ASSIGN:
                token = copy_token_replacing(token, type=initial_token.ASSIGN)
            return VarTokenInfo(stack, node, token, var_identifier)

    from robotframework_ls.impl import robot_constants

    for p in robot_constants.VARIABLE_PREFIXES:
        if initial_token.value.startswith(p + "{"):
            if initial_token.value.endswith("}"):
                var_token = copy_token_with_subpart(initial_token, 2, -1)
            else:
                var_token = copy_token_with_subpart(
                    initial_token, 2, len(initial_token.value)
                )

            var_identifier = p
            return VarTokenInfo(stack, node, var_token, var_identifier)
    return None


def find_variable(section, line, col) -> Optional[VarTokenInfo]:
    """
    Finds the current variable token. Note that it won't include '{' nor '}'.
    The token may also be an empty token if we have a variable without contents.
    """

    token_info = find_token(section, line, col)
    if token_info is not None:
        stack = token_info.stack
        node = token_info.node
        token = token_info.token

        try:
            if (
                token.type == token.ARGUMENT
                and node.__class__.__name__ in CLASSES_WTH_EXPRESSION_ARGUMENTS
            ):
                for part in iter_expression_variables(token):
                    if part.type == token.VARIABLE:
                        if part.col_offset <= col <= part.end_col_offset:
                            return VarTokenInfo(
                                stack, node, part, "$", VarTokenInfo.CONTEXT_EXPRESSION
                            )

                if "$" in token.value:
                    char_in_token = col - token.col_offset
                    if char_in_token >= 0:
                        value_up_to_cursor = token.value[:char_in_token]
                        if value_up_to_cursor.endswith("$"):
                            # Empty variable at this point
                            from robot.api import Token

                            empty_token = Token(
                                type=token.VARIABLE,
                                value="",
                                lineno=token.lineno,
                                col_offset=col,
                            )

                            return VarTokenInfo(
                                stack,
                                node,
                                empty_token,
                                "$",
                                VarTokenInfo.CONTEXT_EXPRESSION,
                            )

        except:
            log.exception("Unable to tokenize: %s", token)

        if "{" in token.value:
            parts = _tokenize_variables_even_when_invalid(token, col)
            if not parts:
                return None

            for part in parts:
                if part.type in (part.VARIABLE, part.ASSIGN):
                    if part.col_offset <= col <= part.end_col_offset:
                        return _find_subvar(
                            token_info.stack, token_info.node, part, col
                        )
            else:
                return None
    return None


def tokenize_variables_from_name(name):
    return tokenize_variables(create_token(name))  # May throw error if it's not OK.


def tokenize_variables(token: IRobotToken) -> Iterator[IRobotToken]:
    # May throw error if it's not OK.
    return token.tokenize_variables()


def _tokenize_variables_even_when_invalid(token: IRobotToken, col: int):
    """
    If Token.tokenize_variables() fails, this can still provide the variable under
    the given column by applying some heuristics to find open variables.
    """
    try:
        return tokenize_variables(token)
    except:
        pass

    # If we got here, it means that we weren't able to tokenize the variables
    # properly (probably some variable wasn't closed properly), so, let's do
    # a custom implementation for this use case.

    from robot.api import Token
    from robotframework_ls.impl.robot_constants import VARIABLE_PREFIXES

    diff = col - token.col_offset
    up_to_cursor = token.value[:diff]
    open_at = up_to_cursor.rfind("{")

    if open_at >= 1:
        if up_to_cursor[open_at - 1] in VARIABLE_PREFIXES:
            varname = [up_to_cursor[open_at - 1 :]]
            from_cursor = token.value[diff:]

            for c in from_cursor:
                if c in VARIABLE_PREFIXES or c.isspace() or c == "{":
                    break
                if c == "}":
                    varname.append(c)
                    break
                varname.append(c)

            return [
                Token(
                    type=token.VARIABLE,
                    value="".join(varname),
                    lineno=token.lineno,
                    col_offset=token.col_offset + open_at - 1,
                    error=token.error,
                )
            ]


LIBRARY_IMPORT_CLASSES = ("LibraryImport",)
RESOURCE_IMPORT_CLASSES = ("ResourceImport",)
SETTING_SECTION_CLASSES = ("SettingSection",)


@_convert_ast_to_indexer
def iter_nodes(ast, accept_class: Union[Tuple[str, ...], str]) -> Iterator[NodeInfo]:
    """
    Note: always recursive.
    """
    if not isinstance(accept_class, (list, tuple, set)):
        accept_class = (accept_class,)

    for classname in accept_class:
        yield from ast.iter_indexed(classname)


def iter_all_nodes(ast, recursive=True) -> Iterator[NodeInfo]:
    """
    Note: use this *very* sparingly as no caching will take place
    (as all nodes need to be iterated).

    Use one of the filtered APIs whenever possible as those are cached
    by the type.
    """
    for stack, node in _iter_nodes(ast, recursive=recursive):
        yield NodeInfo(tuple(stack), node)


def is_library_node_info(node_info: NodeInfo) -> bool:
    return node_info.node.__class__.__name__ in LIBRARY_IMPORT_CLASSES


def is_resource_node_info(node_info: NodeInfo) -> bool:
    return node_info.node.__class__.__name__ in RESOURCE_IMPORT_CLASSES


def is_setting_section_node_info(node_info: NodeInfo) -> bool:
    return node_info.node.__class__.__name__ in SETTING_SECTION_CLASSES


@_convert_ast_to_indexer
def iter_library_imports(ast) -> Iterator[NodeInfo[ILibraryImportNode]]:
    yield from ast.iter_indexed("LibraryImport")


@_convert_ast_to_indexer
def iter_resource_imports(ast) -> Iterator[NodeInfo]:
    yield from ast.iter_indexed("ResourceImport")


@_convert_ast_to_indexer
def iter_variable_imports(ast) -> Iterator[NodeInfo]:
    yield from ast.iter_indexed("VariablesImport")


@_convert_ast_to_indexer
def iter_keywords(ast) -> Iterator[NodeInfo]:
    yield from ast.iter_indexed("Keyword")


@_convert_ast_to_indexer
def iter_variables(ast) -> Iterator[NodeInfo]:
    yield from ast.iter_indexed("Variable")


@_convert_ast_to_indexer
def iter_tests(ast) -> Iterator[NodeInfo]:
    yield from ast.iter_indexed("TestCase")


@_convert_ast_to_indexer
def iter_test_case_sections(ast) -> Iterator[NodeInfo]:
    yield from ast.iter_indexed("TestCaseSection")


@_convert_ast_to_indexer
def iter_setting_sections(ast) -> Iterator[NodeInfo]:
    yield from ast.iter_indexed("SettingSection")


@_convert_ast_to_indexer
def iter_indexed(ast, clsname) -> Iterator[NodeInfo]:
    yield from ast.iter_indexed(clsname)


def iter_keyword_arguments_as_str(ast, tokenize_keyword_name=False) -> Iterator[str]:
    """
    Provides the arguments with the full representation (use only for getting
    docs).

    May return strings as:
    ${my.store}=${my.load}[first][second]
    """
    for token in _iter_keyword_arguments_tokens(ast, tokenize_keyword_name):
        yield token.value


@_convert_ast_to_indexer
def _iter_keyword_arguments_tokens(
    ast, tokenize_keyword_name=False
) -> Iterator[IRobotToken]:
    """
    This API provides tokens as they are.

    i.e.: it returns tokens as: ${my.store}=${my.load}[first][second]

    So, this is internal as the outer world is tailored to
    dealing with what's actually needed.

    Note that it may return Token.ARGUMENT types (if defined in [Argument]) or
    Token.VARIABLE (if defined in keyword name).
    """
    for node_info in ast.iter_indexed("Arguments"):
        for token in node_info.node.tokens:
            if token.type == token.ARGUMENT:
                yield token

    if tokenize_keyword_name:
        from robot.api import Token

        ast_node = ast.ast
        if ast_node.__class__.__name__ == "Keyword":
            keyword_name = ast_node.header.get_token(Token.KEYWORD_NAME)
            if keyword_name:
                try:
                    tokenized_vars = keyword_name.tokenize_variables()
                except:
                    pass
                else:
                    for tok in tokenized_vars:
                        if tok.type == Token.VARIABLE:
                            yield tok


def iter_keyword_arguments_as_tokens(ast) -> Iterator[IRobotToken]:
    """
    API tailored at getting variables from keyword arguments.

    It converts an argument such as:
    "[Arguments]    ${my.store}=${my.load}[first][second]"

    and yields something as:

    "my.store"

    It may also convert keyword arguments in the keyword name such as:

    "Today is ${date:\d{4}-\d{2}-\d{2}}"

    to "date"
    """
    from robotframework_ls.impl.variable_resolve import iter_robot_variable_matches
    from robot.api import Token

    for initial_token in _iter_keyword_arguments_tokens(
        ast, tokenize_keyword_name=True
    ):
        for robot_match, _relative_index in iter_robot_variable_matches(
            initial_token.value
        ):
            i = initial_token.value.find(robot_match.base, robot_match.start)

            t = Token(
                initial_token.type,
                robot_match.base,
                initial_token.lineno,
                initial_token.col_offset + i,
                initial_token.error,
            )
            if initial_token.type == initial_token.VARIABLE:
                i = t.value.find(":")
                if i > 0:
                    t = copy_token_with_subpart(t, 0, i)
            yield t
            break  # Go to next arg.


def iter_keyword_arguments_as_kwarg(
    ast, tokenize_keyword_name=False
) -> Iterator[IKeywordArg]:

    from robotframework_ls.impl.robot_specbuilder import KeywordArg

    for token in _iter_keyword_arguments_tokens(ast, tokenize_keyword_name):
        yield KeywordArg(token.value)


def is_deprecated(ast) -> bool:
    from robotframework_ls.impl.text_utilities import has_deprecated_text

    docs = get_documentation_raw(ast)
    return has_deprecated_text(docs)


def get_documentation_raw(ast: INode) -> str:
    iter_in: Iterator[INode]
    if ast.__class__.__name__ == "File":
        # Handle the case where the File is given (docs must be gotten from
        # the *** Settings *** in this case).
        iter_in = (node_info.node for node_info in iter_setting_sections(ast))
    else:
        iter_in = iter((ast,))

    doc: List[str] = []
    last_line: List[str] = []

    last_token = None
    for ast_node in iter_in:
        for _stack, node in _iter_nodes_filtered_not_recursive(
            ast_node, accept_class="Documentation"
        ):
            for token in node.tokens:
                if last_token is not None and last_token.lineno != token.lineno:
                    doc.extend(last_line)
                    del last_line[:]

                last_token = token

                if token.type in (token.CONTINUATION, token.DOCUMENTATION):
                    # Ignore anything before a continuation.
                    del last_line[:]
                    continue

                last_line.append(token.value)
            else:
                # Last iteration
                doc.extend(last_line)

        if doc:
            # Case with multiple Setting sections
            break

    ret = "".join(doc).strip()
    return ret


def get_documentation_as_markdown(ast) -> str:
    documentation = get_documentation_raw(ast)
    if not documentation:
        return documentation
    try:
        from robotframework_ls import robot_to_markdown

        return robot_to_markdown.convert(documentation)
    except:
        log.exception("Error converting to markdown: %s", documentation)
        return documentation


KEYWORD_SET_LOCAL_TO_VAR_KIND = {
    normalize_robot_name("Set Local Variable"): VariableKind.LOCAL_SET_VARIABLE,
}

KEYWORD_SET_GLOBAL_TO_VAR_KIND = {
    normalize_robot_name("Set Task Variable"): VariableKind.TASK_SET_VARIABLE,
    normalize_robot_name("Set Test Variable"): VariableKind.TEST_SET_VARIABLE,
    normalize_robot_name("Set Suite Variable"): VariableKind.SUITE_SET_VARIABLE,
    normalize_robot_name("Set Global Variable"): VariableKind.GLOBAL_SET_VARIABLE,
}


KEYWORD_SET_ENV_TO_VAR_KIND = {
    normalize_robot_name("Set Environment Variable"): VariableKind.ENV_SET_VARIABLE,
}


@_convert_ast_to_indexer
def iter_local_assigns(ast) -> Iterator[VarTokenInfo]:
    from robot.api import Token

    for clsname, assign_token_type in (
        ("KeywordCall", Token.ASSIGN),
        ("ForHeader", Token.VARIABLE),  # RF 4+
        ("ForLoopHeader", Token.VARIABLE),  # RF 3
        ("ExceptHeader", Token.VARIABLE),
        ("InlineIfHeader", Token.ASSIGN),
    ):
        for node_info in ast.iter_indexed(clsname):
            node = node_info.node
            for token in node.tokens:
                if token.type == assign_token_type:
                    value = token.value

                    i = value.find("{")
                    j = value.rfind("}")
                    if i != -1 and j != -1 and i >= 1:
                        new_value = value[i + 1 : j]
                        token = Token(
                            type=token.type,
                            value=new_value,
                            lineno=token.lineno,
                            col_offset=token.col_offset + i + 1,
                            error=token.error,
                        )

                        yield VarTokenInfo(node_info.stack, node, token, value[0])


_FIXTURE_CLASS_NAMES = (
    "Setup",
    "Teardown",
    "SuiteSetup",
    "SuiteTeardown",
    "TestSetup",
    "TestTeardown",
)

_CLASSES_WITH_ARGUMENTS_AS_KEYWORD_CALLS_AS_TUPLE = _FIXTURE_CLASS_NAMES + (
    "TestTemplate",
    "Template",
)

CLASSES_WITH_ARGUMENTS_AS_KEYWORD_CALLS_AS_SET = frozenset(
    _CLASSES_WITH_ARGUMENTS_AS_KEYWORD_CALLS_AS_TUPLE
)

CLASSES_WTH_EXPRESSION_ARGUMENTS = (
    "IfHeader",
    "ElseIfHeader",
    "WhileHeader",
    "InlineIfHeader",
)


def _tokenize_subvars(initial_token: IRobotToken) -> Iterator[Tuple[IRobotToken, str]]:
    if "{" not in initial_token.value:
        return

    for tok, var_identifier in _tokenize_subvars_tokens(initial_token):
        if tok.type in (tok.ARGUMENT, tok.VARIABLE):
            yield tok, var_identifier


def _tokenize_subvars_tokens(
    initial_token: IRobotToken,
    op_type: str = "variableOperator",
    var_type: Optional[str] = None,
    default_var_identifier: str = "",
) -> Iterator[Tuple[IRobotToken, str]]:

    from robot.api import Token

    if var_type is None:
        var_type = Token.ARGUMENT

    if "{" not in initial_token.value:
        yield initial_token, default_var_identifier
        return

    if initial_token.value.startswith("{") and initial_token.value.endswith("}"):
        # i.e.: We're dealing with an expression.
        first, second, third = split_token_in_3(
            initial_token,
            op_type,
            var_type,
            op_type,
            1,
            -1,
        )
        yield first, ""
        yield from iter_expression_tokens(second)
        yield third, ""
        return

    robot_match_generator = RobotMatchTokensGenerator(initial_token, var_type)
    from robotframework_ls.impl.variable_resolve import iter_robot_variable_matches

    for robot_match, relative_index in iter_robot_variable_matches(initial_token.value):

        yield from robot_match_generator.gen_default_type(
            relative_index + len(robot_match.before)
        )

        yield from robot_match_generator.gen_tokens_from_robot_match(
            robot_match, relative_index, var_type=var_type
        )

    yield from robot_match_generator.gen_default_type(len(initial_token.value))


def _is_store_keyword(node):
    from robot.api import Token

    keyword_name_tok = node.get_token(Token.KEYWORD)
    if not keyword_name_tok:
        return False
    normalized = normalize_robot_name(keyword_name_tok.value)
    return (
        normalized in KEYWORD_SET_LOCAL_TO_VAR_KIND
        or normalized in KEYWORD_SET_GLOBAL_TO_VAR_KIND
    )


def _add_match(found: set, tok: IRobotToken) -> bool:
    """
    Helper to avoid returning 2 matches in the same position if 2 different
    heuristics overlap what they can return.
    """
    key = tok.col_offset, tok.lineno
    if key in found:
        return False
    found.add(key)
    return True


@_convert_ast_to_indexer
def iter_variable_references(ast) -> Iterator[VarTokenInfo]:
    # TODO: This right now makes everything globally, we should have 2 versions,
    # one to resolve references which are global and another to resolve references
    # just inside some scope when dealing with local variables.
    # Right now we're not very smart and even if a variable is local we'll reference
    # global variables...

    # Note: we collect only the references, not the definitions here!
    found: set = set()
    for clsname in (
        "KeywordCall",
        "LibraryImport",
        "ResourceImport",
        "TestTimeout",
        "Variable",
        "ForHeader",  # RF 4+
        "ForLoopHeader",  # RF 3
    ) + _FIXTURE_CLASS_NAMES:
        for node_info in ast.iter_indexed(clsname):
            stack = node_info.stack
            node = node_info.node
            token = None
            arg_i = 0
            for token in node.tokens:
                try:
                    if token.type == token.ARGUMENT:
                        arg_i += 1
                        if arg_i == 1 and clsname == "KeywordCall":
                            if _is_store_keyword(node_info.node):
                                continue

                    if token.type in (token.ARGUMENT, token.NAME):
                        for tok in tokenize_variables(token):
                            if tok.type == token.VARIABLE:
                                # We need to check for inner variables (as in
                                # this case we validate those).
                                for t, var_identifier in _tokenize_subvars(tok):
                                    if t.type != token.VARIABLE:
                                        continue
                                    if not _add_match(found, t):
                                        continue

                                    yield VarTokenInfo(stack, node, t, var_identifier)

                except:
                    log.exception("Unable to tokenize: %s", token)

    for usage_info in _iter_keyword_usage_tokens_first_level_uncached(ast):
        args_as_keywords_handler = get_args_as_keywords_handler(usage_info.node)
        if args_as_keywords_handler is None:
            continue

        stack = usage_info.stack
        node = usage_info.node
        arg_i = 0
        for token in usage_info.node.tokens:
            if token.type == token.ARGUMENT:
                arg_i += 1
                if arg_i == 1:
                    if _is_store_keyword(usage_info.node):
                        continue

                next_tok_type = args_as_keywords_handler.next_tok_type(token)
                if next_tok_type == args_as_keywords_handler.EXPRESSION:
                    for tok in iter_expression_variables(token):
                        if tok.type == token.VARIABLE:
                            if not _add_match(found, tok):
                                continue
                            yield VarTokenInfo(stack, node, tok, "$")

    for clsname in CLASSES_WTH_EXPRESSION_ARGUMENTS:
        for node_info in ast.iter_indexed(clsname):
            stack = node_info.stack
            node = node_info.node
            token = None

            for token in node.tokens:
                try:
                    if token.type == token.ARGUMENT:
                        for tok in iter_expression_variables(token):
                            if tok.type == token.VARIABLE:
                                if not _add_match(found, tok):
                                    continue
                                yield VarTokenInfo(stack, node, tok, "$")
                except:
                    log.exception("Unable to tokenize: %s", token)

    for node_info in ast.iter_indexed("Keyword"):
        stack = [node_info.node]
        for token in _iter_keyword_arguments_tokens(
            node_info.node, tokenize_keyword_name=True
        ):
            iter_in = _tokenize_subvars(token)

            try:
                # The first one is the variable store (the other is the
                # variable load on a default argument)
                # We are only interested in the second in this API.
                next(iter_in)
            except StopIteration:
                continue

            for t, varid in iter_in:
                if t.type != t.VARIABLE:
                    continue
                if not _add_match(found, t):
                    continue
                yield VarTokenInfo(stack, node, t, varid)


@_convert_ast_to_indexer
def iter_keyword_usage_tokens(
    ast, collect_args_as_keywords: bool
) -> Iterator[KeywordUsageInfo]:
    """
    Iterates through all the places where a keyword name is being used, providing
    the stack, node, token and name.
    """

    cache_key = ("iter_keyword_usage_tokens", collect_args_as_keywords)
    yield from ast.iter_cached(
        cache_key, _iter_keyword_usage_tokens_uncached, collect_args_as_keywords
    )


def _same_line_col(tok1: IRobotToken, tok2: IRobotToken):
    return tok1.lineno == tok2.lineno and tok1.col_offset == tok2.col_offset


def _build_keyword_usage(
    stack, node, yield_only_for_token, current_tokens, yield_only_over_keyword_name
) -> Optional[KeywordUsageInfo]:
    # Note: just check for line/col because the token could be changed
    # (for instance, an EOL ' ' could be added to the token).
    if not current_tokens:
        return None

    keyword_at_index = 0
    keyword_token = current_tokens[keyword_at_index]

    if yield_only_for_token is not None:
        if yield_only_over_keyword_name:
            if not _same_line_col(yield_only_for_token, keyword_token):
                return None
        else:
            for tok in current_tokens:
                if _same_line_col(yield_only_for_token, tok):
                    break
            else:
                return None

    keyword_token = copy_token_replacing(keyword_token, type=keyword_token.KEYWORD)
    new_tokens = [keyword_token]
    new_tokens.extend(current_tokens[keyword_at_index + 1 :])

    return KeywordUsageInfo(
        stack,
        node.__class__(new_tokens),
        keyword_token,
        keyword_token.value,
        True,
    )


def _iter_keyword_usage_tokens_uncached_from_args(
    stack,
    node,
    args_as_keywords_handler,
    yield_only_for_token: Optional[IRobotToken] = None,
    yield_only_over_keyword_name: bool = True,
):
    # We may have multiple matches, so, we need to setup the appropriate book-keeping
    current_tokens = []

    iter_in = iter(node.tokens)

    for token in iter_in:
        if token.type == token.ARGUMENT:
            next_tok_type = args_as_keywords_handler.next_tok_type(token)
            if next_tok_type == args_as_keywords_handler.KEYWORD:
                current_tokens.append(token)
                break

    for token in iter_in:
        if token.type == token.ARGUMENT:
            next_tok_type = args_as_keywords_handler.next_tok_type(token)

            if next_tok_type in (
                args_as_keywords_handler.CONTROL,
                args_as_keywords_handler.EXPRESSION,
            ):
                # Don't add IF/ELSE IF/AND nor the condition.
                continue

            if next_tok_type != args_as_keywords_handler.KEYWORD:
                # Argument was now added to current_tokens.
                current_tokens.append(token)
                continue

            if current_tokens:
                # Starting a new one (build for the previous).
                usage_info = _build_keyword_usage(
                    stack,
                    node,
                    yield_only_for_token,
                    current_tokens,
                    yield_only_over_keyword_name,
                )
                if usage_info is not None:
                    yield usage_info

            current_tokens = [token]

    else:
        # Do one last iteration at the end to deal with the last one.
        if current_tokens:
            usage_info = _build_keyword_usage(
                stack,
                node,
                yield_only_for_token,
                current_tokens,
                yield_only_over_keyword_name,
            )
            if usage_info is not None:
                yield usage_info


def _iter_keyword_usage_tokens_first_level_uncached(ast) -> Iterator[KeywordUsageInfo]:
    for clsname in ("KeywordCall",) + _CLASSES_WITH_ARGUMENTS_AS_KEYWORD_CALLS_AS_TUPLE:
        for node_info in ast.iter_indexed(clsname):
            stack = node_info.stack
            node = node_info.node
            usage_info = _create_keyword_usage_info(stack, node)
            if usage_info is not None:
                yield usage_info


def _iter_keyword_usage_tokens_uncached(
    ast, collect_args_as_keywords: bool
) -> Iterator[KeywordUsageInfo]:
    for usage_info in _iter_keyword_usage_tokens_first_level_uncached(ast):
        yield usage_info

        if collect_args_as_keywords:
            args_as_keywords_handler = get_args_as_keywords_handler(usage_info.node)
            if args_as_keywords_handler is None:
                continue

            yield from _iter_keyword_usage_tokens_uncached_from_args(
                usage_info.stack, usage_info.node, args_as_keywords_handler
            )


def _create_keyword_usage_info(stack, node) -> Optional[KeywordUsageInfo]:
    """
    If this is a keyword usage node, return information on it, otherwise,
    returns None.

    :note: this goes hand-in-hand with get_keyword_name_token.
    """
    from robot.api import Token

    if node.__class__.__name__ == "KeywordCall":
        token_type = Token.KEYWORD

    elif node.__class__.__name__ in CLASSES_WITH_ARGUMENTS_AS_KEYWORD_CALLS_AS_SET:
        token_type = Token.NAME

    else:
        return None

    node, token = _strip_node_and_token_bdd_prefix(node, token_type)
    if token is None:
        return None

    keyword_name = token.value
    if keyword_name.lower() == "none":
        return None
    return KeywordUsageInfo(tuple(stack), node, token, keyword_name)


def create_keyword_usage_info_from_token(
    stack: Tuple[INode, ...], node: INode, token: IRobotToken
) -> Optional[KeywordUsageInfo]:
    """
    If this is a keyword usage node, return information on it, otherwise,
    returns None.

    Note that it should return the keyword usage for the whole keyword call
    if we're in an argument that isn't itself a keyword call.
    """
    if token.type == token.ARGUMENT:
        args_as_keywords_handler = get_args_as_keywords_handler(node)
        if args_as_keywords_handler is not None:
            for v in _iter_keyword_usage_tokens_uncached_from_args(
                stack,
                node,
                args_as_keywords_handler,
                yield_only_for_token=token,
                yield_only_over_keyword_name=False,
            ):
                return v

    return _create_keyword_usage_info(stack, node)


class _ConsiderArgsAsKeywordNames:
    NONE = 0
    KEYWORD = 1
    EXPRESSION = 2
    CONTROL = 3

    def __init__(
        self,
        node,
        normalized_keyword_name,
        consider_keyword_at_index,
        consider_condition_at_index,
    ):
        self._node = node
        self._normalized_keyword_name = normalized_keyword_name
        self._consider_keyword_at_index = consider_keyword_at_index
        self._consider_condition_at_index = consider_condition_at_index
        self._current_arg = 0

        # Run Keyword If is special because it has 'ELSE IF' / 'ELSE'
        # which will then be be (cond, keyword) or just (keyword), so
        # we need to provide keyword usages as needed.
        if self._normalized_keyword_name == "runkeywordif":
            self.next_tok_type = self._next_tok_type_run_keyword_if
        elif self._normalized_keyword_name == "runkeywords":
            found = False
            for token in node.tokens:
                if "AND" == token.value:
                    found = True
                    break
            if found:
                self.next_tok_type = self._next_tok_type_run_keywords
            else:
                self.next_tok_type = self._consider_each_arg_as_keyword

        self._stack_kind = None
        self._stack = None
        self._started_match = False

    def next_tok_type_as_str(self, token) -> str:
        tok_type = self.next_tok_type(token)
        if tok_type == self.NONE:
            return "<none>"
        if tok_type == self.EXPRESSION:
            return "<expression>"
        if tok_type == self.KEYWORD:
            return "<keyword>"
        if tok_type == self.CONTROL:
            return "<control>"
        raise AssertionError(f"Unexpected: {tok_type}")

    def next_tok_type(self, token) -> int:  # pylint: disable=method-hidden
        assert token.type == token.ARGUMENT
        self._current_arg += 1

        if self._current_arg == self._consider_condition_at_index:
            return self.EXPRESSION

        if self._current_arg == self._consider_keyword_at_index:
            return self.KEYWORD

        return self.NONE

    def _next_tok_type_run_keyword_if(self, token):
        assert token.type == token.ARGUMENT

        self._current_arg += 1

        if token.value == "ELSE IF":
            self._started_match = True
            self._stack = []
            self._stack_kind = token.value
            return self.CONTROL
        elif token.value == "ELSE":
            self._started_match = True
            self._stack = []
            self._stack_kind = token.value
            return self.CONTROL

        else:
            self._started_match = False
            if self._stack is not None:
                self._stack.append(token)

        if self._stack is not None:
            if self._stack_kind == "ELSE IF":
                if len(self._stack) == 1:
                    return self.EXPRESSION
                return self.KEYWORD if len(self._stack) == 2 else self.NONE

            if self._stack_kind == "ELSE":
                return self.KEYWORD if len(self._stack) == 1 else self.NONE

        if self._current_arg == self._consider_condition_at_index:
            return self.EXPRESSION

        if self._current_arg == self._consider_keyword_at_index:
            return self.KEYWORD

        return self.NONE

    def _consider_each_arg_as_keyword(self, token):
        assert token.type == token.ARGUMENT
        return self.KEYWORD

    def _next_tok_type_run_keywords(self, token):
        assert token.type == token.ARGUMENT

        self._current_arg += 1

        if token.value == "AND":
            self._started_match = True
            self._stack = []
            self._stack_kind = token.value
            return self.CONTROL

        else:
            self._started_match = False
            if self._stack is not None:
                self._stack.append(token)

        if self._stack is not None:
            if self._stack_kind == "AND":
                return self.KEYWORD if len(self._stack) == 1 else self.NONE

        if self._current_arg == self._consider_keyword_at_index:
            return self.KEYWORD
        return self.NONE


def get_args_as_keywords_handler(node) -> Optional[_ConsiderArgsAsKeywordNames]:
    from robot.api import Token

    if node.__class__.__name__ == "KeywordCall":
        token_type = Token.KEYWORD

    elif node.__class__.__name__ in CLASSES_WITH_ARGUMENTS_AS_KEYWORD_CALLS_AS_SET:
        token_type = Token.NAME

    else:
        return None

    node_keyword_name = node.get_token(token_type)
    if node_keyword_name and node_keyword_name.value:
        normalized_keyword_name = normalize_robot_name(node_keyword_name.value)
        consider_keyword_at_index = KEYWORD_NAME_TO_KEYWORD_INDEX.get(
            normalized_keyword_name
        )
        consider_condition_at_index = KEYWORD_NAME_TO_CONDITION_INDEX.get(
            normalized_keyword_name
        )
        if (
            consider_keyword_at_index is not None
            or consider_condition_at_index is not None
        ):
            return _ConsiderArgsAsKeywordNames(
                node,
                normalized_keyword_name,
                consider_keyword_at_index,
                consider_condition_at_index,
            )
    return None


def get_keyword_name_token(
    stack: Tuple[INode, ...],
    node: INode,
    token: IRobotToken,
    accept_only_over_keyword_name: bool = True,
) -> Optional[IRobotToken]:
    """
    If the given token is a keyword call name, return the token, otherwise return None.

    :param accept_only_over_keyword_name:
        If True we'll only accept the token if it's over the keyword name.
        If False we'll accept the token even if it's over a keyword parameter.

    :note: this goes hand-in-hand with iter_keyword_usage_tokens.
    """
    if token.type == token.KEYWORD or (
        token.type == token.NAME
        and node.__class__.__name__ in CLASSES_WITH_ARGUMENTS_AS_KEYWORD_CALLS_AS_SET
    ):
        return _strip_token_bdd_prefix(token)

    if token.type == token.ARGUMENT and not token.value.strip().endswith("}"):
        args_as_keywords_handler = get_args_as_keywords_handler(node)
        if args_as_keywords_handler is not None:
            for _ in _iter_keyword_usage_tokens_uncached_from_args(
                stack,
                node,
                args_as_keywords_handler,
                yield_only_for_token=token,
                yield_only_over_keyword_name=accept_only_over_keyword_name,
            ):
                return token
    return None


def get_library_import_name_token(node, token: IRobotToken) -> Optional[IRobotToken]:
    """
    If the given ast node is a library import and the token is its name, return
    the name token, otherwise, return None.
    """

    if (
        token.type == token.NAME
        and isinstance_name(node, "LibraryImport")
        and node.name == token.value  # I.e.: match the name, not the alias.
    ):
        return token
    return None


def get_resource_import_name_token(node, token: IRobotToken) -> Optional[IRobotToken]:
    """
    If the given ast node is a library import and the token is its name, return
    the name token, otherwise, return None.
    """

    if (
        token.type == token.NAME
        and isinstance_name(node, "ResourceImport")
        and node.name == token.value  # I.e.: match the name, not the alias.
    ):
        return token
    return None


def get_variables_import_name_token(ast, token):
    """
    If the given ast node is a variables import and the token is its name, return
    the name token, otherwise, return None.
    """

    if (
        token.type == token.NAME
        and isinstance_name(ast, "VariablesImport")
        and ast.name == token.value  # I.e.: match the name, not the alias.
    ):
        return token
    return None


def _copy_of_node_replacing_token(node, token, token_type):
    """
    Workaround to create a new version of the same node but with the first
    occurrence of a token of the given type changed to another token.
    """
    new_tokens = list(node.tokens)
    for i, t in enumerate(new_tokens):
        if t.type == token_type:
            new_tokens[i] = token
            break
    return node.__class__(new_tokens)


def _strip_node_and_token_bdd_prefix(node, token_type):
    """
    This is a workaround because the parsing does not separate a BDD prefix from
    the keyword name. If the parsing is improved to do that separation in the future
    we can stop doing this.
    """
    original_token = node.get_token(token_type)
    if original_token is None:
        return node, None
    token = _strip_token_bdd_prefix(original_token)
    if token is original_token:
        # i.e.: No change was done.
        return node, token
    return _copy_of_node_replacing_token(node, token, token_type), token


def _strip_token_bdd_prefix(token):
    """
    This is a workaround because the parsing does not separate a BDD prefix from
    the keyword name. If the parsing is improved to do that separation in the future
    we can stop doing this.

    :return Token:
        Returns a new token with the bdd prefix stripped or the original token passed.
    """
    from robotframework_ls.impl.robot_constants import BDD_PREFIXES
    from robot.api import Token

    if token is None:
        return token

    text = token.value.lower()
    for prefix in BDD_PREFIXES:
        if text.startswith(prefix):
            new_name = token.value[len(prefix) :]
            return Token(
                type=token.type,
                value=new_name,
                lineno=token.lineno,
                col_offset=token.col_offset + len(prefix),
                error=token.error,
            )
    return token


def _append_eol_to_prev_token(last_token, eol_token_contents):
    from robot.api import Token

    new_value = last_token.value + eol_token_contents

    return Token(
        type=last_token.type,
        value=new_value,
        lineno=last_token.lineno,
        col_offset=last_token.col_offset,
        error=last_token.error,
    )


def copy_token_replacing(token, **kwargs):
    from robot.api import Token

    new_kwargs = {
        "type": token.type,
        "value": token.value,
        "lineno": token.lineno,
        "col_offset": token.col_offset,
        "error": token.error,
    }
    new_kwargs.update(kwargs)
    return Token(**new_kwargs)


def copy_token_with_subpart(token, start, end):
    from robot.api import Token

    return Token(
        type=token.type,
        value=token.value[start:end],
        lineno=token.lineno,
        col_offset=token.col_offset + start,
        error=token.error,
    )


def create_range_from_token(token) -> RangeTypedDict:

    start: PositionTypedDict = {"line": token.lineno - 1, "character": token.col_offset}
    end: PositionTypedDict = {
        "line": token.lineno - 1,
        "character": token.end_col_offset,
    }
    code_lens_range: RangeTypedDict = {"start": start, "end": end}
    return code_lens_range


def create_token(name):
    from robot.api import Token

    return Token(Token.NAME, name)


def convert_variable_match_base_to_token(
    token: IRobotToken, variable_match: IRobotVariableMatch
):
    from robot.api import Token

    base = variable_match.base
    assert base is not None
    s = variable_match.string
    if not base:
        base_i = s.find("{") + 1
    else:
        base_i = s.find(base)

    return Token(
        type=token.type,
        value=variable_match.base,
        lineno=token.lineno,
        col_offset=token.col_offset + variable_match.start + base_i,
        error=token.error,
    )


def iter_robot_match_as_tokens(
    robot_match: IRobotVariableMatch, relative_index: int = 0, lineno: int = 0
) -> Iterator[IRobotToken]:
    from robot.api import Token

    base = robot_match.base
    assert base is not None
    s = robot_match.string
    if not base:
        base_i = s.find("{") + 1
    else:
        base_i = s.find(base)

    yield Token(
        type="base",
        value=base,
        lineno=lineno,
        col_offset=relative_index + robot_match.start + base_i,
    )

    last_i = base_i + len(base)
    for item in robot_match.items:
        open_char_i = s.find("[", last_i)
        if open_char_i > 0:
            yield Token(
                type="[",
                value="[",
                lineno=lineno,
                col_offset=relative_index + robot_match.start + open_char_i,
            )

            last_i = open_char_i + 1

        if not item:
            item_i = last_i
        else:
            item_i = s.find(item, last_i)

        yield Token(
            type="item",
            value=item,
            lineno=lineno,
            col_offset=relative_index + robot_match.start + item_i,
        )

        last_i = item_i + len(item)

        close_char_i = s.find("]", last_i)
        if close_char_i < 0:
            break

        yield Token(
            type="]",
            value="]",
            lineno=lineno,
            col_offset=relative_index + robot_match.start + close_char_i,
        )

        last_i = close_char_i


def split_token_in_3(
    token: IRobotToken,
    first_token_type: str,
    second_token_type: str,
    third_token_type,
    start_pos,
    end_pos,
) -> Tuple[IRobotToken, IRobotToken, IRobotToken]:
    first = copy_token_replacing(
        token,
        type=first_token_type,
        value=token.value[:start_pos],
    )
    second = copy_token_replacing(
        token,
        type=second_token_type,
        value=token.value[start_pos:end_pos],
        col_offset=token.col_offset + start_pos,
    )

    third = copy_token_replacing(
        token,
        type=third_token_type,
        value=token.value[end_pos:],
        col_offset=second.end_col_offset,
    )

    return first, second, third


def split_token_change_first(
    token: IRobotToken, first_token_type: str, position: int
) -> Tuple[IRobotToken, IRobotToken]:
    prefix = copy_token_replacing(
        token,
        type=first_token_type,
        value=token.value[:position],
    )
    remainder = copy_token_replacing(
        token, value=token.value[position:], col_offset=prefix.end_col_offset
    )
    return prefix, remainder


def split_token_change_second(
    token: IRobotToken, second_token_type: str, position: int
) -> Tuple[IRobotToken, IRobotToken]:
    prefix = copy_token_replacing(
        token,
        value=token.value[:position],
    )
    remainder = copy_token_replacing(
        token,
        value=token.value[position:],
        col_offset=prefix.end_col_offset,
        type=second_token_type,
    )
    return prefix, remainder


def get_library_arguments_serialized(library) -> Optional[str]:
    return "::".join(library.args) if library.args else None


def iter_expression_variables(expression_token: IRobotToken) -> Iterator[IRobotToken]:
    from robot.api import Token

    for tok, _var_identifier in iter_expression_tokens(expression_token):
        if tok.type == Token.VARIABLE:
            yield tok


class RobotMatchTokensGenerator:
    def __init__(self, token, default_type):
        self.default_type = default_type
        self.token = token
        self.last_gen_end_offset = 0

    def gen_default_type(self, until_offset: int) -> Iterable[Tuple[IRobotToken, str]]:
        token = self.token
        if until_offset > self.last_gen_end_offset:
            from robot.api import Token

            val = token.value[self.last_gen_end_offset : until_offset]
            if val.strip():  # Don't generate just for whitespaces.
                yield Token(
                    self.default_type,
                    val,
                    token.lineno,
                    token.col_offset + self.last_gen_end_offset,
                    token.error,
                ), ""
            self.last_gen_end_offset = until_offset

    def gen_tokens_from_robot_match(
        self,
        robot_match: IRobotVariableMatch,
        last_relative_index: int,
        op_type: str = "variableOperator",
        var_type: Optional[str] = None,
    ) -> Iterable[Tuple[IRobotToken, str]]:
        from robot.api import Token

        curr_var_type = var_type
        if curr_var_type is None:
            curr_var_type = Token.VARIABLE

        token = self.token
        if not robot_match.base:
            i = token.value.find("{", robot_match.start + last_relative_index) + 1
        else:
            i = token.value.find(
                robot_match.base, robot_match.start + last_relative_index
            )

        start_offset = robot_match.start + last_relative_index

        yield from self.gen_default_type(start_offset)

        yield Token(
            op_type,
            token.value[robot_match.start + last_relative_index : i],
            token.lineno,
            token.col_offset + start_offset,
            token.error,
        ), ""

        subvar_tokens = tuple(
            _tokenize_subvars_tokens(
                Token(
                    curr_var_type,
                    robot_match.base,
                    token.lineno,
                    token.col_offset + i,
                    token.error,
                ),
                op_type,
                var_type,
                robot_match.identifier,
            )
        )
        if len(subvar_tokens) == 1:
            tok, var_kind = subvar_tokens[0]
            tok = copy_token_replacing(tok, type=tok.VARIABLE)
            yield (tok, var_kind)
        else:
            yield from iter(subvar_tokens)

        base = robot_match.base
        assert base is not None
        j = i + len(base)

        val = token.value[j : robot_match.end + last_relative_index]
        yield Token(
            op_type,
            val,
            token.lineno,
            token.col_offset + j,
            token.error,
        ), ""

        self.last_gen_end_offset = j + len(val)


def _gen_tokens_in_py_expr(
    py_expr,
    expression_token,
):
    from tokenize import generate_tokens, NAME, ERRORTOKEN
    from io import StringIO
    from robot.api import Token

    var_type = Token.VARIABLE
    op_type = "variableOperator"

    gen_var_token_info = None
    try:
        for token_info in generate_tokens(StringIO(py_expr).readline):
            if token_info.type == ERRORTOKEN and token_info.string == "$":
                gen_var_token_info = token_info

            elif gen_var_token_info is not None and token_info.type == NAME:
                if gen_var_token_info.start[1] == token_info.start[1] - 1:
                    start_offset = gen_var_token_info.start[1]

                    yield Token(
                        op_type,
                        gen_var_token_info.string,
                        expression_token.lineno,
                        expression_token.col_offset + start_offset,
                        expression_token.error,
                    ), ""

                    yield Token(
                        var_type,
                        token_info.string,
                        expression_token.lineno,
                        expression_token.col_offset + token_info.start[1],
                        expression_token.error,
                    ), "$"

    except:
        log.exception(f"Unable to evaluate python expression from: {expression_token}")


def iter_expression_tokens(
    expression_token: IRobotToken,
    default_type=None,
) -> Iterator[Tuple[IRobotToken, str]]:
    # See: robot.variables.evaluation.evaluate_expression

    from robotframework_ls.impl.variable_resolve import iter_robot_variable_matches

    if default_type is None:
        default_type = expression_token.ARGUMENT

    expression_to_evaluate: List[str] = []

    robot_matches_and_relative_index = list(
        iter_robot_variable_matches(expression_token.value)
    )

    robot_match = None
    for robot_match, relative_index in robot_matches_and_relative_index:
        expression_to_evaluate.append(robot_match.before)
        expression_to_evaluate.append("1" * (robot_match.end - robot_match.start))

    if robot_match is None:
        after = expression_token.value
    else:
        after = robot_match.after

    if after.strip():
        expression_to_evaluate.append(after)

    python_toks_and_identifiers = []
    if expression_to_evaluate:
        expr = "".join(expression_to_evaluate)
        if expr.strip():
            python_toks_and_identifiers.extend(
                _gen_tokens_in_py_expr(expr, expression_token)
            )

    robot_match_generator = RobotMatchTokensGenerator(expression_token, default_type)

    # Now, let's put the vars from python and the robot matches we have in a
    # sorted list so that we can iterate properly.
    from robot.api import Token

    def key(obj):
        # obj is either a tuple(robot match/relative index) or a tuple(Token/var identifier)
        if isinstance(obj[0], Token):
            return obj[0].col_offset

        robot_match: IRobotVariableMatch = obj[0]
        relative_index = obj[1]
        return relative_index + robot_match.start + expression_token.col_offset

    lst = sorted(
        python_toks_and_identifiers + robot_matches_and_relative_index, key=key
    )

    # obj is either a tuple(robot match/relative index) or a tuple(Token/var identifier)
    obj: Any
    for obj in lst:
        if isinstance(obj[0], Token):
            yield from robot_match_generator.gen_default_type(
                obj[0].col_offset - expression_token.col_offset
            )
            yield obj
            robot_match_generator.last_gen_end_offset = (
                obj[0].end_col_offset - expression_token.col_offset
            )

        else:
            yield from robot_match_generator.gen_tokens_from_robot_match(*obj)
    yield from robot_match_generator.gen_default_type(len(expression_token.value))


def is_node_with_expression_argument(node):
    if node.__class__.__name__ == "KeywordCall":
        kw_name = node.keyword
        return kw_name and normalize_robot_name(kw_name) == "evaluate"
    else:
        return node.__class__.__name__ in CLASSES_WTH_EXPRESSION_ARGUMENTS
