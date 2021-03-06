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

API to use Domogik database.
Please don't forget to add unit test in 'database_test.py' if you add a new
method. Please always run 'python database_test.py' if you change something in
this file.

Implements
==========

- class DbHelperException(Exception) : exceptions linked to the DbHelper class
- class DbHelper : API to use Domogik database

@author: Maxence DUNNEWIND / Marc SCHNEIDER
@copyright: (C) 2007-2012 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

import datetime, hashlib, time

import json
import sqlalchemy
from sqlalchemy import Table, MetaData, and_
from sqlalchemy.sql.expression import func, extract
from sqlalchemy.orm import sessionmaker

from domogik.common.utils import ucode
from domogik.common import logger
from domogik.common.packagejson import PackageJson
from domogik.common.configloader import Loader
from domogik.common.sql_schema import (
        Device,
        DeviceUsage, DeviceStats,
        Plugin, PluginConfig, DeviceType, Person,
        UserAccount,
        Command, CommandParam,
        Sensor, SensorHistory,
        XplCommand, XplStat, XplStatParam, XplCommandParam
)


def _make_crypted_password(clear_text_password):
    """Make a crypted password (using sha256)

    @param clear_text_password : password in clear text
    @return crypted password

    """
    password = hashlib.sha256()
    password.update(clear_text_password)
    return password.hexdigest()

def _datetime_string_from_tstamp(ts):
    """Make a date from a timestamp"""
    return str(datetime.datetime.fromtimestamp(ts))

def _get_week_nb(dt):
    """Return the week number of a datetime expression"""
    #return (dt - datetime.datetime(dt.year, 1, 1)).days / 7
    return dt.isocalendar()[1]

class DbHelperException(Exception):
    """This class provides exceptions related to the DbHelper class

    """

    def __init__(self, value):
        """Class constructor

        @param value : value of the exception

        """
        Exception.__init__(self, value)
        self.value = value

    def __str__(self):
        """Return the object representation

        @return value of the exception

        """
        return repr(self.value)


class DbHelper():
    """This class provides methods to fetch and put informations on the Domogik database

    The user should only use methods from this class and don't access the database directly

    """
    __engine = None
    __session_object = None

    def __init__(self, echo_output=False, use_test_db=False, engine=None):
        """Class constructor

        @param echo_output : if True displays sqlAlchemy queries (optional, default False)
        @param use_test_db : if True use a test database (optional, default False)
        @param engine : an existing engine, if not provided, a new one will be created
        """
        # Here you have to specify twice the logger name as two instances of DbHelper are created
        self.log = logger.Logger('db_api').get_logger('db_api')
        
        cfg = Loader('database')
        config = cfg.load()
        self.__db_config = dict(config[1])
        
        if config[0]['log_level'] == 'debug':
            logger.Logger('sqlalchemy.engine', domogik_prefix=False, use_filename='sqlalchemy')
            logger.Logger('sqlalchemy.pool', domogik_prefix=False, use_filename='sqlalchemy')
            logger.Logger('sqlalchemy.orm', domogik_prefix=False, use_filename='sqlalchemy')

        url = self.get_url_connection_string()
        if use_test_db:
            url = '%s_test' % url
        # Connecting to the database
        if DbHelper.__engine == None:
            if engine != None:
                DbHelper.__engine = engine
            else:
                DbHelper.__engine = sqlalchemy.create_engine(url, echo = echo_output, encoding='utf8', 
                                                             pool_recycle=7200, pool_size=20, max_overflow=10)
        if DbHelper.__session_object == None:
            DbHelper.__session_object = sessionmaker(bind=DbHelper.__engine, autoflush=True)
        self.__session = DbHelper.__session_object()

    def get_engine(self):
        """Return the existing engine or None if not set
        @return self.__engine

        """
        return DbHelper.__engine

    def __del__(self):
        self.__session.close()

    def __rollback(self):
        """Issue a rollback to a SQL transaction (for dev purposes only)

        """
        self.__session.rollback()

    def get_url_connection_string(self):
        """Get url connection string to the database reading the configuration file"""
        url = "%s://" % self.__db_config['db_type']
        if self.__db_config['db_port'] != '':
            url = "%s%s:%s@%s:%s/%s" % (url, self.__db_config['db_user'], self.__db_config['db_password'],
                                        self.__db_config['db_host'], self.__db_config['db_port'], self.__db_config['db_name'])
        else:
            url = "%s%s:%s@%s/%s" % (url, self.__db_config['db_user'], self.__db_config['db_password'],
                                     self.__db_config['db_host'], self.__db_config['db_name'])
        return url
    
    def get_db_user(self):
        return self.__db_config['db_user']

    def get_db_password(self):
        return self.__db_config['db_password']
    
    def get_db_name(self):
        return self.__db_config['db_name']

    def is_db_type_mysql(self):
        return self.__db_config['db_type'].lower() == 'mysql'

    def get_db_type(self):
        """Return DB type which is currently used (mysql, postgresql)"""
        return self.__db_config['db_type'].lower()

####
# Device type
####
    def list_device_types(self, plugin=None):
        """Return a list of device types

        @return a list of DeviceType objects

        """
        if plugin is not None:
            return self.__session.query(DeviceType).filter_by(plugin_id=ucode(plugin)).all()
        else:
            return self.__session.query(DeviceType).all()

    def get_device_type_by_name(self, dty_name):
        """Return information about a device type

        @param dty_name : The device type name
        @return a DeviceType object

        """
        return self.__session.query(
                        DeviceType
                    ).filter(func.lower(DeviceType.name)==ucode(dty_name.lower())
                    ).first()
    
    def get_device_type_by_id(self, dty_id):
        """Return information about a device type

        @param dty_id : The device type id
        @return a DeviceType object

        """
        return self.__session.query(
                        DeviceType
                    ).filter(func.lower(DeviceType.id)==ucode(dty_id)
                    ).first()

    def add_device_type(self, dty_id, dty_name, dt_id, dty_description=None):
        """Add a device_type (Switch, Dimmer, WOL...)

        @param dty_id : device type id
        @param dty_name : device type name
        @param dt_id : plugin id (x10, plcbus,...)
        @param dty_description : device type description (optional)
        @return a DeviceType (the newly created one)

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        if not self.__session.query(Plugin).filter_by(id=dt_id).first():
            self.__raise_dbhelper_exception("Couldn't add device type with plugin id %s. It does not exist" % dt_id)
        dty = DeviceType(id=ucode(dty_id), name=ucode(dty_name), description=ucode(dty_description),
                         plugin_id=dt_id)
        self.__session.add(dty)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return dty

    def update_device_type(self, dty_id, dty_name=None, dt_id=None, dty_description=None):
        """Update a device type

        @param dty_id : device type id to be updated
        @param dty_name : device type name (optional)
        @param dt_id : id of the associated plugin (optional)
        @param dty_description : device type detailed description (optional)
        @return a DeviceType object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        device_type = self.__session.query(DeviceType).filter_by(id=dty_id).first()
        if device_type is None:
            self.__raise_dbhelper_exception("DeviceType with id %s couldn't be found" % dty_id)
        if dty_id is not None:
            device_type.id = ucode(dty_id)
        if dty_name is not None:
            device_type.name = ucode(dty_name)
        if dt_id is not None:
            if not self.__session.query(Plugin).filter_by(id=dt_id).first():
                self.__raise_dbhelper_exception("Couldn't find plugin id %s. It does not exist" % dt_id)
            device_type.plugin_id = dt_id
        self.__session.add(device_type)
        if dty_description is not None:
            if dty_description == '': dty_description = None
            device_type.description = ucode(dty_description)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception)
        return device_type

    def del_device_type(self, dty_id, cascade_delete=False):
        """Delete a device type

        @param dty_id : device type id
        @param cascade_delete : if set to True records of binded tables will be deleted (default is False)
        @return the deleted DeviceType object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        dty = self.__session.query(DeviceType).filter_by(id=ucode(dty_id)).first()
        if dty:
            if cascade_delete:
                for device in self.__session.query(Device).filter_by(device_type_id=ucode(dty.id)).all():
                    self.del_device(device.id)
            else:
                device_list = self.__session.query(Device).filter_by(device_type_id=ucode(dty.id)).all()
                if len(device_list) > 0:
                    self.__raise_dbhelper_exception("Couldn't delete device type %s : there are associated device(s)" % dty_id)
            self.__session.delete(dty)
            try:
                self.__session.commit()
            except Exception as sql_exception:
                self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
            return dty
        else:
            self.__raise_dbhelper_exception("Couldn't delete device type with id %s : it doesn't exist" % dty_id)

####
# Plugin
####
    def get_plugin(self, id=None):
        """Return a list of device technologies

        @return a list of DeviceTechnology objects

        """
        if id == None:
            return self.__session.query(Plugin).all()
        else:
            return self.__session.query(Plugin).filter_by(id=ucode(id)).first()

    def add_plugin(self, name, description=None, version=None):
        """Add a plugin

        @param name : plugin name
        @param description : extended description of the plugin
        @param version : version of the plugin

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        dt = Plugin(id=name, description=description, version=version)
        self.__session.add(dt)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return dt

    def update_plugin(self, id, description=None, version=None):
        """Update a plugin

        @param name : plugin name
        @param description : extended description of the plugin
        @param version : version of the plugin
        @return a plugin object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        plugin = self.__session.query(
                                Plugin
                            ).filter_by(id=ucode(id)
                            ).first()
        if plugin is None:
            self.__raise_dbhelper_exception("Plugin with id %s couldn't be found" % id)
        if description is not None:
            if description == '': description = None
            plugin.description = ucode(description)
        if version is not None:
            if version == '': version = None
            plugin.version = ucode(version)
        self.__session.add(plugin)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return plugin

    def del_plugin(self, pid, cascade_delete=False):
        """Delete a plugin

        @param id : id of the plugin to delete
        @param cascade_delete : True if related objects should be deleted, optional default set to False
        @return the deleted plugin  object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        dt = self.__session.query(Plugin).filter_by(id=ucode(pid)).first()
        if dt:
            if cascade_delete:
                for device_type in self.__session.query(DeviceType).filter_by(plugin_id=ucode(dt.id)).all():
                    self.del_device_type(device_type.id, cascade_delete=True)
                    self.__session.commit()
            else:
                device_type_list = self.__session.query(
                                            DeviceType
                                        ).filter_by(plugin_id=ucode(dt.id)
                                        ).all()
                if len(device_type_list) > 0:
                    self.__raise_dbhelper_exception("Couldn't delete plugin %s : there are associated device types"
                                               % dt_id)

            self.__session.delete(dt)
            try:
                self.__session.commit()
            except Exception as sql_exception:
                self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
            return dt
        else:
            self.__raise_dbhelper_exception("Couldn't delete plugin with id %s : it doesn't exist" % dt_id)

####
# Plugin config
####
    def list_all_plugin_config(self):
        """Return a list of all plugin config parameters

        @return a list of PluginConfig objects

        """
        return self.__session.query(PluginConfig).all()

    def list_plugin_config(self, pl_id, pl_hostname):
        """Return all parameters of a plugin

        @param pl_id : plugin id
        @param pl_hostname : hostname the plugin is installed on
        @return a list of PluginConfig objects

        """
        return self.__session.query(
                        PluginConfig
                    ).filter_by(id=ucode(pl_id)
                    ).filter_by(hostname=ucode(pl_hostname)
                    ).all()

    def get_plugin_config(self, pl_id, pl_hostname, pl_key):
        """Return information about a plugin parameter

        @param pl_id : plugin id
        @param pl_hostname : hostname the plugin is installed on
        @param pl_key : key we want the value from
        @return a PluginConfig object

        """
        self.log.debug("GPC %s, %s, %s" % (pl_id, pl_hostname, pl_key)) 
        try:
            ret = self.__session.query(
                        PluginConfig
                    ).filter_by(id=ucode(pl_id)
                    ).filter_by(hostname=ucode(pl_hostname)
                    ).filter_by(key=ucode(pl_key)
                    ).first()
            self.log.debug("GPC %s, %s, %s => %s=%s" % (pl_id, pl_hostname, pl_key, ret.key, ret.value)) 
        except:
            self.log.Debug("oups")
        return ret

    def set_plugin_config(self, pl_id, pl_hostname, pl_key, pl_value):
        """Add / update a plugin parameter

        @param pl_id : plugin id
        @param pl_hostname : hostname the plugin is installed on
        @param pl_key : key we want to add / update
        @param pl_value : key value we want to add / update
        @return : the added / updated PluginConfig item

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        plugin_config = self.__session.query(
                                PluginConfig
                            ).filter_by(id=ucode(pl_id)
                            ).filter_by(hostname=ucode(pl_hostname)
                            ).filter_by(key=ucode(pl_key)).first()
        if not plugin_config:
            plugin_config = PluginConfig(id=pl_id, hostname=pl_hostname, key=pl_key, value=pl_value)
        else:
            plugin_config.value = ucode(pl_value)
        self.__session.add(plugin_config)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : " % sql_exception, True)
        return plugin_config

    def del_plugin_config(self, pl_id, pl_hostname):
        """Delete all parameters of a plugin config

        @param pl_id : plugin id
        @param pl_hostname : hostname the plugin is installed on
        @return the deleted PluginConfig objects

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        plugin_config_list = self.__session.query(
                                    PluginConfig
                                ).filter_by(id=ucode(pl_id)
                                ).filter_by(hostname=ucode(pl_hostname)).all()
        for plc in plugin_config_list:
            self.__session.delete(plc)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : " % sql_exception, True)
        return plugin_config_list

    def del_plugin_config_key(self, pl_id, pl_hostname, pl_key):
        """Delete a key of a plugin config

        @param pl_id : plugin id
        @param pl_hostname : hostname the plugin is installed on
        @param pl_key : key of the plugin config
        @return the deleted PluginConfig object

        """        
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        plugin_config = self.__session.query(
                               PluginConfig
                           ).filter_by(id=ucode(pl_id)
                           ).filter_by(hostname=ucode(pl_hostname)
                           ).filter_by(key=ucode(pl_key)).first()
        if plugin_config is not None:
            self.__session.delete(plugin_config)
            try:
                self.__session.commit()
            except Exception as sql_exception:
                self.__raise_dbhelper_exception("SQL exception (commit) : " % sql_exception, True)
        return plugin_config
        
###
# Devices
###
    def list_devices(self):
        """Return a list of devices
        @return a list of Device objects (only the devices that are known by this realease)
        """
        return self.__session.query(Device).filter(Device.address==None).all()

    def list_old_devices(self):
        """Return a list of devices
        @return a list of Device objects (only the devices that are inot known by this realease)
        """
        return self.__session.query(Device).filter(Device.address!=None).all()

    def get_device(self, d_id):
        """Return a device by its id

        @param d_id : The device id
        @return a Device object

        """
        return self.__session.query(Device).filter_by(id=d_id).first()

    def add_device_and_commands(self, name, type_id, description, reference):
        # first add the device itself
        if not self.__session.query(DeviceType).filter_by(id=type_id).first():
            self.__raise_dbhelper_exception("Couldn't add device with device type id %s It does not exist" % type_id)
        dt = self.get_device_type_by_id(type_id)
        self.__session.expire_all()
        dev = Device(name=name, description=description, reference=reference, \
                        device_type_id=type_id)
        self.__session.add(dev)
        self.__session.flush()
        # hanle all the commands for this device_type
        pack = PackageJson(dt.plugin_id)
        pjson = pack.json
        if pjson['json_version'] < 2:
            self.__raise_dbhelper_exception("This plugin does not support this command, json_version should at least be 2", True)
            return None
        sensors = {}
        addedxplstats = {}
        tmp = pack.find_xplstats_for_device_type(dt.id)
        for sensor_id in tmp:
            sensor = pjson['sensors'][sensor_id]
            sen = Sensor(name=sensor['name'], \
                    device_id=dev.id, reference=sensor_id, \
                    data_type=sensor['data_type'], conversion=sensor['conversion'])
            self.__session.add(sen)
            self.__session.flush()
            sensors[sensor_id] = sen.id
            for stat in tmp[sensor_id]:
                xpl_stat_id = stat
                xpl_stat = pjson['xpl_stats'][xpl_stat_id]
                xplstat = XplStat(name=xpl_stat['name'], schema=xpl_stat['schema'], device_id=dev.id, json_id=xpl_stat_id)
                self.__session.add(xplstat)
                self.__session.flush()
                addedxplstats[xpl_stat_id] = xplstat.id
                # add static params
                for p in xpl_stat['parameters']['static']:
                    par = XplStatParam(xplstat_id=xplstat.id, sensor_id=None, \
                                   key=p['key'], value=p['value'], static=True, ignore_values=None)           
                    self.__session.add(par)
                # add dynamic params
                for p in xpl_stat['parameters']['dynamic']:
                    if 'ignore_values' not in p:
                        p['ignore_values'] = None
                    sensorid = None
                    if p['sensor'] is not None: 
                        if p['sensor'] in sensors:
                            sensorid = sensors[p['sensor']]
                        else:
                            self.__raise_dbhelper_exception("Can not find sensor %s" % (p['sensor']), True)
                            return None
                    par = XplStatParam(xplstat_id=xplstat.id, sensor_id=sensorid, \
                                    key=p['key'], value=None, static=False, ignore_values=p['ignore_values'])           
                    self.__session.add(par)
        for command_id in pjson['device_types'][dt.id]['commands']:
            # add the command
            command = pjson['commands'][command_id]
            cmd = Command(name=command['name'], \
                    device_id=dev.id, reference=command_id, return_confirmation=command['return_confirmation'])
            self.__session.add(cmd)
            self.__session.flush()
            # add the command params
            for p in pjson['commands'][command_id]['params']:
                pa = CommandParam(cmd.id, p['key'], p['data_type'], p['conversion'])
                self.__session.add(pa)
                self.__session.flush()
            # if needed add the xpl* stuff
            if 'xpl_command' in command:
                xpl_command_id = command['xpl_command']
                xpl_command = pjson['xpl_commands'][command['xpl_command']]
                # add the xpl_stat
                if 'xplstat_name' in xpl_command:
		    xpl_stat_id = xpl_command['xplstat_name']
                    if xpl_stat_id not in addedxplstats:
                        xpl_stat = pjson['xpl_stats'][xpl_stat_id]
                        xplstat = XplStat(name=xpl_stat['name'], schema=xpl_stat['schema'], device_id=dev.id, json_id=xpl_stat_id)
                        self.__session.add(xplstat)
                        self.__session.flush()
                        xplstatid = xplstat.id
                        # add static params
                        for p in xpl_stat['parameters']['static']:
                            par = XplStatParam(xplstat_id=xplstat.id, sensor_id=None, \
                                         key=p['key'], value=p['value'], static=True)           
                            self.__session.add(par)
                        # add dynamic params
                        for p in xpl_stat['parameters']['dynamic']:
                            if 'ignore_values' not in p:
                                p['ignore_values'] = None
                            sensorid = None
                            if p['sensor'] is not None: 
                                if p['sensor'] in sensors:
                                    sensorid = sensors[p['sensor']]
                                else:
                                    self.__raise_dbhelper_exception("Can not find sensor %s" % (p['sensor']), True)
                                    return None
                            par = XplStatParam(xplstat_id=xplstat.id, sensor_id=sensorid, \
                                         key=p['key'], value=None, static=False, ignore_values=p['ignore_values'])           
                            self.__session.add(par)
                    else:
                        xplstatid = addedxplstats[xpl_stat_id]
                else:
                    xplstatid = None
                # add the xpl command
                xplcommand = XplCommand(cmd_id=cmd.id, \
                                        name=xpl_command['name'], \
                                        schema=xpl_command['schema'], \
                                        device_id=dev.id, stat_id=xplstatid, \
                                        json_id=xpl_command_id) 
                self.__session.add(xplcommand)
                self.__session.flush()
                # add static params
                for p in xpl_command['parameters']['static']:
                    par = XplCommandParam(cmd_id=xplcommand.id, \
                                         key=p['key'], value=p['value'])           
                    self.__session.add(par)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, False)
        d = self.get_device(dev.id)
        return d

    def add_device(self, d_name, d_type_id, d_description=None, d_reference=None):
        """Add a device item

        @param d_name : name of the device
        @param d_type_id : device type id (x10.Switch, x10.Dimmer, Computer.WOL...)
        @param d_description : extended device description, optional
        @param d_reference : device reference (ex. AM12 for x10), optional
        @return the new Device object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        if not self.__session.query(DeviceType).filter_by(id=d_type_id).first():
            self.__raise_dbhelper_exception("Couldn't add device with device type id %s It does not exist" % d_type_id)
        device = Device(name=d_name, description=d_description, reference=d_reference, \
                        device_type_id=d_type_id)
        self.__session.add(device)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return device

    def update_device(self, d_id, d_name=None, d_description=None, d_reference=None, d_address=None):
        """Update a device item

        If a param is None, then the old value will be kept

        @param d_id : Device id
        @param d_name : device name (optional)
        @param d_description : Extended item description (optional)
        @return the updated Device object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        device = self.__session.query(Device).filter_by(id=d_id).first()
        if device is None:
            self.__raise_dbhelper_exception("Device with id %s couldn't be found" % d_id)
        if d_name is not None:
            device.name = ucode(d_name)
        if d_address is not None:
            device.address = ucode(d_address)
        if d_description is not None:
            if d_description == '': d_description = None
            device.description = ucode(d_description)
        if d_reference is not None:
            if d_reference == '': d_reference = None
            device.reference = ucode(d_reference)
        self.__session.add(device)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return device

    def del_device(self, d_id):
        """Delete a device

        @param d_id : device id
        @return the deleted device

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        device = self.__session.query(Device).filter_by(id=d_id).first()
        if device is None:
            self.__raise_dbhelper_exception("Device with id %s couldn't be found" % d_id)
        
        # Use this method rather than cascade deletion (much faster)
        meta = MetaData(bind=DbHelper.__engine)
        t_stats = Table(DeviceStats.__tablename__, meta, autoload=True)
        self.__session.execute(
            t_stats.delete().where(t_stats.c.device_id == d_id)
        )

        # delete sensor history data
        ssens = self.__session.query(Sensor).filter_by(device_id=d_id).all()
        meta = MetaData(bind=DbHelper.__engine)
        t_hist = Table(SensorHistory.__tablename__, meta, autoload=True)
        for sen in ssens:
            self.__session.execute(
                t_hist.delete().where(t_hist.c.sensor_id == sen.id)
            )
        
        self.__session.delete(device)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return device

####
# stats upgrade
####
    def upgrade_list_old(self):
        return self.__session.query(Device.id, Device.name, DeviceStats.skey).\
                    filter(Device.id==DeviceStats.device_id).\
                    filter(Device.address!=None).\
                    order_by(Device.id).\
                    distinct()

    def upgrade_list_new(self):
        return self.__session.query(Device.id, Device.name, Sensor.name, Sensor.id).\
                     filter(Device.id==Sensor.device_id).\
                     filter(Device.address==None).\
                     order_by(Device.id).\
                     distinct()

    def upgrade_do(self, oid, okey, nid, nsid):
        self.__session.expire_all()
        oldvals = self.__session.query(DeviceStats.id, DeviceStats.value, DeviceStats.timestamp).\
                     filter(DeviceStats.skey==okey).\
                     filter(DeviceStats.device_id ==oid)
        num = 0
        for val in oldvals:
            # add the value
            self.add_sensor_history(nsid, val[1], val[2])
  	    # increment num
            num += 1
        # delete the statas
        meta = MetaData(bind=DbHelper.__engine)
        t_stats = Table(DeviceStats.__tablename__, meta, autoload=True)
        self.__session.execute(
            t_stats.delete().where(and_(t_stats.c.device_id == oid, t_stats.c.skey == okey))
        )
        self.__session.commit()
        return num
            
####
# Sensor history
####
    def add_sensor_history(self, sid, value, date):
	self.__session.expire_all()
	sensor = self.__session.query(Sensor).filter_by(id=sid).first()
	if sensor is not None:
            # only store stats if the value is different
            if sensor.last_value is not str(value):
                # insert new recored in core_sensor_history
                h = SensorHistory(sensor.id, datetime.datetime.fromtimestamp(date), value)
                self.__session.add(h)
	        sensor.last_received = date
                sensor.last_value = str(value)
                self.__session.add(sensor)
                try:
                    self.__session.commit()
                except Exception as sql_exception:
                    self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        else:
            self.__raise_dbhelper_exception("Can not add history to not existing sensor: %s" % sid, True)             

    def list_sensor_history(self, sid, num=None):
        if num is None:
            return self.__session.query(SensorHistory).filter_by(sensor_id=sid).all()
        else:
            return self.__session.query(SensorHistory).filter_by(sensor_id=sid).limit(num)
            
    def list_sensor_history_between(self, sid, frm, to=None):
        if to:
            if to < frm:
                self.__raise_dbhelper_exception("'end_date' can't be prior to 'start_date'")
        else:
            to = int(time.time())
        return self.__session.query(SensorHistory
                  ).filter_by(sensor_id=sid
                  ).filter("date >= " + _datetime_string_from_tstamp(frm)
                  ).filter("date <= " + _datetime_string_from_tstamp(to)
                  ).order_by(sqlalchemy.asc(SensorHistory.date)
                  ).all()
       
    def list_sensor_history_filter(self, sid, frm, to, step_used, function_used):
        if not frm:
            self.__raise_dbhelper_exception("You have to provide a start date")
        if to:
            if to < frm:
                self.__raise_dbhelper_exception("'end_date' can't be prior to 'start_date'")
        else:
            to = int(time.time())
        if function_used is None or function_used.lower() not in ('min', 'max', 'avg'):
            self.__raise_dbhelper_exception("'function_used' parameter should be one of : min, max, avg")
        if step_used is None or step_used.lower() not in ('minute', 'hour', 'day', 'week', 'month', 'year'):
            self.__raise_dbhelper_exception("'period' parameter should be one of : minute, hour, day, week, month, year")
        function = {
            'min': func.min(SensorHistory.value_num),
            'max': func.max(SensorHistory.value_num),
            'avg': func.avg(SensorHistory.value_num),
        }
        sql_query = {
            'minute' : {
                # Query for mysql
                # func.week(SensorHistory.date, 3) is equivalent to python's isocalendar()[2] method
                'mysql': self.__session.query(
                            func.year(SensorHistory.date), func.month(SensorHistory.date),
                            func.week(SensorHistory.date, 3), func.day(SensorHistory.date),
                            func.hour(SensorHistory.date), func.minute(SensorHistory.date),
                            function[function_used]
                        ).group_by(
                            func.year(SensorHistory.date), func.month(SensorHistory.date),
                            func.day(SensorHistory.date), func.hour(SensorHistory.date),
                            func.minute(SensorHistory.date)
                        ),
                 'postgresql': self.__session.query(
                            extract('year', SensorHistory.date).label('year_c'), extract('month', SensorHistory.date),
                            extract('week', SensorHistory.date), extract('day', SensorHistory.date),
                            extract('hour', SensorHistory.date), extract('minute', SensorHistory.date),
                            function[function_used]
                        ).group_by(
                            extract('year', SensorHistory.date), extract('month', SensorHistory.date),
                            extract('week', SensorHistory.date), extract('day', SensorHistory.date),
                            extract('hour', SensorHistory.date), extract('minute', SensorHistory.date)
                        ).order_by(
                            sqlalchemy.asc('year_c')
                        )
            },
            'hour' : {
                'mysql': self.__session.query(
                            func.year(SensorHistory.date), func.month(SensorHistory.date),
                            func.week(SensorHistory.date, 3), func.day(SensorHistory.date),
                            func.hour(SensorHistory.date), function[function_used]
                        ).group_by(
                            func.year(SensorHistory.date), func.month(SensorHistory.date),
                            func.day(SensorHistory.date), func.hour(SensorHistory.date)
                        ),
                'postgresql': self.__session.query(
                            extract('year', SensorHistory.date).label('year_c'), extract('month', SensorHistory.date),
                            extract('week', SensorHistory.date), extract('day', SensorHistory.date),
                            extract('hour', SensorHistory.date),
                            function[function_used]
                        ).group_by(
                            extract('year', SensorHistory.date), extract('month', SensorHistory.date),
                            extract('week', SensorHistory.date), extract('day', SensorHistory.date),
                            extract('hour', SensorHistory.date)
                        ).order_by(
                            sqlalchemy.asc('year_c')
                        )
            },
            'day' : {
                'mysql': self.__session.query(
                            func.year(SensorHistory.date), func.month(SensorHistory.date),
                            func.week(SensorHistory.date, 3), func.day(SensorHistory.date),
                                      function[function_used]
                        ).group_by(
                            func.year(SensorHistory.date), func.month(SensorHistory.date),
                            func.day(SensorHistory.date)
                        ),
                'postgresql': self.__session.query(
                            extract('year', SensorHistory.date).label('year_c'), extract('month', SensorHistory.date),
                            extract('week', SensorHistory.date), extract('day', SensorHistory.date),
                            function[function_used]
                        ).group_by(
                            extract('year', SensorHistory.date), extract('month', SensorHistory.date),
                            extract('week', SensorHistory.date), extract('day', SensorHistory.date)
                        ).order_by(
                            sqlalchemy.asc('year_c')
                        )
            },
            'week' : {
                'mysql': self.__session.query(
                            func.year(SensorHistory.date), func.week(SensorHistory.date, 1), function[function_used]
                        ).group_by(
                            func.year(SensorHistory.date), func.week(SensorHistory.date, 1)
                        ),
                'postgresql': self.__session.query(
                            extract('year', SensorHistory.date).label('year_c'), extract('week', SensorHistory.date),
                            function[function_used]
                        ).group_by(
                            extract('year', SensorHistory.date).label('year_c'), extract('week', SensorHistory.date)
                        ).order_by(
                            sqlalchemy.asc('year_c')
                        )
            },
            'year' : {
                'mysql': self.__session.query(
                            func.year(SensorHistory.date), function[function_used]
                        ).group_by(
                            func.year(SensorHistory.date)
                        ),
                'postgresql': self.__session.query(
                            extract('year', SensorHistory.date).label('year_c'), function[function_used]
                        ).group_by(
                            extract('year', SensorHistory.date)
                        ).order_by(
                            sqlalchemy.asc('year_c')
                        )
            },
            'global' : self.__session.query(
                            function['min'], function['max'], function['avg']
                        )
        }
        if self.get_db_type() in ('mysql', 'postgresql'):
            cond_min = "date >= '" + _datetime_string_from_tstamp(frm) + "'"
            cond_max = "date < '" + _datetime_string_from_tstamp(to) + "'"
            query = sql_query[step_used][self.get_db_type()]
            query = query.filter_by(sensor_id=sid
                        ).filter(cond_min
                        ).filter(cond_max)
            results_global = sql_query['global'].filter_by(sensor_id=sid
                                               ).filter(cond_min
                                               ).filter(cond_max
                                               ).first()
            return {
                'values': query.all(),
                'global_values': {
                    'min': results_global[0],
                    'max': results_global[1],
                    'avg': results_global[2]
                }
            }


####
# User accounts
####
    def list_user_accounts(self):
        """Return a list of all accounts

        @return a list of UserAccount objects

        """
        list_sa = self.__session.query(UserAccount).all()
        return list_sa

    def get_user_account(self, a_id):
        """Return user account information from id

        @param a_id : account id
        @return a UserAccount object

        """
        user_acc = self.__session.query(UserAccount).filter_by(id=a_id).first()
        return user_acc

    def get_user_account_by_login(self, a_login):
        """Return user account information from login

        @param a_login : login
        @return a UserAccount object

        """
        return self.__session.query(
                            UserAccount
                        ).filter_by(login=ucode(a_login)
                        ).first()

    def get_user_account_by_person(self, p_id):
        """Return a user account associated to a person, if existing

        @param p_id : The person id
        @return a UserAccount object

        """
        return self.__session.query(
                        UserAccount
                    ).filter_by(person_id=p_id
                    ).first()

    def authenticate(self, a_login, a_password):
        """Check if a user account with a_login, a_password exists

        @param a_login : Account login
        @param a_password : Account password (clear)
        @return True or False

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        user_acc = self.__session.query(
                            UserAccount
                        ).filter_by(login=ucode(a_login)
                        ).first()
        return user_acc is not None and user_acc._UserAccount__password == _make_crypted_password(a_password)

    def add_user_account(self, a_login, a_password, a_person_id, a_is_admin=False, a_skin_used=''):
        """Add a user account

        @param a_login : Account login
        @param a_password : Account clear text password (will be hashed in sha256)
        @param a_person_id : id of the person associated to the account
        @param a_is_admin : True if it is an admin account, False otherwise (optional, default=False)
        @return the new UserAccount object or raise a DbHelperException if it already exists

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        user_account = self.__session.query(
                                UserAccount
                            ).filter_by(login=ucode(a_login)
                            ).first()
        if user_account is not None:
            self.__raise_dbhelper_exception("Error %s login already exists" % a_login)
        person = self.__session.query(Person).filter_by(id=a_person_id).first()
        if person is None:
            self.__raise_dbhelper_exception("Person id '%s' does not exist" % a_person_id)
        user_account = UserAccount(login=a_login, password=_make_crypted_password(a_password),
                                   person_id=a_person_id, is_admin=a_is_admin, skin_used=a_skin_used)
        self.__session.add(user_account)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return user_account

    def add_user_account_with_person(self, a_login, a_password, a_person_first_name, a_person_last_name,
                                     a_person_birthdate=None, a_is_admin=False, a_skin_used=''):
        """Add a user account and a person

        @param a_login : Account login
        @param a_password : Account clear text password (will be hashed in sha256)
        @param a_person_first_name : first name of the person associated to the account
        @param a_person_last_name : last name of the person associated to the account
        @param a_person_birthdate : birthdate of the person associated to the account, optional
        @param a_is_admin : True if it is an admin account, False otherwise (optional, default=False)
        @param a_skin_used : name of the skin choosen by the user (optional, default='skins/default')
        @return the new UserAccount object or raise a DbHelperException if it already exists

        """
        person = self.add_person(a_person_first_name, a_person_last_name, a_person_birthdate)
        return self.add_user_account(a_login, a_password, person.id, a_is_admin, a_skin_used)

    def update_user_account(self, a_id, a_new_login=None, a_person_id=None, a_is_admin=None, a_skin_used=None):
        """Update a user account

        @param a_id : Account id to be updated
        @param a_new_login : The new login (optional)
        @param a_person_id : id of the person associated to the account
        @param a_is_admin : True if it is an admin account, False otherwise (optional)
        @param a_skin_used : name of the skin choosen by the user (optional, default='skins/default')
        @return a UserAccount object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        user_acc = self.__session.query(UserAccount).filter_by(id=a_id).first()
        if user_acc is None:
            self.__raise_dbhelper_exception("UserAccount with id %s couldn't be found" % a_id)
        if a_new_login is not None:
            user_acc.login = ucode(a_new_login)
        if a_person_id is not None:
            person = self.__session.query(Person).filter_by(id=a_person_id).first()
            if person is None:
                self.__raise_dbhelper_exception("Person id '%s' does not exist" % a_person_id)
            user_acc.person_id = a_person_id
        if a_is_admin is not None:
            user_acc.is_admin = a_is_admin
        if a_skin_used is not None:
            user_acc.skin_used = ucode(a_skin_used)
        self.__session.add(user_acc)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return user_acc

    def update_user_account_with_person(self, a_id, a_login=None, p_first_name=None, p_last_name=None, p_birthdate=None,
                                        a_is_admin=None, a_skin_used=None):
        """Update a user account a person information

        @param a_id : Account id to be updated
        @param a_login : The new login (optional)
        @param p_first_name : first name of the person associated to the account, optional
        @param p_last_name : last name of the person associated to the account, optional
        @param p_birthdate : birthdate of the person associated to the account, optional
        @param a_is_admin : True if it is an admin account, False otherwise, optional
        @param a_skin_used : name of the skin choosen by the user (optional, default='skins/default')
        @return a UserAccount object

        """
        user_acc = self.update_user_account(a_id, a_login, None, a_is_admin, a_skin_used)
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        person = user_acc.person
        if p_first_name is not None:
            person.first_name = ucode(p_first_name)
        if p_last_name is not None:
            person.last_name = ucode(p_last_name)
        if p_birthdate is not None:
            person.birthdate = p_birthdate
        self.__session.add(person)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return user_acc

    def change_password(self, a_id, a_old_password, a_new_password):
        """Change the password

        @param a_id : account id
        @param a_old_password : the password to change (the old one, in clear text)
        @param a_new_password : the new password, in clear text (will be hashed in sha256)
        @return True if the password could be changed, False otherwise (login or old_password is wrong)

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        user_acc = self.__session.query(UserAccount).filter_by(id=a_id).first()
        if user_acc is not None:
            old_pass = ucode(_make_crypted_password(a_old_password))
            if user_acc._UserAccount__password != old_pass:
                return False
        else:
            return False
        user_acc.set_password(ucode(_make_crypted_password(a_new_password)))
        self.__session.add(user_acc)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return True

    def add_default_user_account(self):
        """Add a default user account (login = admin, password = domogik, is_admin = True)
        if there isn't already one

        @return a UserAccount object

        """
        default_person_fname = "Admin"
        default_person_lname = "Admin"
        default_user_account_login = "admin"
        if self.__session.query(UserAccount).count() > 0:
            return None
        person = self.add_person(p_first_name=default_person_fname, p_last_name=default_person_lname, 
                                 p_birthdate=datetime.date(1900, 01, 01))
        return self.add_user_account(a_login=default_user_account_login, a_password='123', a_person_id=person.id, 
                                     a_is_admin=True)

    def del_user_account(self, a_id):
        """Delete a user account

        @param a_id : account id
        @return the deleted UserAccount object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        user_account = self.__session.query(UserAccount).filter_by(id=a_id).first()
        if user_account:
            self.__session.delete(user_account)
            try:
                self.__session.commit()
            except Exception as sql_exception:
                self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
            return user_account
        else:
            self.__raise_dbhelper_exception("Couldn't delete user account with id %s : it doesn't exist" % a_id)

####
# Persons
####
    def list_persons(self):
        """Return the list of all persons

        @return a list of Person objects

        """
        return self.__session.query(Person).all()

    def get_person(self, p_id):
        """Return person information

        @param p_id : person id
        @return a Person object

        """
        return self.__session.query(Person).filter_by(id=p_id).first()

    def add_person(self, p_first_name, p_last_name, p_birthdate=None):
        """Add a person

        @param p_first_name     : first name
        @param p_last_name      : last name
        @param p_birthdate      : birthdate, optional
        @param p_user_account   : Person account on the user (optional)
        @return the new Person object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        person = Person(first_name=p_first_name, last_name=p_last_name, birthdate=p_birthdate)
        self.__session.add(person)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return person

    def update_person(self, p_id, p_first_name=None, p_last_name=None, p_birthdate=None):
        """Update a person

        @param p_id             : person id to be updated
        @param p_first_name     : first name (optional)
        @param p_last_name      : last name (optional)
        @param p_birthdate      : birthdate (optional)
        @return a Person object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        person = self.__session.query(Person).filter_by(id=p_id).first()
        if person is None:
            self.__raise_dbhelper_exception("Person with id %s couldn't be found" % p_id)
        if p_first_name is not None:
            person.first_name = ucode(p_first_name)
        if p_last_name is not None:
            person.last_name = ucode(p_last_name)
        if p_birthdate is not None:
            if p_birthdate == '':
                p_birthdate = None
            person.birthdate = p_birthdate
        self.__session.add(person)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return person

    def del_person(self, p_id):
        """Delete a person and the associated user account if it exists

        @param p_id : person account id
        @return the deleted Person object

        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        person = self.__session.query(Person).filter_by(id=p_id).first()
        if person is not None:
            self.__session.delete(person)
            try:
                self.__session.commit()
            except Exception as sql_exception:
                self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
            return person
        else:
            self.__raise_dbhelper_exception("Couldn't delete person with id %s : it doesn't exist" % p_id)

###################
# sensor
###################
    def get_all_sensor(self):
        self.__session.expire_all()
        return self.__session.query(Sensor).all()

    def get_sensor_by_device_id(self, did):
        self.__session.expire_all()
        return self.__session.query(Sensor).filter_by(device_id=did).all()

###################
# command
###################
    def get_all_command(self):
        self.__session.expire_all()
        return self.__session.query(Command).all()
    
    def get_command(self, id):
        self.__session.expire_all()
        return self.__session.query(Command).filter_by(id=id).first()
    
    def add_command(self, device_id, name, reference, return_confirmation):
        self.__session.expire_all()
        cmd = Command(name=name, device_id=device_id, reference=reference, return_confirmation=return_confirmation)
        self.__session.add(cmd)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return cmd

###################
# commandParam
###################
    def add_commandparam(self, cmd_id, key, dtype, conversion): 
        self.__session.expire_all()
        p = CommandParam(cmd_id=cmd_id, key=key, data_type=dtype, conversion=conversion)
        self.__session.add(p)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return p

###################
# xplcommand
###################
    def get_all_xpl_command(self):
        self.__session.expire_all()
        return self.__session.query(XplCommand).all()
    
    def get_xpl_command(self, p_id):
        self.__session.expire_all()
        return self.__session.query(XplCommand).filter_by(id=p_id).first()

    def get_xpl_command_by_device_id(self, d_id):
        self.__session.expire_all()
        return self.__session.query(XplCommand).filter_by(device_id=d_id).all()

    def add_xpl_command(self, cmd_id, name, schema, device_id, stat_id, json_id):
        self.__session.expire_all()
        cmd = XplCommand(cmd_id=cmd_id, name=name, schema=schema, device_id=device_id, stat_id=stat_id, json_id=json_id)
        self.__session.add(cmd)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return cmd

    def del_xpl_command(self, id):
        self.__session.expire_all()
        cmd = self.__session.query(XplCommand).filter_by(id=id).first()
        if cmd is not None:
            self.__session.delete(cmd)
            try:
                self.__session.commit()
            except Exception as sql_exception:
                self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
            return cmd
        else:
            self.__raise_dbhelper_exception("Couldn't delete xpl-command with id %s : it doesn't exist" % id)

    def update_xpl_command(self, id, cmd_id=None, name=None, schema=None, device_id=None, stat_id=None):
        """Update a xpl_stat
        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        cmd = self.__session.query(XplCommand).filter_by(id=id).first()
        if cmd is None:
            self.__raise_dbhelper_exception("XplCommand with id %s couldn't be found" % id)
        if cmd_id is not None:
            cmd.cmd_id = cmd_id
        if schema is not None:
            cmd.schema = ucode(schema)
        if device_id is not None:
            cmd.device_id = device_id
        if stat_id is not None:
            cmd.stat_id = stat_id
        if name is not None:
            cmd.name = name
        self.__session.add(cmd)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return cmd


###################
# xplstat
###################
    def get_all_xpl_stat(self):
        self.__session.expire_all()
        return self.__session.query(XplStat).all()

    def get_xpl_stat(self, p_id):
        self.__session.expire_all()
        return self.__session.query(XplStat).filter_by(id=p_id).first()
    
    def get_xpl_stat_by_device_id(self, d_id):
        self.__session.expire_all()
        return self.__session.query(XplStat).filter_by(device_id=d_id).all()

    def add_xpl_stat(self, name, schema, device_id, json_id):
        self.__session.expire_all()
        stat = XplStat(name=name, schema=schema, device_id=device_id, json_id=json_id)
        self.__session.add(stat)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return stat

    def del_xpl_stat(self, id):
        self.__session.expire_all()
        stat = self.__session.query(XplStat).filter_by(id=id).first()
        if stat is not None:
            self.__session.delete(stat)
            try:
                self.__session.commit()
            except Exception as sql_exception:
                self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
            return stat
        else:
            self.__raise_dbhelper_exception("Couldn't delete xpl-stat with id %s : it doesn't exist" % id)
    
    def update_xpl_stat(self, id, name=None, schema=None, device_id=None):
        """Update a xpl_stat
        """
        # Make sure previously modified objects outer of this method won't be commited
        self.__session.expire_all()
        stat = self.__session.query(XplStat).filter_by(id=id).first()
        if stat is None:
            self.__raise_dbhelper_exception("XplStat with id %s couldn't be found" % id)
        if schema is not None:
            stat.schema = ucode(schema)
        if device_id is not None:
            stat.device_id = device_id
        if name is not None:
            stat.name = name
        self.__session.add(stat)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return stat

###################
# XplCommandParam
###################
    def add_xpl_command_param(self, cmd_id, key, value):
        self.__session.expire_all()
        param = XplCommandParam(cmd_id=cmd_id, key=key, value=value)
        self.__session.add(param)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return param

    def update_xpl_command_param(self, cmd_id, key, value=None):
        self.__session.expire_all()
        param = self.__session.query(XplCommandParam).filter_by(xplcmd_id=cmd_id).filter_by(key=key).first()
        if param is None:
            self.__raise_dbhelper_exception("XplCommandParam with id %s and key %s couldn't be found" % (cmd_id, key))
        if value is not None:
            param.value = ucode(value)
        self.__session.add(param)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return param

    def del_xpl_command_param(self, id, key):
        self.__session.expire_all()
        param = self.__session.query(XplCommandParam).filter_by(xplcmd_id=id).filter_by(key=key).first()
        if param is not None:
            self.__session.delete(param)
            try:
                self.__session.commit()
            except Exception as sql_exception:
                self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
            return param
        else:
            self.__raise_dbhelper_exception("Couldn't delete xpl-command-param with id %s : it doesn't exist" % id)

###################
# XplStatParam
###################
    def get_xpl_stat_param_by_sensor(self, sensor_id):
        return self.__session.query(XplStatParam).filter_by(sensor_id=sensor_id).first()

    def add_xpl_stat_param(self, statid, key, value, static, ignore_values=None):
        self.__session.expire_all()
        param = XplStatParam(xplstat_id=statid, key=key, value=value, static=static, sensor_id=None, ignore_values=ignore_values)
        self.__session.add(param)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return param

    def update_xpl_stat_param(self, stat_id, key, value=None, static=None, ignore_values=None):
        self.__session.expire_all()
        param = self.__session.query(XplStatParam).filter_by(xplstat_id=stat_id).filter_by(key=key).first()
        if param is None:
            self.__raise_dbhelper_exception("XplStatParam with id %s couldn't be found" % id)
        if value is not None:
            param.value = ucode(value)
        if static is not None:
            param.static = static
        if ignore_values is not None:
            param.ignore_values = ignore_values
        self.__session.add(param)
        try:
            self.__session.commit()
        except Exception as sql_exception:
            self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
        return param

    def del_xpl_stat_param(self, stat_id, key):
        self.__session.expire_all()
        param = self.__session.query(XplStatParam).filter_by(xplstat_id=stat_id).filter_by(key=key).first()
        if param is not None:
            self.__session.delete(param)
            try:
                self.__session.commit()
            except Exception as sql_exception:
                self.__raise_dbhelper_exception("SQL exception (commit) : %s" % sql_exception, True)
            return param
        else:
            self.__raise_dbhelper_exception("Couldn't delete xpl-stat-param with id %s : it doesn't exist" % id)
         
###################
# helper functions
###################
    def __raise_dbhelper_exception(self, error_msg, with_rollback=False):
        """Raise a DbHelperException and log it

        @param error_msg : error message
        @param with_rollback : True if a rollback should be done (default is set to False)

        """
        self.log.error(error_msg)
        if with_rollback:
            self.__session.rollback()
        raise DbHelperException(error_msg)

