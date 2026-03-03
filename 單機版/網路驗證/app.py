# -*- coding: utf-8 -*-
"""
Created on Thu Jan 27 08:55:49 2022

@author: jerry
"""

from flask import Flask, jsonify, Response, request
import json, cryptocode

app = Flask(__name__)

check_list = [r"ACE4_2E00_1A2D_8B4D_2EE4_AC00_0000_0001.PCI\VEN_10DE&DEV_1F9D&SUBSYS_15361025&REV_A1\4&C337064&0&0009",
              r"324C_3233_3239_4137_00E0_4C15_7BA3_C36E.PCI\VEN_10DE&DEV_21C4&SUBSYS_C75A1462&REV_A1\4&37732CF4&0&0008",
              r"     WD-WCC6Y6FVSD08PCI\VEN_10DE&DEV_1C03&SUBSYS_85AC1043&REV_A1\4&FC7F53B&0&0018",
              r"0008_0D04_0009_3E7B.PCI\VEN_8086&DEV_5916&SUBSYS_00261414&REV_02\3&11583659&0&10",
              r"        WCC6Y5XUN8FHPCI\VEN_8086&DEV_3E98&SUBSYS_12491025&REV_02\3&11583659&0&10",
              r"     WD-WCC6Y0DXXFR9PCI\VEN_10DE&DEV_2184&SUBSYS_37921462&REV_A1\4&35E0AEB3&0&0008",
              r"            ZFL1V6RSPCI\VEN_10DE&DEV_2184&SUBSYS_37921462&REV_A1\4&1FC990D7&0&0019",
              r"            5VPA84RJPCI\VEN_1002&DEV_6938&SUBSYS_2350148C&REV_F1\4&3834D97&0&0008",
              r"2L102LQQ8ERC        _00000001.PCI\VEN_10DE&DEV_1380&SUBSYS_37513842&REV_A2\4&1DA95F35&0&0019",
              r"           618VXUGNSPCI\VEN_10DE&DEV_2504&SUBSYS_463019DA&REV_A1\4&38AB2860&0&0008",
              r"0000_0000_0000_0000_8CE3_8E03_008E_2D5E.PCI\VEN_8086&DEV_A7A0&SUBSYS_18031043&REV_04\3&11583659&0&10",
              r"0000_0000_0100_0000_E4D2_5CCC_8E44_5401.PCI\VEN_8086&DEV_9A49&SUBSYS_1EBF1043&REV_01\3&11583659&0&10",
              
            ]

@app.route('/aaaaa/', methods=['POST'])
def test_api():
    data = cryptocode.decrypt(request.values["pw"], "923923923975607")
    if data in check_list:
        ret_data = cryptocode.encrypt("OKKKKK~~", "923923923975607")
        return jsonify(message=ret_data)
    else:
        ret_data = cryptocode.encrypt("NOOOOO!", "923923923975607")
        return jsonify(message=ret_data)

    
@app.route('/test_api/', methods=['GET'])
def test_api2():
    return jsonify(message='test OK!')

if __name__ == '__main__':
    # app.run(ssl_context=('server.crt', 'server.key'))
    app.run()