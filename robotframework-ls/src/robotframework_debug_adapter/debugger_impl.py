"""
Unfortunately right now Robotframework doesn't really provide the needed hooks
for a debugger, so, we monkey-patch internal APIs to gather the needed info.

More specifically:

    robot.running.steprunner.StepRunner - def run_step

    is patched so that we can stop when some line is about to be executed.
"""
import functools
from robotframework_debug_adapter import file_utils
import threading
from robotframework_debug_adapter.constants import (
    STATE_RUNNING,
    STATE_PAUSED,
    REASON_BREAKPOINT,
    STEP_IN,
    REASON_STEP,
    STEP_NEXT,
    STEP_OUT,
)
import itertools
from functools import partial
from os.path import os
from robocode_ls_core.robotframework_log import get_logger, get_log_level
from collections import namedtuple
import weakref

log = get_logger(__name__)

next_id = partial(next, itertools.count(1))


class RobotBreakpoint(object):
    def __init__(self, lineno):
        """
        :param int lineno:
            1-based line for the breakpoint.
        """
        self.lineno = lineno


class BusyWait(object):
    def __init__(self):
        self.before_wait = []
        self.waited = 0
        self.proceeded = 0
        self._condition = threading.Condition()

    def pre_wait(self):
        for c in self.before_wait:
            c()

    def wait(self):
        self.waited += 1
        with self._condition:
            self._condition.wait()

    def proceed(self):
        self.proceeded += 1
        with self._condition:
            self._condition.notify_all()


class _BaseObjectToDAP(object):
    """
    Base class for classes which converts some object to the DAP.
    """

    def compute_as_dap(self):
        return []


class _ArgsAsDAP(_BaseObjectToDAP):
    """
    Provides args as DAP variables.
    """

    def __init__(self, keyword_args):
        self._keyword_args = keyword_args

    def compute_as_dap(self):
        from robotframework_debug_adapter.dap.dap_schema import Variable
        from robotframework_debug_adapter.safe_repr import SafeRepr

        lst = []
        safe_repr = SafeRepr()
        for i, arg in enumerate(self._keyword_args):
            lst.append(Variable("Arg %s" % (i,), safe_repr(arg), variablesReference=0))
        return lst


class _VariablesAsDAP(_BaseObjectToDAP):
    """
    Provides variables as DAP variables.
    """

    def __init__(self, variables):
        self._variables = variables

    def compute_as_dap(self):
        from robotframework_debug_adapter.dap.dap_schema import Variable
        from robotframework_debug_adapter.safe_repr import SafeRepr

        variables = self._variables
        as_dct = variables.as_dict()
        lst = []
        safe_repr = SafeRepr()
        for key, val in as_dct.items():
            lst.append(Variable(safe_repr(key), safe_repr(val), variablesReference=0))
        return lst


class _BaseFrameInfo(object):
    @property
    def dap_frame(self):
        raise NotImplementedError("Not implemented in: %s" % (self.__class__,))

    def get_scopes(self):
        raise NotImplementedError("Not implemented in: %s" % (self.__class__,))

    def get_type_name(self):
        raise NotImplementedError("Not implemented in: %s" % (self.__class__,))


class _SuiteFrameInfo(_BaseFrameInfo):
    def __init__(self, stack_list, dap_frame):
        self._stack_list = weakref.ref(stack_list)
        self._dap_frame = dap_frame

    @property
    def dap_frame(self):
        return self._dap_frame

    def get_scopes(self):
        return []

    def get_type_name(self):
        return "Suite"


class _TestFrameInfo(_BaseFrameInfo):
    def __init__(self, stack_list, dap_frame):
        self._stack_list = weakref.ref(stack_list)
        self._dap_frame = dap_frame

    @property
    def dap_frame(self):
        return self._dap_frame

    def get_scopes(self):
        return []

    def get_type_name(self):
        return "Test"


class _KeywordFrameInfo(_BaseFrameInfo):
    def __init__(self, stack_list, dap_frame, keyword, variables):
        self._stack_list = weakref.ref(stack_list)
        self._dap_frame = dap_frame
        self._keyword = keyword
        self._scopes = None
        self._variables = variables

    @property
    def keyword(self):
        return self._keyword

    @property
    def variables(self):
        return self._variables

    @property
    def dap_frame(self):
        return self._dap_frame

    def get_type_name(self):
        return "Keyword"

    def get_scopes(self):
        if self._scopes is not None:
            return self._scopes
        stack_list = self._stack_list()
        if stack_list is None:
            return []

        from robotframework_debug_adapter.dap.dap_schema import Scope

        locals_variables_reference = next_id()
        vars_variables_reference = next_id()
        scopes = [
            Scope("Variables", vars_variables_reference, expensive=False),
            Scope(
                "Arguments",
                locals_variables_reference,
                expensive=False,
                presentationHint="locals",
            ),
        ]

        try:
            args = self._keyword.args
        except:
            log.debug("Unable to get arguments for keyword: %s", self._keyword)
            args = []
        stack_list.register_variables_reference(
            locals_variables_reference, _ArgsAsDAP(args)
        )
        # ctx.namespace.get_library_instances()

        stack_list.register_variables_reference(
            vars_variables_reference, _VariablesAsDAP(self._variables)
        )
        self._scopes = scopes
        return self._scopes


class _StackInfo(object):
    """
    This is the information for the stacks available when we're stopped in a
    breakpoint.
    """

    def __init__(self):
        self._frame_id_to_frame_info = {}
        self._dap_frames = []
        self._ref_id_to_children = {}

    def iter_frame_ids(self):
        """
        Access to list(int) where iter_frame_ids[0] is the current frame
        where we're stopped (topmost frame).
        """
        return (x.id for x in self._dap_frames)

    def register_variables_reference(self, variables_reference, children):
        self._ref_id_to_children[variables_reference] = children

    def add_keyword_entry_stack(self, keyword, filename, variables):
        from robotframework_debug_adapter.dap import dap_schema

        frame_id = next_id()
        try:
            name = str(keyword).strip()
            if not name:
                name = keyword.__class__.__name__
        except:
            name = "<Unable to get keyword name>"
        dap_frame = dap_schema.StackFrame(
            frame_id,
            name=name,
            line=keyword.lineno or 1,
            column=0,
            source=dap_schema.Source(name=os.path.basename(filename), path=filename),
        )
        self._dap_frames.append(dap_frame)
        self._frame_id_to_frame_info[frame_id] = _KeywordFrameInfo(
            self, dap_frame, keyword, variables
        )
        return frame_id

    def add_suite_entry_stack(self, name, filename):
        from robotframework_debug_adapter.dap import dap_schema

        frame_id = next_id()
        dap_frame = dap_schema.StackFrame(
            frame_id,
            name=name,
            line=1,
            column=0,
            source=dap_schema.Source(name=os.path.basename(filename), path=filename),
        )
        self._dap_frames.append(dap_frame)
        self._frame_id_to_frame_info[frame_id] = _SuiteFrameInfo(self, dap_frame)
        return frame_id

    def add_test_entry_stack(self, name, filename, lineno):
        from robotframework_debug_adapter.dap import dap_schema

        frame_id = next_id()
        dap_frame = dap_schema.StackFrame(
            frame_id,
            name=name,
            line=lineno,
            column=0,
            source=dap_schema.Source(name=os.path.basename(filename), path=filename),
        )
        self._dap_frames.append(dap_frame)
        self._frame_id_to_frame_info[frame_id] = _TestFrameInfo(self, dap_frame)
        return frame_id

    @property
    def dap_frames(self):
        """
        Access to list(StackFrame) where dap_frames[0] is the current frame
        where we're stopped (topmost frame).
        """
        return self._dap_frames

    def get_scopes(self, frame_id):
        frame_info = self._frame_id_to_frame_info.get(frame_id)
        if frame_info is None:
            return None
        return frame_info.get_scopes()

    def get_variables(self, variables_reference):
        lst = self._ref_id_to_children.get(variables_reference)
        if lst is not None:
            if isinstance(lst, _BaseObjectToDAP):
                lst = lst.compute_as_dap()
        return lst


_StepEntry = namedtuple("_StepEntry", "variables, keyword")
_SuiteEntry = namedtuple("_SuiteEntry", "name, source")
_TestEntry = namedtuple("_TestEntry", "name, source, lineno")


class InvalidFrameIdError(Exception):
    pass


class InvalidFrameTypeError(Exception):
    pass


class UnableToEvaluateError(Exception):
    pass


class EvaluationResult(Exception):
    def __init__(self, result):
        self.result = result


class _EvaluationInfo(object):
    def __init__(self, frame_id, expression):
        from concurrent import futures

        self.frame_id = frame_id
        self.expression = expression
        self.future = futures.Future()

    def _do_eval(self, debugger_impl):
        frame_id = self.frame_id
        stack_info = debugger_impl._get_stack_info_from_frame_id(frame_id)

        if stack_info is None:
            raise InvalidFrameIdError(
                "Unable to find frame id for evaluation: %s" % (frame_id,)
            )

        info = stack_info._frame_id_to_frame_info.get(frame_id)
        if info is None:
            raise InvalidFrameIdError(
                "Unable to find frame info for evaluation: %s" % (frame_id,)
            )

        if not isinstance(info, _KeywordFrameInfo):
            raise InvalidFrameTypeError(
                "Can only evaluate at a Keyword context (current context: %s)"
                % (info.get_type_name(),)
            )
        log.info("Doing evaluation in the Keyword context: %s", info.keyword)

        from robotframework_ls.impl.text_utilities import is_variable_text

        from robot.libraries.BuiltIn import BuiltIn
        from robot.api import get_model
        from robotframework_ls.impl import ast_utils

        # We can't really use
        # BuiltIn().evaluate(expression, modules, namespace)
        # because we can't set the variable_store used with it
        # (it always uses the latest).

        variable_store = info.variables.store

        if is_variable_text(self.expression):
            try:
                value = variable_store[self.expression[2:-1]]
            except Exception:
                pass
            else:
                return EvaluationResult(value)

        # Do we want this?
        # from robot.variables.evaluation import evaluate_expression
        # try:
        #     result = evaluate_expression(self.expression, variable_store)
        # except Exception:
        #     log.exception()
        # else:
        #     return EvaluationResult(result)

        # Try to check if it's a KeywordCall.
        s = (
            """
*** Test Cases ***
Evaluation
    %s
"""
            % self.expression
        )
        model = get_model(s)
        usage_info = list(ast_utils.iter_keyword_usage_tokens(model))
        if len(usage_info) == 1:
            _stack, node, _token, name = next(iter(usage_info))

            dap_frames = stack_info.dap_frames
            if dap_frames:
                top_frame_id = dap_frames[0].id
                if top_frame_id != frame_id:
                    if get_log_level() >= 2:
                        log.debug(
                            "Unable to evaluate.\nFrame id for evaluation: %r\nTop frame id: %r.\nDAP frames:\n%s",
                            frame_id,
                            top_frame_id,
                            "\n".join(x.to_json() for x in dap_frames),
                        )

                    raise UnableToEvaluateError(
                        "Keyword calls may only be evaluated at the topmost frame."
                    )

                return EvaluationResult(BuiltIn().run_keyword(name, *node.args))

        raise UnableToEvaluateError("Unable to evaluate: %s" % (self.expression,))

    def evaluate(self, debugger_impl):
        """
        :param _RobotDebuggerImpl debugger_impl:
        """
        try:
            r = self._do_eval(debugger_impl)
            self.future.set_result(r.result)
        except Exception as e:
            log.exception("Error evaluating: %s", self.expression)
            self.future.set_exception(e)


class _RobotDebuggerImpl(object):
    """
    This class provides the main API to deal with debugging
    Robot Framework.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        from collections import deque

        self._filename_to_line_to_breakpoint = {}
        self.busy_wait = BusyWait()

        self._run_state = STATE_RUNNING
        self._step_cmd = None
        self._reason = None
        self._next_id = next_id
        self._stack_ctx_entries_deque = deque()
        self._stop_on_stack_len = 0

        self._tid_to_stack_list = {}
        self._frame_id_to_tid = {}
        self._evaluations = []
        self._skip_breakpoints = 0

    @property
    def stop_reason(self):
        return self._reason

    def _get_stack_info_from_frame_id(self, frame_id):
        thread_id = self._frame_id_to_tid.get(frame_id)
        if thread_id is not None:
            return self._get_stack_info(thread_id)

    def _get_stack_info(self, thread_id):
        """
        :return _StackInfo
        """
        return self._tid_to_stack_list.get(thread_id)

    def get_frames(self, thread_id):
        stack_info = self._get_stack_info(thread_id)
        if not stack_info:
            return None
        return stack_info.dap_frames

    def get_scopes(self, frame_id):
        tid = self._frame_id_to_tid.get(frame_id)
        if tid is None:
            return None

        stack_info = self._get_stack_info(tid)
        if not stack_info:
            return None
        return stack_info.get_scopes(frame_id)

    def get_variables(self, variables_reference):
        for stack_list in list(self._tid_to_stack_list.values()):
            variables = stack_list.get_variables(variables_reference)
            if variables is not None:
                return variables

    def _get_filename(self, obj, msg):
        try:
            source = obj.source
            if source is None:
                return u"None"

            filename, _changed = file_utils.norm_file_to_client(source)
        except:
            filename = u"<Unable to get %s filename>" % (msg,)
            log.exception(filename)

        return filename

    def _create_stack_info(self, thread_id):
        stack_info = _StackInfo()

        for entry in reversed(self._stack_ctx_entries_deque):
            try:
                if entry.__class__ == _StepEntry:
                    keyword = entry.keyword
                    variables = entry.variables
                    filename = self._get_filename(keyword, u"Keyword")

                    frame_id = stack_info.add_keyword_entry_stack(
                        keyword, filename, variables
                    )

                elif entry.__class__ == _SuiteEntry:
                    name = u"TestSuite: %s" % (entry.name,)
                    filename = self._get_filename(keyword, u"TestSuite")

                    frame_id = stack_info.add_suite_entry_stack(name, filename)

                elif entry.__class__ == _TestEntry:
                    name = u"TestCase: %s" % (entry.name,)
                    filename = self._get_filename(keyword, u"TestCase")

                    frame_id = stack_info.add_test_entry_stack(
                        name, filename, entry.lineno
                    )
            except:
                log.exception("Error creating stack trace.")

        for frame_id in stack_info.iter_frame_ids():
            self._frame_id_to_tid[frame_id] = thread_id

        self._tid_to_stack_list[thread_id] = stack_info

    def _dispose_stack_info(self, thread_id):
        stack_list = self._tid_to_stack_list.pop(thread_id)
        for frame_id in stack_list.iter_frame_ids():
            self._frame_id_to_tid.pop(frame_id)

    def wait_suspended(self, reason):
        from robotframework_debug_adapter.constants import MAIN_THREAD_ID

        log.info("wait_suspended", reason)
        self._create_stack_info(MAIN_THREAD_ID)
        try:
            self._run_state = STATE_PAUSED
            self._reason = reason

            self.busy_wait.pre_wait()

            while self._run_state == STATE_PAUSED:
                self.busy_wait.wait()

                evaluations = self._evaluations
                self._evaluations = []

                for evaluation in evaluations:  #: :type evaluation: _EvaluationInfo
                    self._skip_breakpoints += 1
                    try:
                        evaluation.evaluate(self)
                    finally:
                        self._skip_breakpoints -= 1

            if self._step_cmd == STEP_NEXT:
                self._stop_on_stack_len = len(self._stack_ctx_entries_deque)

            elif self._step_cmd == STEP_OUT:
                self._stop_on_stack_len = len(self._stack_ctx_entries_deque) - 1

        finally:
            self._dispose_stack_info(MAIN_THREAD_ID)

    def evaluate(self, frame_id, expression):
        """
        Asks something to be evaluated.
        
        This is an asynchronous operation and returns an _EvaluationInfo (to get
        the result, access _EvaluationInfo.future.result())
        
        :param frame_id:
        :param expression:
        :return _EvaluationInfo:
        """
        evaluation_info = _EvaluationInfo(frame_id, expression)
        self._evaluations.append(evaluation_info)
        self.busy_wait.proceed()
        return evaluation_info

    def step_continue(self):
        self._step_cmd = None
        self._run_state = STATE_RUNNING
        self.busy_wait.proceed()

    def step_in(self):
        self._step_cmd = STEP_IN
        self._run_state = STATE_RUNNING
        self.busy_wait.proceed()

    def step_next(self):
        self._step_cmd = STEP_NEXT
        self._run_state = STATE_RUNNING
        self.busy_wait.proceed()

    def step_out(self):
        self._step_cmd = STEP_OUT
        self._run_state = STATE_RUNNING
        self.busy_wait.proceed()

    def set_breakpoints(self, filename: str, breakpoints):
        """
        :param str filename:
        :param list(RobotBreakpoint) breakpoints:
        """
        if isinstance(breakpoints, RobotBreakpoint):
            breakpoints = (breakpoints,)
        filename = file_utils.get_abs_path_real_path_and_base_from_file(filename)[1]
        line_to_bp = {}
        for bp in breakpoints:
            log.info("Set breakpoint in %s: %s", filename, bp.lineno)
            line_to_bp[bp.lineno] = bp
        self._filename_to_line_to_breakpoint[filename] = line_to_bp

    # ------------------------------------------------- RobotFramework listeners

    def before_run_step(self, step_runner, step, name=None):
        ctx = step_runner._context
        self._stack_ctx_entries_deque.append(_StepEntry(ctx.variables.current, step))
        if self._skip_breakpoints:
            return

        try:
            lineno = step.lineno
            source = step.source
        except AttributeError:
            return

        source = file_utils.get_abs_path_real_path_and_base_from_file(source)[1]
        log.debug(
            "run_step %s, %s - step: %s - %s\n", step, lineno, self._step_cmd, source
        )
        lines = self._filename_to_line_to_breakpoint.get(source)

        stop_reason = None
        step_cmd = self._step_cmd
        if lines and step.lineno in lines:
            stop_reason = REASON_BREAKPOINT

        elif step_cmd is not None:
            if step_cmd == STEP_IN:
                stop_reason = REASON_STEP

            elif step_cmd in (STEP_NEXT, STEP_OUT):
                if len(self._stack_ctx_entries_deque) <= self._stop_on_stack_len:
                    stop_reason = REASON_STEP

        if stop_reason is not None:
            self.wait_suspended(stop_reason)

    def after_run_step(self, step_runner, step, name=None):
        self._stack_ctx_entries_deque.pop()

    def start_suite(self, data, result):
        self._stack_ctx_entries_deque.append(_SuiteEntry(data.name, data.source))

    def end_suite(self, data, result):
        self._stack_ctx_entries_deque.pop()

    def start_test(self, data, result):
        self._stack_ctx_entries_deque.append(
            _TestEntry(data.name, data.source, data.lineno)
        )

    def end_test(self, data, result):
        self._stack_ctx_entries_deque.pop()


def _patch(
    execution_context_cls, impl, method_name, call_before_method, call_after_method
):

    original_method = getattr(execution_context_cls, method_name)

    @functools.wraps(original_method)
    def new_method(*args, **kwargs):
        call_before_method(*args, **kwargs)
        try:
            ret = original_method(*args, **kwargs)
        finally:
            call_after_method(*args, **kwargs)
        return ret

    setattr(execution_context_cls, method_name, new_method)


def patch_execution_context(new_session=True):
    try:
        impl = patch_execution_context.impl
    except AttributeError:
        # Note: only patches once, afterwards, returns the same instance.
        from robot.running.steprunner import StepRunner
        from robotframework_debug_adapter.listeners import DebugListener

        impl = _RobotDebuggerImpl()

        DebugListener.on_start_suite.register(impl.start_suite)
        DebugListener.on_end_suite.register(impl.end_suite)

        DebugListener.on_start_test.register(impl.start_test)
        DebugListener.on_end_test.register(impl.end_test)

        _patch(StepRunner, impl, "run_step", impl.before_run_step, impl.after_run_step)
        patch_execution_context.impl = impl
    else:
        if new_session:
            impl.reset()

    return patch_execution_context.impl
