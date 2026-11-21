## S (fewshot, batch 8): 447 batches, last batch 1 row(s)
- smoke batches (full-run index: max prompt tokens): 0: 697, 64: 1009, 127: 1023, 191: 1029, 254: 1037, 318: 1243, 381: 1879, 445: 1994
- rows in batches 0-364: 2920 (= 'after row 2920'); remaining batches 365-446: 82 batches, 649 rows
- max prompt tokens: batch 363 1780, 364 1780, remaining 1783-1994
- remaining batches, max prompt tokens per batch: 1783 1785 1786 1788 1791 1797 1803 1837 1851 1859 1860 1863 1865 1866 1869 1874 1879 1884 1889 1891 1893 1895 1897 1898 1899 1901 1901 1903 1904 1905 1906 1907 1909 1911 1912 1913 1914 1915 1917 1918 1919 1922 1923 1923 1925 1927 1928 1930 1932 1933 1934 1936 1939 1940 1942 1942 1944 1946 1947 1950 1954 1956 1958 1959 1960 1963 1964 1965 1966 1967 1969 1970 1971 1972 1973 1976 1978 1983 1988 1992 1994 1994
- padded prompt tokens per batch, remaining / batches 0-364: 1.700
## T (zero, batch 8): 447 batches, last batch 1 row(s)
- smoke batches (full-run index: max prompt tokens): 0: 111, 64: 423, 127: 437, 191: 443, 254: 451, 318: 657, 381: 1293, 445: 1408
## Measured peaks (box copies)
- smoke S per-batch cumulative peak_alloc: [2753126400, 3971223040, 4011912192, 4030207488, 4030207488, 4030207488, 4030207488, 4030207488]; session peak_alloc 4030207488, peak_reserved 6490685440 (reserved/alloc 1.611)
- smoke T per-batch cumulative peak_alloc: [2366736896, 2851532800, 2874707968, 2885064704, 2900426752, 3219714560, 4215678464, 4403054592]; session peak_alloc 4403054592, peak_reserved 7059013632 (reserved/alloc 1.603)
- PREFLIGHT-2: gpu_free_at_start 7385120768, gpu_total 8546484224, preflight peak_alloc 2253176832, peak_reserved 2422210560
## Emma-reported (laptop, 7:40 PM PT; not on the box)
- full S: peak_alloc 6990548992 after batch 363; ABORT 3 peak_alloc 7001188352 after row 2920 (batch 364); full T (E4): about 5.28e9
## Model
- length model rejected: smoke S ran full-run batches 381 and 445 (the longest full batch, 1994 tokens) in a fresh session at <= 4030207488; under a length model batch 445 would need >= 7.0e9
- in-session growth: (7001188352 - 4030207488) / 365 = 8139674 B per batch on average (T: (5.28e9 - 4403054592) / 447 = 1961847, Emma-reported endpoint)
- fresh-session projection, growth per batch: 4030207488 + 667453235 = 4697660723; margin to 7.0e9 2302339277
- fresh-session projection, growth per padded prompt token: 4030207488 + 1134385505 = 5164592993; margin to 7.0e9 1835407007
- growth rate needed to reach 7.0e9 within 82 batches from 4030207488: 36216982 B per batch = 4.45 x the observed average
- VRAM: free at start 7385120768 of 8546484224; at 7.0e9 allocated the reserved pool is >= 7.0e9, i.e. within 385120768 B of all free memory
- not fitted: the per-batch curve of the stopped session (only in the laptop's eval-S.out; E5-S1-keep copies it and e5s1_check.py fits it)
