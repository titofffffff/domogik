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

Plugin purpose
==============

Send time informations on the xPL network

Implements
==========

- xPLDateTime.__init__(self)
- xPLDateTime._format(self, nb)
- xPLDateTime._send_datetime(self)

@author: Maxence Dunnewind <maxence@dunnewind.net>
@copyright: (C) 2007-2012 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

from time import localtime
from domogik.xpl.common.xplconnector import XplTimer
from domogik.xpl.common.plugin import XplPlugin
from domogik.xpl.common.xplmessage import XplMessage

TIME_BETWEEN_EACH_MESSAGE = 60


class XPLDateTime(XplPlugin):
    '''
    Send date and time on the xPL network every minute
    '''

    def __init__(self):
        XplPlugin.__init__(self, name = 'xpl_time')
        
        self._listen_thr = XplTimer(TIME_BETWEEN_EACH_MESSAGE, \
                                    self._send_datetime,
                                    self.myxpl)
        self._listen_thr.start()
        self.enable_hbeat()

    def _format(self, number):
        '''
        Format the number
        '''
        if int(number) < 10:
            return "0%s" % number
        else:
            return number

    def _send_datetime(self):
        '''
        Send date and time on xPL network
        '''
        ldt = localtime()
        date = "%s%s%s" % (ldt[0], self._format(ldt[1]), self._format(ldt[2]))
        time = "%s%s%s" % (self._format(ldt[3]), self._format(ldt[4]), self._format(ldt[5]))
        datetime = "%s%s" % (date, time)
        mess = XplMessage()
        mess.set_type("xpl-trig")
        mess.set_schema("datetime.basic")
        mess.add_data({"datetime" :  datetime})
        mess.add_data({"date" :  date})
        mess.add_data({"time" :  time})
        # datetime + weekday
        mess.add_data({"format1" :  "%s%s" % (datetime, ldt[6])}) 
        print(mess)
        self.myxpl.send(mess)

if __name__ == "__main__":
    XPLDateTime()
