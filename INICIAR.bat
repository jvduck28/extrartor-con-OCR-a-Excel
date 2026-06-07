@echo off
chcp 65001 >nul
title 🏦 Procesador de Planillas
color 0A

echo.
echo ╔══════════════════════════════════════════╗
echo ║  🏦 PROCESADOR DE PLANILLAS BANCARIAS   ║
echo ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python no encontrado
    echo Descargá: https://www.python.org/downloads/
    echo ⚠️ Marcá "Add to PATH" al instalar
    pause
    exit
)

REM Instalar librerías si faltan
echo 📦 Verificando librerías...
python -c "import pandas, openpyxl, fitz" 2>nul
if errorlevel 1 (
    echo Instalando librerías necesarias...
    pip install pandas openpyxl PyMuPDF pdf2image Pillow pytesseract -q
    echo ✅ Listo
)

echo.
echo 📁 Carpeta: %CD%
echo.
echo ═══════════════════════════════════════════
echo.

REM Ejecutar
python procesar.py %*

echo.
echo ═══════════════════════════════════════════
pause