nvidia-smi --query-gpu=name,memory.used,memory.total,temperature.gpu --format=csv
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
Get-CimInstance -ClassName Win32_Battery | Select-Object BatteryStatus,EstimatedChargeRemaining
powercfg /getactivescheme
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE
powercfg /query SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE
Get-PSDrive C
Test-Path -LiteralPath C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\jf00
Test-Path -LiteralPath C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\out-T\eval.lock
"STATUS $((Get-Content -LiteralPath C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\out-T\run-bluebird-v1.0-e2.json -Raw | ConvertFrom-Json).status)"
$expect = [ordered]@{
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\out-T\EVAL.SHA256' = '5d0873c68712a1531acb6ef95c52702cef85ce786cccfe547754146b0d2d7f64'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\out-T\predictions-bluebird-v1.0-e2.jsonl' = '8b2fab1571464515bf517419d84e476a99b847d65245110491b5883fc7f3fed3'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\out-T\run-bluebird-v1.0-e2.json' = 'ee85fbb619fbf7ba226acb302256298aa1231bc1e4b6f47e79973f090b600e44'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\adapter\ADAPTER.SHA256' = '35589c33dcc605024b44f6cadecae002998ffff4ecb75a7c52d5432f2988251b'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\adapter\final-adapter\adapter_config.json' = '11e460712a1fc783799e0a3b336b2a94d8b566b86cfc16a51364dd7a3470511f'
 'C:\Users\mdk32\lb-eval-bluebird-v1.0-r03\adapter\final-adapter\adapter_model.safetensors' = '3b4166836c840e4e1661e030aad42e0c0c00c31b01aede65be98520cf007112d'
 'C:\Users\mdk32\models\Qwen2.5-3B-Instruct\tokenizer.json' = 'c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539'
}
foreach ($f in $expect.Keys) { $h = (Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash; if ($h -eq $expect[$f]) { "OK    $h  $f" } else { "FAIL  $h  $f" } }
& C:\Users\mdk32\venvs\bia562-train\Scripts\python.exe -B -c "import torch,transformers,peft,bitsandbytes as b;print(torch.__version__,torch.version.cuda,transformers.__version__,peft.__version__,b.__version__)"
