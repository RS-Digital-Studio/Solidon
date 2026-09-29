Set-Location 'F:\3D Druck\.claude\.state\uebergabe-gesamt-2026-09-27'
$env:PYTHONUTF8 = '1'
& 'C:\Program Files\Git\bin\bash.exe' alle_plaene.sh > 'F:\3D Druck\output\review\gesamt-2026-09-27\plaene.txt' 2>&1
"Exit: $LASTEXITCODE" | Out-File 'F:\3D Druck\output\review\gesamt-2026-09-27\plaene-exit.txt'
