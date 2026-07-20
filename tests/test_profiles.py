import sys
sys.path.append(".")
import pandas as pd
from src.profiles import robust_profile

def test_median_resistant_to_one_outlier():
    normal=pd.Series([800, 800, 820, 800, 9000])
    stats=robust_profile(normal)
    assert 795<stats["centre"]<825