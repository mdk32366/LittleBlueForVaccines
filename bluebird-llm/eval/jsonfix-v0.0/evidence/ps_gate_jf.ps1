# jf0.0: run the J3 gate's classifier line (taken verbatim from ps-blocks-jf/04-J3.ps1, line 1) against mock Win32_Process objects.
# A function named Get-CimInstance shadows the cmdlet (function > cmdlet precedence), so no system process is read. nvidia-smi line not run.
param([string]$Block)
function Get-CimInstance { param($ClassName)
  $d = [datetime]'2026-11-12 14:20:35'
  $app1 = '"C:\Users\mdk32\venvs\littleblue-app\Scripts\python.exe" "C:\Users\mdk32\venvs\littleblue-app\Scripts\streamlit.exe" run app.py --server.address 127.0.0.1 --server.headless true'
  $app2 = '"C:\Users\mdk32\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\mdk32\venvs\littleblue-app\Scripts\streamlit.exe" run app.py --server.address 127.0.0.1 --server.headless true'
  @(
    [pscustomobject]@{ ProcessId = 21896; Name = 'python.exe'; CreationDate = $d; CommandLine = $app1; Case = 'M1 known app parent -> KNOWN-EXCEPTION' }
    [pscustomobject]@{ ProcessId = 2580; Name = 'python.exe'; CreationDate = $d; CommandLine = $app2; Case = 'M2 known app child -> KNOWN-EXCEPTION' }
    [pscustomobject]@{ ProcessId = 2580; Name = 'python.exe'; CreationDate = $d.AddSeconds(1); CommandLine = $app2; Case = 'M3 same pid, other start time (pid reused) -> STOP' }
    [pscustomobject]@{ ProcessId = 21896; Name = 'python.exe'; CreationDate = $d; CommandLine = $app1 + ' eval.py'; Case = 'M4 known pid but eval.py in cmd -> STOP' }
    [pscustomobject]@{ ProcessId = 9448; Name = 'python.exe'; CreationDate = [datetime]'2026-11-16 08:00:00'; CommandLine = 'C:\Users\mdk32\venvs\bia562-train\Scripts\python.exe -B eval.py --model x'; Case = 'M5 live eval -> STOP' }
    [pscustomobject]@{ ProcessId = 7777; Name = 'pwsh.exe'; CreationDate = [datetime]'2026-11-16 08:00:00'; CommandLine = 'pwsh -c python eval.py'; Case = 'M6 wrapper mentioning eval.py -> STOP (N44 fail-safe)' }
    [pscustomobject]@{ ProcessId = 1344; Name = 'dwm.exe'; CreationDate = $d; CommandLine = $null; Case = 'M7 non-python, no eval.py -> not listed' }
    [pscustomobject]@{ ProcessId = 5555; Name = 'python.exe'; CreationDate = $d; CommandLine = $null; Case = 'M8 python with hidden cmd -> STOP' }
    [pscustomobject]@{ ProcessId = 3333; Name = 'python.exe'; CreationDate = $d; CommandLine = '"C:\x\venvs\littleblue-app\Scripts\streamlit.exe" run app.py --x'; Case = 'M9 app cmd but other pid -> STOP' }
  )
}
$line = (Get-Content -LiteralPath $Block)[0]
'MOCK CASES:'; Get-CimInstance -ClassName Win32_Process | ForEach-Object { '  ' + $_.Case }
'GATE OUTPUT:'
Invoke-Expression $line
