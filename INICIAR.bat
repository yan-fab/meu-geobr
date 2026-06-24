@echo off
title geoBR Explorer - Iniciando...
color 0A
echo.
echo  ============================================
echo   geoBR Explorer - Layer Builder + Frontend
echo  ============================================
echo.
echo  [1/3] Iniciando API do Layer Builder (porta 5050)...
wmic process call create "c:\Users\yanju\.gemini\antigravity\scratch\geo_workspace\layer_builder\start_api.bat" >nul 2>&1
timeout /t 5 /nobreak >nul

echo  [2/3] Iniciando Favela API (porta 5001)...
wmic process call create "cmd /c cd /d c:\Users\yanju\.gemini\antigravity\scratch\geo_workspace\layer_builder && python favela_api.py" >nul 2>&1
timeout /t 3 /nobreak >nul

echo  [3/3] Iniciando servidor web do frontend (porta 8080)...
wmic process call create "cmd /c cd /d c:\Users\yanju\.gemini\antigravity\scratch\geobr\frontend && python -m http.server 8080" >nul 2>&1
timeout /t 3 /nobreak >nul

echo.
echo  Verificando servicos...
timeout /t 2 /nobreak >nul

echo.
echo  Servidores iniciados em background!
echo.
echo  Frontend:    http://localhost:8080
echo  API Builder: http://localhost:5050/api/health
echo  Favela API:  http://localhost:5001/api/favelas/all
echo.
echo  Abrindo navegador...
start http://localhost:8080/index.html
echo.
echo  Para parar os servidores, use o Gerenciador de Tarefas (python.exe)
echo.
pause
