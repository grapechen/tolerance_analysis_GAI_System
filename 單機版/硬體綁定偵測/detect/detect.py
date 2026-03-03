# -*- coding: utf-8 -*-
"""
Created on Thu Jan 13 22:11:35 2022

@author: user
"""

import wmi
import cryptocode

c = wmi.WMI()   
data_str = ""

item1 = c.Win32_PhysicalMedia()[0]
item2 = c.Win32_VideoController()[0]
data_str += item1.wmi_property('SerialNumber').value
data_str += item2.PNPDeviceID
    
encode = cryptocode.encrypt(data_str, "975607")

path = 'output.txt'

with open(path, 'w') as f:
    f.write(encode)
    
