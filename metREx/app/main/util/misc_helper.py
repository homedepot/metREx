def str_to_bool(x):
    x = str(x)

    return x.lower() in ('true', 't', 'yes', 'y', '1')
