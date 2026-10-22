#!/bin/bash
echo "Сторож запущен. Ждём завершения build_index_v3_jsonl.py..."
while pgrep -f "python build_index_v3_jsonl.py" > /dev/null; do
    sleep 30
done
echo "Скрипт завершён! Ждём 2 минуты..."
sleep 120
cd /mnt/c/
echo "Выключаю компьютер..."
cmd.exe /c "shutdown /s /t 0"
