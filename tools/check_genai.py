import google, sys, importlib
print('google __file__=', getattr(google,'__file__',None))
print('has genai attr=', hasattr(google,'genai'))
print('sys.path[0..8]=')
for p in sys.path[:9]: print('  ', p)
try:
    m = importlib.import_module('google.genai')
    print('imported google.genai from', getattr(m,'__file__', None))
except Exception as e:
    print('import google.genai failed:', e)
