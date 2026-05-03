try:
    import fer
    print('fer imported from', fer.__file__)
    from fer import FER
    print('FER class ok', FER)
except Exception as e:
    print(type(e).__name__, e)
