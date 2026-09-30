@echo off
setlocal enabledelayedexpansion

REM Traverse all files in current directory and subdirectories
for /r %%f in (*) do (
    set "fullpath=%%f"
    set "filename=%%~nxf"
    
    REM Replace may, May, or MAY with June in the filename
    set "newname=!filename:august=September!"
    set "newname=!newname:August=September!"
    set "newname=!newname:AUGUST=September!"
    
    REM If filename was changed, rename the file
    if not "!filename!"=="!newname!" (
        echo Renaming "%%~nxf" to "!newname!"
        ren "%%f" "!newname!"
    )
)

echo Done.
pause
