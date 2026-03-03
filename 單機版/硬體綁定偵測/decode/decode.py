# -*- coding: utf-8 -*-
"""
Created on Thu Jan 13 23:36:36 2022

@author: user
"""

import cryptocode

path = 'output.txt'

with open(path, 'r') as f:
    data = f.read()

decode =  cryptocode.decrypt(data, '975607')

print(decode)
input()

