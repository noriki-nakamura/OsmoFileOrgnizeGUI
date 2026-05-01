@echo off
REM ============================================================
REM  build.bat  -  OsmoFileOrganize .exe ビルドスクリプト
REM ============================================================
REM 使い方: このファイルをダブルクリック、または
REM         コマンドプロンプトで build.bat を実行してください。
REM
REM 出力先: dist\OsmoFileOrganize.exe
REM ============================================================

echo [OSMO Build] ビルドを開始します...
echo.

REM ビルドに必要な環境の準備 (uv sync)
echo [OSMO Build] 依存関係を同期しています...
uv sync
if %ERRORLEVEL% neq 0 (
    echo [OSMO Build] uv sync に失敗しました。
    exit /b %ERRORLEVEL%
)

REM 古いビルド成果物を削除
if exist dist\OsmoFileOrganize.exe (
    echo [OSMO Build] 古い dist\OsmoFileOrganize.exe を削除しています...
    del /f /q dist\OsmoFileOrganize.exe
)

REM PyInstaller でビルド
echo [OSMO Build] PyInstaller を実行しています...
uv run pyinstaller OsmoFileOrganize.spec --noconfirm

echo.
if %ERRORLEVEL% == 0 (
    echo ============================================
    echo  ビルド成功！
    echo  出力ファイル: dist\OsmoFileOrganize.exe
    echo ============================================
) else (
    echo ============================================
    echo  ビルド失敗。上のエラーメッセージを確認してください。
    echo ============================================
)

echo.
pause
