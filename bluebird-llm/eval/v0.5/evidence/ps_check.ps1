# @0.5: parse (never run) each extracted §g PowerShell block with the PowerShell parser. Args: a dir of NN-name.ps1 files. Prints one line per block.
param([string]$Dir)
Get-ChildItem -LiteralPath $Dir -Filter '*.ps1' | Sort-Object Name | ForEach-Object {
  $t = $null; $e = $null
  [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$t, [ref]$e)
  if ($e.Count -eq 0) { 'PARSE OK      {0}' -f $_.Name } else { 'PARSE ERRORS  {0}: {1}' -f $_.Name, (($e | ForEach-Object { 'line {0}: {1}' -f $_.Extent.StartLineNumber, $_.Message }) -join ' | ') }
}
