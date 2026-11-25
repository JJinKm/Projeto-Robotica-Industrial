@echo off
setlocal
chcp 65001 >nul

rem Funciona tanto dentro da pasta do projeto quanto copiado para a Area de Trabalho:
rem se nao achar a pasta ELO ao lado deste arquivo, usa o caminho do projeto abaixo.
set "AEGIS_DIR=%~dp0"
if not exist "%AEGIS_DIR%ELO\AEGIS_RTDE.py" set "AEGIS_DIR=C:\Users\ADM\Desktop\Insper\7° Semestre\Robotica\projeto\elo-interface\"
if not exist "%AEGIS_DIR%ELO\AEGIS_RTDE.py" (
    echo Pasta do AEGIS nao encontrada. Edite AEGIS_DIR neste arquivo.
    pause
    exit /b 1
)
cd /d "%AEGIS_DIR%"

where py >nul 2>nul
if errorlevel 1 (
    echo Python Launcher nao encontrado. Instale o Python 3.12 e tente novamente.
    pause
    exit /b 1
)

py -3.12 --version >nul 2>nul
if errorlevel 1 (
    echo Python 3.12 nao encontrado. Instale o Python 3.12 antes de abrir o AEGIS.
    pause
    exit /b 1
)

set "ELO_VENV=%LOCALAPPDATA%\ELO\elo-rtde-env"
if not exist "%ELO_VENV%\Scripts\python.exe" (
    echo Preparando o ambiente do AEGIS pela primeira vez...
    py -3.12 -m venv "%ELO_VENV%"
    if errorlevel 1 (
        echo Nao foi possivel criar o ambiente Python.
        pause
        exit /b 1
    )
)

echo Conferindo as bibliotecas do AEGIS...
"%ELO_VENV%\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo Nao foi possivel instalar as bibliotecas. Confira sua conexao com a internet.
    pause
    exit /b 1
)

echo Conferindo os modelos 3D UR3e e UR5e...
"%ELO_VENV%\Scripts\python.exe" "%AEGIS_DIR%ELO\setup_models.py"
if errorlevel 1 (
    echo Os modelos 3D nao foram baixados. A interface ainda pode abrir sem internet.
)

echo Abrindo o AEGIS com controle dos robos...
"%ELO_VENV%\Scripts\python.exe" "%AEGIS_DIR%ELO\AEGIS_RTDE.py"
if errorlevel 1 (
    echo O AEGIS foi encerrado com erro. Confira as mensagens acima.
    pause
)

endlocal
