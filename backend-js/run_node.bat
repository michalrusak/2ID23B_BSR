@echo off
echo Starting 6 blockchain nodes...

FOR /L %%N IN (1,1,6) DO (
    echo Starting node node%%N...
    start "Node node%%N" cmd /c "node src/blockchain/node.js node%%N"
)

echo All nodes are being started in separate windows.
