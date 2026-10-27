@echo off
REM Systemized Drawing Subsystem Extractor - BATCH mode.
REM Put every "<PLANT> Systemized <TYPE>.pdf" you want processed in
REM this folder, then double-click this file. Plant and doc type are
REM read from each filename - no config editing needed.
REM Results land in the output folder.

echo ============================================
echo  Extracting subsystems from all PDFs here...
echo ============================================
set /p SUBS="Which subsystems? Type one (33-05), several (33-05 50-08), or just press Enter for ALL: "
echo.
python extract_all.py %SUBS%
if errorlevel 1 goto :err

echo.
echo DONE. Your files are in the output folder.
pause
exit /b 0

:err
echo.
echo Something went wrong. Take a screenshot of the error and send
echo it over - do not re-run until we look at it.
pause
exit /b 1
