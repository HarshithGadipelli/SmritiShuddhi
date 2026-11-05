import sys
from pathlib import Path
print('Python:', sys.version)
try:
    import pymongo; print('PyMongo:', pymongo.__version__)
except Exception as e: print('PyMongo error:',e)
try:
    import sklearn; print('scikit-learn:', sklearn.__version__)
except Exception as e: print('scikit-learn error:',e)
print('Project:', Path(__file__).resolve().parents[1])
