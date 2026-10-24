@echo off
setlocal

if "%DOCS_HARNESS_ROOT%"=="" (
  echo docs-harness router: DOCS_HARNESS_ROOT is required 1>&2
  exit /b 0
)

set "PYTHON="
set "PYTHON_ARGS="
for %%P in (python python3) do (
  if not defined PYTHON (
    %%P -c "import sys" >nul 2>nul && set "PYTHON=%%P"
  )
)
if not defined PYTHON (
  py -3 -c "import sys" >nul 2>nul && set "PYTHON=py" && set "PYTHON_ARGS=-3"
)
if not defined PYTHON (
  echo docs-harness router: python not found 1>&2
  exit /b 0
)

"%PYTHON%" %PYTHON_ARGS% "%DOCS_HARNESS_ROOT%\routing\hosts\qoder\route_hook.py"
exit /b %ERRORLEVEL%
