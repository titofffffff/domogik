#!/usr/bin/python
# -*- coding: utf-8 -*-

""" This file is part of B{Domogik} project (U{http://www.domogik.org}).

License
=======

B{Domogik} is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

B{Domogik} is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Domogik. If not, see U{http://www.gnu.org/licenses}.

Module purpose
==============

xPL X10 client

Implements
==========

- x10Main.__init__(self)
- x10Main.x10_cmnd_cb(self, message)
- x10Main.x10_monitor_cb(self, unit, order, args = None)

@author: Maxence Dunnewind <maxence@dunnewind.net>
@copyright: (C) 2007-2009 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

import os

if os.name == 'nt':
    from domogik.xpl.lib.win_x10 import *
else:
    from domogik.xpl.lib.x10 import *
from domogik.xpl.lib.xplconnector import *
from domogik.xpl.common.xplmessage import XplMessage
from domogik.xpl.lib.module import *
from domogik.common.configloader import Loader
from domogik.common import logger
from domogik.xpl.lib.queryconfig import *

class x10Main(xPLModule):

    def __init__(self):
        '''
        Create the X10Main class
        This class is used to connect x10 (through heyu) to the xPL Network
        '''
        xPLModule.__init__(self, name = 'x10')
        self._heyu_cfg_path_res = ""
        self._config = Query(self._myxpl)
        res = xPLResult()
        self._config.query('x10', 'heyu-cfg-path', res)
        self._heyu_cfg_path_res = res.get_value()['heyu-cfg-path']
        try:
            pass
            self.__myx10 = X10API(self._heyu_cfg_path_res)
        except:
            print "Something went wrong during heyu init, check logs"
            exit(1)
        #Create listeners
        Listener(self.x10_cmnd_cb, self._myxpl, {'schema': 'x10.basic',
                'xpltype': 'xpl-cmnd'})
        #One listener for system schema, allowing to reload config
        Listener(self.heyu_reload_config, self._myxpl, {'schema': 'domogik.system',
           'xpltype': 'xpl-cmnd', 'command': 'reload', 'module': 'x10'})
        #One listener for system schema, allowing to dump config
        Listener(self.heyu_dump_config, self._myxpl, {'schema': 'domogik.system',
            'xpltype': 'xpl-cmnd', 'command': 'push_config', 'module': 'x10'})
        self._log = self.get_my_logger()
#        self._monitor = X10Monitor(self._heyu_cfg_path_res)
#        self._monitor.get_monitor().add_cb(self.x10_monitor_cb)
#        self._monitor.get_monitor().start()
        self._log.debug("Heyu correctly started")

    def heyu_reload_config(self, message):
        '''
        Regenerate the heyu config file
        First, it needs to get all config items, then rewrite the config file
        and finally restart heyu
        '''
        #Heyu config items
        res = xPLResult()
#        self._config = Query(self._myxpl)
        self._config.query('x10','', res)
        result = res.get_value()
        if result is not None:
            heyu_config_items = filter(lambda k : k.startswith("heyu-file-"), result.keys())
            heyu_config_values = []
            for key in heyu_config_items:
                heyu_config_values.append(result[key])
            #Heyu path
            myheyu = HeyuManager(self._heyu_cfg_path_res)
            try:
                myheyu.write(heyu_config_values)
            except IOError:
                self._log.warning("Heyu config file can't be opened")
            res = myheyu.restart()
            if res:
                self._log.warning("Error during heyu restart : %s" % res)

        else:
            print "empty res"


    def heyu_dump_config(self, message):
        '''
        Send the heyu config file on the network
        '''
        res = xPLResult()
        #Heyu path
        myheyu = HeyuManager(self._heyu_cfg_path_res)
        lines = myheyu.load()
        m = XplMessage()
        m.set_type('xpl-trig')
        m.set_schema('domogik.config')
        count = 0
        for line in lines:
            key = "heyu_file_%s" % count
            count = count + 1
            m.add_data({key :  line})
        #print "Message is : %s" % m
        self._myxpl.send(m)


    def x10_cmnd_cb(self, message):
        '''
        General callback for all command messages
        '''
        commands = {
            'on': lambda d, h, l: self.__myx10.on(d),
            'off': lambda d, h, l: self.__myx10.off(d),
            'all_units_on': lambda d, h, l: self.__myx10.house_on(h),
            'all_units_off': lambda d, h, l: self.__myx10.house_off(h),
            'all_lights_on': lambda d, h, l: self.__myx10.lights_on(h),
            'all_lights_off': lambda d, h, l: self.__myx10.lights_off(h),
            'bright': lambda d, h, l: self.__myx10.bright(d, l),
            'dim': lambda d, h, l: self.__myx10.dim(d, l),
            'brightb': lambda d, h, l: self.__myx10.brightb(d, l),
            'dimb': lambda d, h, l: self.__myx10.dimb(d, l),
        }
        cmd = None
        dev = None
        house = None
        level = None
        if 'command' in message:
            cmd = message.data['command']
        if 'device' in message:
            dev = message.data['device']
        if 'house' in message:
            house = message.data['house']
        if 'level' in message:
            level = message.data['level']
        self._log.debug("%s received : device = %s, house = %s, level = %s" % (
                cmd, dev, house, level))
        commands[cmd](dev, house, level)

    def x10_monitor_cb(self, unit, order, args = None):
        """
        Callback for x10 monitoring
        @param unit : the unit of the element controled
        @param order : the order sent to the unit
        """
        self._log.debug("X10 Callback for %s" % unit)
        mess = XplMessage()
        mess.set_type("xpl-trig")
        mess.set_schema("x10.basic")
        mess.add_data({"device" :  unit})
        mess.add_data({"command" :  order})
        if args:
            mess.add_data({"level" : args})
        self._myxpl.send(mess)

if __name__ == "__main__":
    x = x10Main()
