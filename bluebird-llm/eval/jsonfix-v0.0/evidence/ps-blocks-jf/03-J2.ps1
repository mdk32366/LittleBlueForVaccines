$expect = [ordered]@{
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\RUN-INPUTS.SHA256' = 'c5db63e4a0194582245692c73ef7333297bf27dc46dd298ce55f98fa58903871'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\eval_rows.jsonl' = 'dd3fc66d50373f123ce4f76602658794a438f6250c0953e8fffa7c84934db899'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\fewshot.json' = 'a27d1f08e6a85afd728ae76d65ee62f3e7b4901bc7bdfdbd79c92b013b3e9f07'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\eval.py' = '772189be5b30ea03dccef4f49b77260d91b17f1d52ab1ddfa6945621082d6874'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\evalcore.py' = '2d1d2f9bc0716938278a6d9dee9d19830ec673721c68d0753390127c3104ba75'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00\jsonslot.py' = '38c79c58be1049f04ac18f6973db5e54c7ddaf5a01b62d4d870d56a08612f956'
}
foreach ($f in $expect.Keys) { $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash; if ($h -eq $expect[$f]) { "OK    $h  $f" } else { "FAIL  $h  $f" } }
