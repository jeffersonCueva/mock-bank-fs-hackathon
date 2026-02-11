@echo off
title Mock Bank Launcher

REM ------------------------------------
REM Adjust this if your venv folder name is different
REM ------------------------------------
REM call mock_bank\Scripts\activate

REM ------------------------------------
REM Start Bank A
REM ------------------------------------
@REM python -m uvicorn run_bank_gcash:app --port 8000 --reload
start "GCash" cmd /k "set BANK_NAME=gcash && python -m uvicorn run_bank_gcash:app --port 8002 --reload"


REM ------------------------------------
REM Start Bank B
REM ------------------------------------
@REM python -m uvicorn run_bank_bpi:app --port 8001 --reload

start "BPI" cmd /k "set BANK_NAME=bpi && python -m uvicorn run_bank_bpi:app --port 8003 --reload"

REM ------------------------------------
REM Start Clearing House
REM ------------------------------------
start "Clearing House" cmd /k "python -m uvicorn clearing_house.main:app --port 9000 --reload"

echo All services started.
exit
