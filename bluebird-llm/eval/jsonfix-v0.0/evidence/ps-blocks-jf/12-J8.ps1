Get-ChildItem -LiteralPath C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\out-T-jf,C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\pre-T-jf -File | Get-FileHash -Algorithm SHA256 | Select-Object Hash,Path
Get-FileHash -Algorithm SHA256 -LiteralPath C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\eval-T-jf.out,C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\eval-T-jf.err | Select-Object Hash,Path
$expect = [ordered]@{
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\out-T\EVAL.SHA256' = '5d0873c68712a1531acb6ef95c52702cef85ce786cccfe547754146b0d2d7f64'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\out-T\predictions-bluebird-v1.0-e2.jsonl' = '8b2fab1571464515bf517419d84e476a99b847d65245110491b5883fc7f3fed3'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\out-T\run-bluebird-v1.0-e2.json' = 'ee85fbb619fbf7ba226acb302256298aa1231bc1e4b6f47e79973f090b600e44'
}
foreach ($f in $expect.Keys) { $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash; if ($h -eq $expect[$f]) { "OK    $h  $f" } else { "FAIL  $h  $f" } }
Get-ChildItem -LiteralPath C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\out-T -Force | Select-Object Name,Length
