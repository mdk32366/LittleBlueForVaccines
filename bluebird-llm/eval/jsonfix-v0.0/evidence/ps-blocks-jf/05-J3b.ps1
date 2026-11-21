Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" | Select-Object ProcessId,Name,CommandLine
