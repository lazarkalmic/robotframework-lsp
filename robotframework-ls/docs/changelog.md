New in 0.3.0 (2020-07-01)
-----------------------------

 - Go to definition for variables.
 - Code completion for `Resource Imports` and `Library Imports`.
 - Go to definition support for `Resource Imports` and `Library Imports`.
 - Do code analysis in a separate process (i.e.: code-completion should not wait for code analysis).
 - Create cached document from filesystem (i.e.: ast is not recreated unless `.robot` file is changed).
 - Check spaces and unicode characters on pythonpath/resources/imports.
 - Config link in the vs code extension documentation is broken.


New in 0.2.3 (2020-06-16)
-----------------------------

- Variables: Code-completion for builtin variables.
- When a user library (.py) changes the related auto-generated spec is automatically updated.
- If `robot.python.executable` is set, it's used to launch the debugger.
- Debugger: step return implementation added.
- Properly Search for python and python3 on the PATH on Linux and Mac.


New in 0.2.2 (2020-06-09)
-----------------------------

- `robot.pythonpath` setting automatically passed as `--pythonpath` argument when launching.
- `robot.pythonpath` setting now used to locate resources and libraries for when resolving keywords. [#79](https://github.com/robocorp/robotframework-lsp/issues/79)
- `robot.variables` setting automatically passed as `--variable` argument when launching. 
- `robot.variables` setting is now used in code completion for variables. [#21](https://github.com/robocorp/robotframework-lsp/issues/21)
- Arguments shown in code completion when creating a Keyword. [#21](https://github.com/robocorp/robotframework-lsp/issues/21)
- Support for Library Import with `WITH NAME` syntax. [#64](https://github.com/robocorp/robotframework-lsp/issues/64)
- Typing info removed when completing keywords. [#89](https://github.com/robocorp/robotframework-lsp/issues/89)


New in 0.2.1 (2020-06-04)
-----------------------------

Critical bugfix to support the debugger with Setup/Teardown. [#85](https://github.com/robocorp/robotframework-lsp/issues/85)


New in 0.2.0 (2020-06-03)
-----------------------------

- Preliminary support for debugging. [#30](https://github.com/robocorp/robotframework-lsp/issues/30)
    - Note: this is an initial release for the feature and should be considered beta (please test and report any issues found).
    - The current functionalities include:
        - Add line breakpoints
        - Pause at breakpoints to inspect the stack and see variables
        - Step in
        - Step over
        - Continue
- Handling `text` only parameter in `textDocument/didChange`. [#78](https://github.com/robocorp/robotframework-lsp/issues/78)
- Updated VSCode client dependency versions. [#65](https://github.com/robocorp/robotframework-lsp/issues/65)
- Snippets code-completion for some constructs (`For In`, `Run Keyword If`). [#69](https://github.com/robocorp/robotframework-lsp/issues/69)


New in 0.1.1 (2020-05-11)
-----------------------------

- Variables code completion is provided for variables assigned to keyword return values. [#21](https://github.com/robocorp/robotframework-lsp/issues/21)
- Variables properly tokenized when completing for variables. [#21](https://github.com/robocorp/robotframework-lsp/issues/21)
- Show argument names in code completion. Fixes [#53](https://github.com/robocorp/robotframework-lsp/issues/53)
- No longer giving error if specified resource points to a directory. Fixes [#63](https://github.com/robocorp/robotframework-lsp/issues/63)
- `tab` now properly applies completions. [#52](https://github.com/robocorp/robotframework-lsp/issues/52)


New in 0.1.0 (2020-05-05)
-----------------------------

- Preliminary code completion support for variables defined in [Variable Tables](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#variable-table).
- Support for keywords defined with a library prefix  [#58](https://github.com/robocorp/robotframework-lsp/issues/58).
- Support for keywords with embededd arguments  [#59](https://github.com/robocorp/robotframework-lsp/issues/59).
- Support for keywords with Gherkin syntax (i.e.: given, when, then, etc) [#59](https://github.com/robocorp/robotframework-lsp/issues/59).


New in 0.0.10 (2020-04-28)
-----------------------------

- Code analysis: check if keywords are properly imported/defined (new in 0.0.10).
- Properly consider that keywords may appear in fixtures and templates (code analysis, code completion and go to definition).
- Add `args` placeholder to Robot launch configuration file (launching).
- Arguments are now shown in keyword documentation (code completion).
- Properly deal with path based library imports (code analysis, code completion and go to definition).


New in 0.0.9 (2020-04-20)
-----------------------------

- Go to definition implemented for keywords.
- Only environment variables set by the user when launching are passed when launching in integrated terminal.
- `~` is properly expanded when it's specified in the logging file.


New in 0.0.8 (2020-04-14)
-----------------------------

- Launch robotframework directly from VSCode (note: right now debugging is still not supported 
  -- a debug run will do a regular launch). Fixes [#29](https://github.com/robocorp/robotframework-lsp/issues/29)
- A setting to complete section headers only in the plural/singular form is now available (`robot.completions.section_headers.form`). Fixes [#42](https://github.com/robocorp/robotframework-lsp/issues/42)
- Improvements in syntax highlighting


New in 0.0.7 (2020-04-04)
-----------------------------

- Return empty list when code formatter has no changes. Fixes [#35](https://github.com/robocorp/robotframework-lsp/issues/35)
- Don't show keywords twice. Fixes [#34](https://github.com/robocorp/robotframework-lsp/issues/34)
- Improvements in syntax highlighting


New in 0.0.6 (2020-04-02)
-----------------------------

- Provide source code formatting with the Tidy builtin tool. Fixes [#26](https://github.com/robocorp/robotframework-lsp/issues/26)
- Fix for incomplete json message ([#33](https://github.com/robocorp/robotframework-lsp/issues/33)) and parsing of .resource ([#32](https://github.com/robocorp/robotframework-lsp/issues/32))


New in 0.0.5 (2020-03-30)
-----------------------------

- Add icon to extension. Fixes [#22](https://github.com/robocorp/robotframework-lsp/issues/22)
- Code completion for keywords.
- License is now Apache 2.0. Fixes [#24](https://github.com/robocorp/robotframework-lsp/issues/24)


New in 0.0.4 (2020-03-05)
-----------------------------

- Code completion for section internal names


New in 0.0.3 (2020-02-11)
-----------------------------

- Code completion for section headers


New in 0.0.2 (2020-02-09)
-----------------------------

- Various internal improvementss


New in 0.0.1 (2020-01-31)
-----------------------------

- Basic syntax highlighting
- Syntax validation