@echo off
setlocal
set "CONFIG=%~dp0launcher\LeanControl.Launcher.json"
for /f "tokens=2 delims=:," %%A in ('findstr /i "\"url\"" "%CONFIG%"') do set "APP_URL=%%~A"
set "APP_URL=%APP_URL: =%"
set "APP_URL=%APP_URL:\"=%"
if not defined APP_URL (
  echo URL nao encontrada em %CONFIG%
  pause
  exit /b 1
)
start "" "%APP_URL%"
endlocal

