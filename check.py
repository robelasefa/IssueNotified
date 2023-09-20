sets = {1, 2, 3, 4, 5, 6, 7, 8, 9}

dicts = dict(enumerate(sets, start=1))
dict2 =  dict(sets, value='No name')

print(dicts, "\n\n", dict2)