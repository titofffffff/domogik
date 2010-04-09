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

API to use Domogik database.
Please don't forget to add unit test in 'database_test.py' if you add a new
method. Please always run 'python database_test.py' if you change something in
this file.

Implements
==========

- class DbHelperException(Exception) : exceptions linked to the DbHelper class
- class DbHelper : API to use Domogik database

@author: Maxence DUNNEWIND / Marc SCHNEIDER
@copyright: (C) 2007-2009 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

import copy, datetime, hashlib
from types import DictType, ListType, NoneType

import sqlalchemy
from sqlalchemy.sql.expression import func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound


from domogik.common.configloader import Loader
from domogik.common.sql_schema import ACTUATOR_VALUE_TYPE_LIST, Area, Device, DeviceTypeFeature, \
                                      ActuatorFeature, SensorFeature, DeviceUsage, DeviceFeatureAssociation, \
                                      DEVICE_FEATURE_ASSOCIATION_LIST, \
                                      DeviceConfig, DeviceStats, DeviceStatsValue, DeviceTechnology, PluginConfig, \
                                      DeviceType, UIItemConfig, Room, Person, UserAccount, SENSOR_VALUE_TYPE_LIST, \
                                      SystemConfig, SystemStats, SystemStatsValue, Trigger


class DbHelperException(Exception):
    """
    This class provides exceptions related to the DbHelper class
    """

    def __init__(self, value):
        """
        Class constructor
        @param value : value of the exception
        """
        self.value = value

    def __str__(self):
        """
        Return the object representation
        @return value of the exception
        """
        return repr(self.value)


class DbHelper():
    """
    This class provides methods to fetch and put informations on the Domogik database
    The user should only use methods from this class and don't access the database directly
    """
    __dbprefix = None
    __engine = None
    __session = None

    def __init__(self, echo_output=False, use_test_db=False):
        """
        Class constructor
        @param echo_output : if True displays sqlAlchemy queries (optional, default False)
        @param use_test_db : if True use a test database (optional, default False)
        """
        cfg = Loader('database')
        config = cfg.load()
        db = dict(config[1])
        url = "%s://" % db['db_type']
        if db['db_type'] == 'sqlite':
            url = "%s/%s" % (url, db['db_path'])
        else:
            if db['db_port'] != '':
                url = "%s%s:%s@%s:%s/%s" % (url, db['db_user'], \
                                            db['db_password'],
                                            db['db_host'], db['db_port'], \
                                            db['db_name'])
            else:
                url = "%s%s:%s@%s/%s" % (url, db['db_user'], db['db_password'],
                                         db['db_host'], db['db_name'])

        if use_test_db:
            url = '%s_test' % url
        # Connecting to the database
        self.__dbprefix = db['db_prefix']
        self.__engine = sqlalchemy.create_engine(url, echo=echo_output)
        Session = sessionmaker(bind=self.__engine, autoflush=False)
        self.__session = Session()

    def __rollback(self):
        """
        Issue a rollback to a SQL transaction (for dev purposes only)
        """
        self.__session.rollback()

    def __to_unicode(self, my_string):
        """
        Convert a string into unicode or return None if None value is passed
        @param my_string : string value to convert
        @return a unicode string
        """
        if my_string is not None:
            return unicode(my_string)
        else:
            return None

####
# Areas
####
    def list_areas(self):
        """
        Return all areas
        @return list of Area objects
        """
        return self.__session.query(Area).all()

    def list_areas_with_rooms(self):
        """
        Return all areas with associated rooms
        @return a list of Area objects containing the associated room list
        """
        area_list = self.__session.query(Area).all()
        area_rooms_list = []
        for area in area_list:
            # to avoid creating a join with following request
            room_list = self.__session.query(Room)\
                            .filter_by(area_id=area.id).all()
            # set Room in area object
            area.Room = room_list
            area_rooms_list.append(area)
        return area_rooms_list

    def search_areas(self, filters):
        """
        Look for area(s) with filter on their attributes
        @param filters :  filter fields can be one of
        @return a list of Area objects
        """
        if type(filters) is not DictType:
            raise DbHelperException("Wrong type of 'filters', Should be a dictionnary")
        area_list = self.__session.query(Area)
        for filter in filters:
            filter_arg = "%s = '%s'" % (filter, self.__to_unicode(filters[filter]))
            area_list = area_list.filter(filter_arg)
        return area_list.all()

    def get_area_by_id(self, area_id):
        """
        Fetch area information
        @param area_id : The area id
        @return an area object
        """
        return self.__session.query(Area).filter_by(id=area_id).first()


    def get_area_by_name(self, area_name):
        """
        Fetch area information
        @param area_name : The area name
        @return an area object
        """
        return self.__session.query(Area)\
                             .filter(func.lower(Area.name)==self.__to_unicode(area_name.lower()))\
                             .first()

    def add_area(self, a_name, a_description=None):
        """
        Add an area
        @param a_name : area name
        @param a_description : area detailed description (optional)
        @return an Area object
        """
        self.__session.expire_all()
        area = Area(name=self.__to_unicode(a_name), description=self.__to_unicode(a_description))
        self.__session.add(area)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return area

    def update_area(self, a_id, a_name=None, a_description=None):
        """
        Update an area
        @param a_id : area id to be updated
        @param a_name : area name (optional)
        @param a_description : area detailed description (optional)
        @return an Area object
        """
        self.__session.expire_all()
        area = self.__session.query(Area).filter_by(id=a_id).first()
        if area is None:
            raise DbHelperException("Area with id %s couldn't be found" % a_id)
        if a_name is not None:
            area.name = self.__to_unicode(a_name)
        if a_description is not None:
            if a_description == '': a_description = None
            area.description = self.__to_unicode(a_description)
        self.__session.add(area)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return area

    def del_area(self, area_del_id, cascade_delete=False):
        """
        Delete an area record
        @param area_id : id of the area to delete
        @param cascade_delete : True if we wish to delete associated items
        @return the deleted Area object
        """
        self.__session.expire_all()
        area = self.__session.query(Area).filter_by(id=area_del_id).first()
        if area:
            area_d = area
            if cascade_delete:
                for room in self.__session.query(Room).filter_by(area_id=area_del_id).all():
                    self.del_room(room.id, True)
            dfa_list = self.__session.query(DeviceFeatureAssociation)\
                                     .filter_by(place_id=area.id, place_type=u'area').all()
            for dfa in dfa_list:
                self.__session.delete(dfa)
            self.__session.delete(area)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return area_d
        else:
            raise DbHelperException("Couldn't delete area with id %s : it doesn't exist" % area_del_id)

####
# Rooms
####
    def list_rooms(self):
        """
        Return a list of rooms
        @return list of Room objects
        """
        return self.__session.query(Room).all()

    def list_rooms_with_devices(self):
        """
        Return all rooms with associated devices
        @return a list of Room objects containing the associated device list
        """
        room_list = self.__session.query(Room).all()
        room_devices_list = []
        for room in room_list:
            device_list = self.__session.query(Device)\
                              .filter_by(room_id=room.id).all()
            # set Room in area object
            room.Device = device_list
            room_devices_list.append(room)
        return room_devices_list

    def search_rooms(self, filters):
        """
        Look for room(s) with filter on their attributes
        @param filters :  filter fields (dictionnary)
        @return a list of Room objects
        """
        if type(filters) is not DictType:
            raise DbHelperException("Wrong type of 'filters', Should be a dictionnary")
        room_list = self.__session.query(Room)
        for filter in filters:
            filter_arg = "%s = '%s'" % (filter, self.__to_unicode(filters[filter]))
            room_list = room_list.filter(filter_arg)
        return room_list.all()

    def get_room_by_name(self, r_name):
        """
        Return information about a room
        @param r_name : The room name
        @return a room object
        """
        return self.__session.query(Room)\
                             .filter(func.lower(Room.name)==self.__to_unicode(r_name.lower()))\
                             .first()

    def get_room_by_id(self, r_id):
        """
        Return information about a room
        @param r_id : The room id
        @return a room object
        """
        return self.__session.query(Room).filter_by(id=r_id).first()

    def add_room(self, r_name, r_area_id=None, r_description=None):
        """
        Add a room
        @param r_name : room name
        @param area_id : id of the area where the room is, optional
        @param r_description : room detailed description, optional
        @return : a room object
        """
        self.__session.expire_all()
        if r_area_id != None:
            try:
                self.__session.query(Area).filter_by(id=r_area_id).one()
            except NoResultFound:
                raise DbHelperException("Couldn't add room with area id %s. It does not exist" % r_area_id)
        room = Room(name=self.__to_unicode(r_name), description=self.__to_unicode(r_description), area_id=r_area_id)
        self.__session.add(room)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return room

    def update_room(self, r_id, r_name=None, r_area_id=None, r_description=None):
        """
        Update a room
        @param r_id : room id to be updated
        @param r_name : room name (optional)
        @param r_description : room detailed description (optional)
        @param r_area_id : id of the area the room belongs to (optional)
        @return a Room object
        """
        self.__session.expire_all()
        room = self.__session.query(Room).filter_by(id=r_id).first()
        if room is None:
            raise DbHelperException("Room with id %s couldn't be found" % r_id)
        if r_name is not None:
            room.name = self.__to_unicode(r_name)
        if r_description is not None:
            if r_description == '': r_description = None
            room.description = self.__to_unicode(r_description)
        if r_area_id is not None:
            if r_area_id != '':
                try:
                    self.__session.query(Area).filter_by(id=r_area_id).one()
                except NoResultFound:
                    raise DbHelperException("Couldn't find area id %s. It does not exist" % r_area_id)
            else:
                r_area_id = None
            room.area_id = r_area_id
        self.__session.add(room)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return room

    def del_room(self, r_id, cascade_delete=False):
        """
        Delete a room record
        @param r_id : id of the room to delete
        @param cascade_delete : True if we wish to delete associated items
        @return the deleted Room object
        """
        self.__session.expire_all()
        room = self.__session.query(Room).filter_by(id=r_id).first()
        if room:
            room_d = room
            if cascade_delete:
                for device in self.__session.query(Device).filter_by(room_id=r_id).all():
                    self.del_device(device.id)
            dfa_list = self.__session.query(DeviceFeatureAssociation)\
                                     .filter_by(place_id=room.id, place_type=u'room').all()
            for dfa in dfa_list:
                self.__session.delete(dfa)
            self.__session.delete(room)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return room_d
        else:
            raise DbHelperException("Couldn't delete room with id %s : it doesn't exist" % r_id)

    def get_all_rooms_of_area(self, a_area_id):
        """
        Returns all the rooms of an area
        @param a_area_id : the area id
        @return a list of Room objects
        """
        return self.__session.query(Room).filter_by(area_id=a_area_id).all()

####
# Device usage
####
    def list_device_usages(self):
        """
        Return a list of device usages
        @return a list of DeviceUsage objects
        """
        return self.__session.query(DeviceUsage).all()

    def get_device_usage_by_name(self, du_name,):
        """
        Return information about a device usage
        @param du_name : The device usage name
        @return a DeviceUsage object
        """
        return self.__session.query(DeviceUsage)\
                             .filter(func.lower(DeviceUsage.name)==self.__to_unicode(du_name.lower()))\
                             .first()

    def add_device_usage(self, du_name, du_description=None, du_default_options=None):
        """
        Add a device_usage (temperature, heating, lighting, music, ...)
        @param du_name : device usage name
        @param du_description : device usage description (optional)
        @param du_default_options : default options (optional)
        @return a DeviceUsage (the newly created one)
        """
        self.__session.expire_all()
        du = DeviceUsage(name=self.__to_unicode(du_name), description=self.__to_unicode(du_description),
                         default_options=self.__to_unicode(du_default_options))
        self.__session.add(du)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return du

    def update_device_usage(self, du_id, du_name=None, du_description=None, du_default_options=None):
        """
        Update a device usage
        @param du_id : device usage id to be updated
        @param du_name : device usage name (optional)
        @param du_description : device usage detailed description (optional)
        @param du_default_options : default options (optional)
        @return a DeviceUsage object
        """
        self.__session.expire_all()
        device_usage = self.__session.query(DeviceUsage).filter_by(id=du_id).first()
        if device_usage is None:
            raise DbHelperException("DeviceUsage with id %s couldn't be found" % du_id)
        if du_name is not None:
            device_usage.name = self.__to_unicode(du_name)
        if du_description is not None:
            if du_description == '': du_description = None
            device_usage.description = self.__to_unicode(du_description)
        if du_default_options is not None:
            if du_default_options == '': du_default_options = None
            device_usage.default_options = self.__to_unicode(du_default_options)
        self.__session.add(device_usage)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_usage

    def del_device_usage(self, du_id, cascade_delete=False):
        """
        Delete a device usage record
        @param dc_id : id of the device usage to delete
        @return the deleted DeviceUsage object
        """
        self.__session.expire_all()
        du = self.__session.query(DeviceUsage).filter_by(id=du_id).first()
        if du:
            du_d = du
            if cascade_delete:
                for device in self.__session.query(Device).filter_by(device_usage_id=du.id).all():
                    self.del_device(device.id)
            else:
                device_list = self.__session.query(Device).filter_by(device_usage_id=du.id).all()
                if len(device_list) > 0:
                    raise DbHelperException("Couldn't delete device usage %s : there are associated devices" % du_id)

            self.__session.delete(du)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return du_d
        else:
            raise DbHelperException("Couldn't delete device usage with id %s : it doesn't exist" % du_id)

####
# Device type
####
    def list_device_types(self):
        """
        Return a list of device types
        @return a list of DeviceType objects
        """
        return self.__session.query(DeviceType).all()

    def get_device_type_by_name(self, dty_name):
        """
        Return information about a device type
        @param dty_name : The device type name
        @return a DeviceType object
        """
        return self.__session.query(DeviceType)\
                             .filter(func.lower(DeviceType.name)==self.__to_unicode(dty_name.lower()))\
                             .first()

    def add_device_type(self, dty_name, dt_id, dty_description=None):
        """
        Add a device_type (x10.Switch, x10.Dimmer, Computer.WOL...)
        @param dty_name : device type name
        @param dt_id : technology id (x10, plcbus,...)
        @param dty_description : device type description (optional)
        @return a DeviceType (the newly created one)
        """
        self.__session.expire_all()
        try:
            self.__session.query(DeviceTechnology).filter_by(id=dt_id).one()
        except NoResultFound:
            raise DbHelperException("Couldn't add device type with technology id %s. It does not exist" % dt_id)
        dty = DeviceType(name=self.__to_unicode(dty_name), description=self.__to_unicode(dty_description),
                         device_technology_id=dt_id)
        self.__session.add(dty)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return dty

    def update_device_type(self, dty_id, dty_name=None, dt_id=None,
                           dty_description=None):
        """
        Update a device type
        @param dty_id : device type id to be updated
        @param dty_name : device type name (optional)
        @param dt_id : id of the associated technology (optional)
        @param dty_description : device type detailed description (optional)
        @return a DeviceType object
        """
        self.__session.expire_all()
        device_type = self.__session.query(DeviceType).filter_by(id=dty_id).first()
        if device_type is None:
            raise DbHelperException("DeviceType with id %s couldn't be found" % dty_id)
        if dty_name is not None:
            device_type.name = self.__to_unicode(dty_name)
        if dt_id is not None:
            try:
                self.__session.query(DeviceTechnology).filter_by(id=dt_id).one()
            except NoResultFound:
                raise DbHelperException("Couldn't find technology id %s. It does not exist" % dt_id)
            device_type.device_technology_id = dt_id
        self.__session.add(device_type)
        if dty_description is not None:
            if dty_description == '': dty_description = None
            device_type.description = self.__to_unicode(dty_description)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_type

    def del_device_type(self, dty_id, cascade_delete=False):
        """
        Delete a device type record
        @param dty_id : id of the device type to delete
        @return the deleted DeviceType object
        """
        self.__session.expire_all()
        dty = self.__session.query(DeviceType).filter_by(id=dty_id).first()
        if dty:
            dty_d = dty
            if cascade_delete:
                for device in self.__session.query(Device).filter_by(device_type_id=dty.id).all():
                    self.del_device(device.id)
                for df in self.__session.query(DeviceTypeFeature).filter_by(device_type_id=dty.id).all():
                    self.del_device_type_feature(df.id)
            else:
                device_list = self.__session.query(Device).filter_by(device_type_id=dty.id).all()
                if len(device_list) > 0:
                    raise DbHelperException("Couldn't delete device type %s : there are associated device(s)" % dty_id)
                df_list = self.__session.query(DeviceTypeFeature).filter_by(device_type_id=dty.id).all()
                if len(df_list) > 0:
                    raise DbHelperException("Couldn't delete device type %s : there are associated device type feature(s)" % dty_id)
            self.__session.delete(dty)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return dty_d
        else:
            raise DbHelperException("Couldn't delete device type with id %s : it doesn't exist" % dty_id)

####
# Device type features
####
    def list_device_type_features(self):
        """
        Return a list of device type features
        @return a list of DeviceTypeFeature objects
        """
        return self.__session.query(DeviceTypeFeature).all()

    def get_device_type_feature_by_id(self, dtf_id):
        """
        Return information about a device type feature
        @param dtf_device_type_id : device type id
        @return a DeviceTypeFeature object
        """
        return self.__session.query(DeviceTypeFeature).filter_by(id=dtf_id).first()

    def add_device_type_feature(self, dtf_name, dtf_feature_type, dtf_device_type_id, dtf_parameters=None):
        """
        Add a device type feature
        @param dtf_name : device feature name (Switch, Dimmer, Thermometer, Voltmeter...)
        @param dtf_feature_type : device feature type
        @param dtf_device_type_id : device type id
        @param dtf_parameters : parameters about the command or the returned data associated to the device, optional
        @return a DeviceTechnology object (the one created)
        """
        self.__session.expire_all()
        if self.__session.query(DeviceType).filter_by(id=dtf_device_type_id).first() is None:
            raise DbHelperException("Can't add device type feature : device type id '%s' doesn't exist" % dtf_device_type_id)
        device_type_feature = DeviceTypeFeature(name=self.__to_unicode(dtf_name),
                                                feature_type=self.__to_unicode(dtf_feature_type),
                                                device_type_id=dtf_device_type_id,
                                                parameters=self.__to_unicode(dtf_parameters))
        self.__session.add(device_type_feature)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_type_feature

    def update_device_type_feature(self, dtf_id, dtf_name=None, dtf_parameters=None):
        """
        Update a device type feature
        @param dtf_id : device type feature id
        @param dtf_name : device feature name (Switch, Dimmer, Thermometer, Voltmeter...), optional
        @param dtf_parameters : parameters about the command or the returned data associated to the device, optional
        @return a DeviceTypeFeature object (the newly updated one)
        """
        self.__session.expire_all()
        device_type_feature = self.__session.query(DeviceTypeFeature).filter_by(id=dtf_id).first()
        if device_type_feature is None:
            raise DbHelperException("DeviceTypeFeature with id %s couldn't be found - can't update it" % dtf_id)
        if dtf_name is not None:
            device_type_feature.name = self.__to_unicode(dtf_name)
        if dtf_parameters is not None:
            if dtf_parameters == '':
                dtf_parameters = None
            device_type_feature.parameters = self.__to_unicode(dtf_parameters)
        self.__session.add(device_type_feature)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_type_feature

    def del_device_type_feature(self, dtf_id):
        """
        Delete a device type feature record
        @param dtf_id : device type feature id
        @return the deleted DeviceTypeFeature object
        """
        self.__session.expire_all()
        device_type_feature = self.__session.query(DeviceTypeFeature).filter_by(id=dtf_id).first()
        if device_type_feature is None:
            raise DbHelperException("Can't delete device type feature (id=%s) : it doesn't exist" % dtf_id)
        actuator_feature = self.__session.query(ActuatorFeature).filter_by(device_type_feature_id=dtf_id).first()
        if actuator_feature is not None:
            self.__session.delete(actuator_feature)
        sensor_feature = self.__session.query(SensorFeature).filter_by(device_type_feature_id=dtf_id).first()
        if sensor_feature is not None:
            self.__session.delete(sensor_feature)
        dfa_list = self.__session.query(DeviceFeatureAssociation)\
                                 .filter_by(device_type_feature_id=device_type_feature.id).all()
        for dfa in dfa_list:
            self.__session.delete(dfa)
        self.__session.delete(device_type_feature)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_type_feature

####
# Actuator features
####
    def list_actuator_features(self):
        """
        Return a list of actuator features
        @return a list of ActuatorFeature objects
        """
        return self.__session.query(ActuatorFeature).all()

    def get_actuator_feature_by_id(self, af_id):
        """
        Return information about an actuator feature
        @param af_id : actuator feature id (which is a device type feature id)
        @return an ActuatorFeature object
        """
        return self.__session.query(ActuatorFeature).filter_by(device_type_feature_id=af_id).first()

    def add_actuator_feature(self, af_id, af_value_type, af_return_confirmation=False):
        """
        Add an actuator
        @param af_id : actuator feature id (which is a device type feature id)
        @param af_value_type : value type the actuator can accept
        @param af_return_confirmation : True if the actuator returns a confirmation after having executed a command ,optional (default False)
        @return an ActuatorFeature object (the newly created one)
        """
        sensor_feature = self.__session.query(SensorFeature).filter_by(device_type_feature_id=af_id).first()
        if sensor_feature is not None:
            raise DbHelperException("Can't add this id (%s) to actuator feature. It is used by a sensor feature" % af_id)
        device_type_feature = self.__session.query(DeviceTypeFeature).filter_by(id=af_id).first()
        if device_type_feature is None:
            raise DbHelperException("Can't add actuator feature with device type feature id %s : it doesn't exist" % af_id)
        if af_value_type not in ACTUATOR_VALUE_TYPE_LIST:
            raise DbHelperException("Value type (%s) is not in the allowed item list : %s" % (af_value_type, ACTUATOR_VALUE_TYPE_LIST))
        self.__session.expire_all()
        actuator_feature = ActuatorFeature(device_type_feature_id=af_id, value_type=self.__to_unicode(af_value_type),
                                           return_confirmation=af_return_confirmation)
        self.__session.add(actuator_feature)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return actuator_feature

    def update_actuator_feature(self, af_id, af_value_type=None, af_return_confirmation=None):
        """
        Update an actuator feature
        @param af_id : actuator feature id (which is a device type feature id)
        @param af_value_type : value type the actuator can accept, optional
        @param af_return_confirmation : True if the actuator returns a confirmation after having executed a command ,optional
        @return an ActuatorFeature object (the newly updated one)
        """
        self.__session.expire_all()
        actuator_feature = self.__session.query(ActuatorFeature).filter_by(device_type_feature_id=af_id).first()
        if actuator_feature is None:
            raise DbHelperException("Actuator feature with id %s couldn't be found" % af_id)
        if af_value_type is not None:
            if af_value_type not in ACTUATOR_VALUE_TYPE_LIST:
                raise DbHelperException("Value type (%s) is not in the allowed item list : %s" % (af_value_type, ACTUATOR_VALUE_TYPE_LIST))
            actuator_feature.value_type = self.__to_unicode(af_value_type)
        if af_return_confirmation is not None:
            actuator_feature.return_confirmation = af_return_confirmation
        self.__session.add(actuator_feature)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return actuator_feature

    def del_actuator_feature(self, af_id):
        """
        Delete an actuator feature record
        @param af_id : actuator feature id (which is a device type feature id)
        @return the deleted ActuatorFeature object
        """
        self.__session.expire_all()
        actuator_feature = self.__session.query(ActuatorFeature).filter_by(device_type_feature_id=af_id).first()
        if actuator_feature is None:
            raise DbHelperException("Couldn't delete actuator feature with id %s : it doesn't exist" % af_id)
        self.__session.delete(actuator_feature)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return actuator_feature

####
# Sensor features
####
    def list_sensor_features(self):
        """
        Return a list of sensor features
        @return a list of SensorFeature objects
        """
        return self.__session.query(SensorFeature).all()

    def get_sensor_feature_by_id(self, sf_id):
        """
        Return information about a sensor feature
        @param df_id : sensor feature id (which is a device type feature id)
        @return a SensorFeature object
        """
        return self.__session.query(SensorFeature).filter_by(device_type_feature_id=sf_id).first()

    def add_sensor_feature(self, sf_id, sf_value_type):
        """
        Add a sensor
        @param sf_id : sensor feature id (which is a device type feature id)
        @param sf_value_type : value type the sensor can return
        @return a SensorFeature object (the newly created one)
        """
        actuator_feature = self.__session.query(ActuatorFeature).filter_by(device_type_feature_id=sf_id).first()
        if actuator_feature is not None:
            raise DbHelperException("Can't add this id (%s) to sensor feature. It is used by an actuator feature" % sf_id)
        device_type_feature = self.__session.query(DeviceTypeFeature).filter_by(id=sf_id).first()
        if device_type_feature is None:
            raise DbHelperException("Can't add sensor feature with device type feature id %s : it doesn't exist" % sf_id)
        if sf_value_type not in SENSOR_VALUE_TYPE_LIST:
            raise DbHelperException("Value type (%s) is not in the allowed item list : %s" % (sf_value_type, SENSOR_VALUE_TYPE_LIST))
        self.__session.expire_all()
        sensor_feature = SensorFeature(device_type_feature_id=sf_id, value_type=self.__to_unicode(sf_value_type))
        self.__session.add(sensor_feature)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return sensor_feature

    def update_sensor_feature(self, sf_id, sf_value_type=None):
        """
        Update a sensor feature
        @param sf_id : sensor feature id (which is a device type feature id)
        @param sf_value_type : value type the sensor can return, optional
        @return a SensorFeature object (the newly updated one)
        """
        self.__session.expire_all()
        sensor_feature = self.__session.query(SensorFeature).filter_by(device_type_feature_id=sf_id).first()
        if sensor_feature is None:
            raise DbHelperException("Sensor feature with id %s couldn't be found" % sf_id)
        if sf_value_type is not None:
            if sf_value_type not in SENSOR_VALUE_TYPE_LIST:
                raise DbHelperException("Value type (%s) is not in the allowed item list : %s" % (sf_value_type, SENSOR_VALUE_TYPE_LIST))
            sensor_feature.value_type = self.__to_unicode(sf_value_type)
        self.__session.add(sensor_feature)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return sensor_feature

    def del_sensor_feature(self, sf_id):
        """
        Delete a sensor feature record
        @param sf_id : sensor feature id (which is a device type feature id)
        @return the deleted SensorFeature object
        """
        self.__session.expire_all()
        sensor_feature = self.__session.query(SensorFeature).filter_by(device_type_feature_id=sf_id).first()
        if sensor_feature is None:
            raise DbHelperException("Couldn't delete sensor feature with id %s : it doesn't exist" % sf_id)
        self.__session.delete(sensor_feature)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return sensor_feature

####
# Device feature association
####
    def list_device_feature_association(self):
        """
        List all records for the device / feature association
        @return a list of DeviceFeatureAssociation objects
        """
        return self.__session.query(DeviceFeatureAssociation).all()

    def list_device_feature_association_by_house(self):
        """
        List device / feature association for the house
        @return a list of DeviceFeatureAssociation objects
        """
        return self.__session.query(DeviceFeatureAssociation).filter_by(place_type=u'house').all()

    def list_device_feature_association_by_room_id(self, room_id):
        """
        List device / feature association for a room
        @param room_id : room id
        @return a list of DeviceFeatureAssociation objects
        """
        return self.__session.query(DeviceFeatureAssociation).filter_by(place_id=room_id, place_type=u'room').all()

    def list_device_feature_association_by_area_id(self, area_id):
        """
        List device / feature association for an area
        @param area_id : area id
        @return a list of DeviceFeatureAssociation objects
        """
        return self.__session.query(DeviceFeatureAssociation).filter_by(place_id=area_id, place_type=u'area').all()

    def list_device_feature_association_by_feature_id(self, feature_id):
        """
        List device / feature association for an id of a feature of a device type
        @param feature_id : feature id
        @return a list of DeviceFeatureAssociation objects
        """
        return self.__session.query(DeviceFeatureAssociation).filter_by(device_type_feature_id=feature_id).all()

    def list_device_feature_association_by_device_id(self, d_device_id):
        """
        List device / feature association for a device id
        @param device_id : device id
        @return a list of DeviceFeatureAssociation objects
        """
        return self.__session.query(DeviceFeatureAssociation).filter_by(device_id=d_device_id).all()

    def add_device_type_feature_association(self, d_device_id, d_type_feature_id, d_place_type=None, d_place_id=None):
        """
        Add a device feature association
        @param d_device_id : device id
        @param d_type_feature_id : feature id of the device type (switch, dimmer)
        @param d_place_id : room id, area id or None for the house the device is associated to
        @param d_place_type : room, area or house (None means the device is not associated)
        @return the DeviceFeatureAssociation object
        """
        self.__session.expire_all()
        if d_place_type not in DEVICE_FEATURE_ASSOCIATION_LIST:
            raise DbHelperException("Place type should be one of : %s" % DEVICE_FEATURE_ASSOCIATION_LIST)
        if d_place_type is None and d_place_id is not None:
            raise DbHelperException("Place id should be None as item type is None")
        if (d_place_type == 'room' or d_place_type == 'area') and d_place_id is None:
            raise DbHelperException("A place id should have been provided, place type is %s" % d_place_type)
        if d_place_id is not None and d_place_type != 'house':
            if d_place_type == 'room':
                try:
                    self.__session.query(Room).filter_by(id=d_place_id).one()
                except NoResultFound:
                    raise DbHelperException("Couldn't add device with room id %s It does not exist" % d_place_id)
            else: # it is an area
                try:
                    self.__session.query(Area).filter_by(id=d_place_id).one()
                except NoResultFound:
                    raise DbHelperException("Couldn't add device with area id %s It does not exist" % d_place_id)
        device_feature_asso = DeviceFeatureAssociation(device_id=d_device_id, device_type_feature_id=d_type_feature_id,
                                                       place_type=self.__to_unicode(d_place_type), place_id=d_place_id)
        self.__session.add(device_feature_asso)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_feature_asso

    def del_device_feature_association(self, d_device_id, d_type_feature_id):
        """
        Delete a device feature association
        @param d_device_id : device id
        @param d_type_feature_id : feature id of the device type (switch, dimmer)
        @return the DeviceFeatureAssociation object which was deleted
        """
        self.__session.expire_all()
        dfa = self.__session.query(DeviceFeatureAssociation)\
                            .filter_by(device_id=d_device_id, device_type_feature_id=d_type_feature_id).first()
        if dfa is None:
            raise DbHelperException("DeviceFeatureAssociation to be deleted not found")
        self.__session.delete(dfa)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return dfa

####
# Device technology
####
    def list_device_technologies(self):
        """
        Return a list of device technologies
        @return a list of DeviceTechnology objects
        """
        return self.__session.query(DeviceTechnology).all()

    def get_device_technology_by_id(self, dt_id):
        """
        Return information about a device technology
        @param dt_id : the device technology id
        @return a DeviceTechnology object
        """
        return self.__session.query(DeviceTechnology).filter_by(id=dt_id).first()

    def add_device_technology(self, dt_id, dt_name, dt_description=None):
        """
        Add a device_technology
        @param dt_id : technology id (ie x10, plcbus, eibknx...) with no spaces / accents or special characters
        @param dt_name : device technology name, one of 'x10', '1wire', 'PLCBus', 'RFXCom', 'IR'
        @param dt_description : extended description of the technology
        """
        self.__session.expire_all()
        dt = DeviceTechnology(id=dt_id, name=self.__to_unicode(dt_name), description=self.__to_unicode(dt_description))
        self.__session.add(dt)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return dt

    def update_device_technology(self, dt_id, dt_name=None, dt_description=None):
        """
        Update a device technology
        @param dt_id : device technology id to be updated
        @param dt_name : device technology name (optional)
        @param dt_description : device technology detailed description (optional)
        @return a DeviceTechnology object
        """
        self.__session.expire_all()
        device_tech = self.__session.query(DeviceTechnology).filter_by(id=dt_id).first()
        if device_tech is None:
            raise DbHelperException("DeviceTechnology with id %s couldn't be found" % dt_id)
        if dt_name is not None:
            device_tech.name = self.__to_unicode(dt_name)
        if dt_description is not None:
            if dt_description == '': dt_description = None
            device_tech.description = self.__to_unicode(dt_description)
        self.__session.add(device_tech)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_tech

    def del_device_technology(self, dt_id, cascade_delete=False):
        """
        Delete a device technology record
        @param dt_id : id of the device technology to delete
        @return the deleted DeviceTechnology object
        """
        self.__session.expire_all()
        dt = self.__session.query(DeviceTechnology).filter_by(id=dt_id).first()
        if dt:
            dt_d = dt
            if cascade_delete:
                for device_type in self.__session.query(DeviceType).filter_by(device_technology_id=dt.id).all():
                    self.del_device_type(device_type.id, cascade_delete=True)
            else:
                device_type_list = self.__session.query(DeviceType).filter_by(device_technology_id=dt.id).all()
                if len(device_type_list) > 0:
                    raise DbHelperException("Couldn't delete device technology %s : there are associated device types" % dt_id)

            self.__session.delete(dt)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return dt_d
        else:
            raise DbHelperException("Couldn't delete device technology with id %s : it doesn't exist" % dt_id)

####
# Plugin config
####
    def list_plugin_config(self, pl_name):
        """
        Return all keys and values of a plugin
        @param pl_name : plugin name
        @return a list of PluginConfig objects
        """
        return self.__session.query(PluginConfig)\
                             .filter_by(plugin_name=self.__to_unicode(pl_name)).all()

    def list_all_plugin_config(self):
        """
        Return a list of all plugin parameters
        @return a list of PluginConfig objects
        """
        return self.__session.query(PluginConfig).all()

    def get_plugin_config(self, pl_name, pl_key):
        """
        Return information about a plugin parameter
        @param pl_name : plugin name
        @param pl_key : key we want the value from
        @return a PluginConfig object
        """
        return self.__session.query(PluginConfig)\
                             .filter_by(plugin_name=self.__to_unicode(pl_name))\
                             .filter_by(key=self.__to_unicode(pl_key))\
                             .first()

    def set_plugin_config(self, pl_name, pl_key, pl_value):
        """
        Add / update a plugin parameter
        @param pl_name : plugin name
        @param pl_key : key we want to add / update
        @param pl_value : key value we want to add / update
        @return : the added / updated PluginConfig item
        """
        self.__session.expire_all()
        plugin_key = self.__session.query(PluginConfig)\
                                   .filter_by(plugin_name=self.__to_unicode(pl_name), key=self.__to_unicode(pl_key))\
                                   .first()
        if plugin_key is None:
            plugin_key = PluginConfig(plugin_name=self.__to_unicode(pl_name), key=self.__to_unicode(pl_key),
                                      value=self.__to_unicode(pl_value))
        else:
            plugin_key.value = self.__to_unicode(pl_value)
        self.__session.add(plugin_key)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return plugin_key

    def del_plugin_config(self, pl_name):
        """
        Delete all parameters of a plugin
        @param pl_name : plugin name
        @return the deleted PluginConfig objects (list)
        """
        self.__session.expire_all()
        plugin_key_list = self.__session.query(PluginConfig)\
                              .filter_by(plugin_name=self.__to_unicode(pl_name)).all()
        pl_key_deleted_list = []
        for plugin_key in plugin_key_list:
            plugin_key_d = plugin_key
            pl_key_deleted_list.append(plugin_key_d)
            self.__session.delete(plugin_key)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return pl_key_deleted_list

###
# Devices
###
    def list_devices(self):
        """
        Returns a list of devices
        @return a list of Device objects
        """
        return self.__session.query(Device).all()

    def get_device(self, d_id):
        """
        Return a device by its id
        @param d_id : The device id
        @return a Device object
        """
        return self.__session.query(Device).filter_by(id=d_id).first()

    def get_device_by_technology_and_address(self, techno_name, device_address):
        """
        Return a device by its technology and address
        @param techno_name : technology name
        @param device address : device address
        @return a device object
        """
        device_list = self.__session.query(Device)\
                                    .filter_by(address=self.__to_unicode(device_address))\
                                    .all()
        if len(device_list) == 0:
            return None
        device = []
        for device in device_list:
            device_type = self.__session.query(DeviceType).filter_by(id=device.device_type_id).first()
            device_tech = self.__session.query(DeviceTechnology).filter_by(id=device_type.device_technology_id).first()
            if device_tech.name.lower() == self.__to_unicode(techno_name.lower()):
                return device
        return None

    def get_all_devices_of_room(self, d_room_id):
        """
        Return all the devices of a room
        @param d_room_id: room id
        @return a list of Device objects
        """
        return self.__session.query(Device)\
                             .filter_by(room_id=d_room_id).all()

    def get_all_devices_of_area(self, d_area_id):
        """
        Return all the devices of an area
        @param d_area_id : the area id
        @return a list of Device objects
        """
        device_list = []
        for room in self.__session.query(Room).filter_by(area_id=d_area_id).all():
            for device in self.__session.query(Device).filter_by(room_id=room.id).all():
                device_list.append(device)
        return device_list

    def get_all_devices_of_usage(self, du_id):
        """
        Return all the devices of a usage
        @param du_id: usage id
        @return a list of Device objects
        """
        return self.__session.query(Device)\
                             .filter_by(usage_id=du_id).all()

    def get_all_devices_of_technology(self, dt_id):
        """
        Returns all the devices of a technology
        @param dt_id : technology id
        @return a list of Device objects
        """
        return self.__session.query(Device)\
                             .filter_by(technology_id=dt_id).all()

    def add_device(self, d_name, d_address, d_type_id, d_usage_id, d_description=None, d_reference=None):
        """
        Add a device item
        @param d_name : name of the device
        @param d_address : address (ex : 'A3' for x10/plcbus, '111.111111111' for 1wire)
        @param d_type_id : device type id (x10.Switch, x10.Dimmer, Computer.WOL...)
        @param d_usage_id : usage id (ex. temperature)
        @param d_description : extended device description, optional
        @param d_reference : device reference (ex. AM12 for x10), optional
        @return the new Device object
        """
        self.__session.expire_all()
        try:
            self.__session.query(DeviceType).filter_by(id=d_type_id).one()
        except NoResultFound:
            raise DbHelperException("Couldn't add device with device type id %s It does not exist" % d_type_id)
        try:
            self.__session.query(DeviceUsage).filter_by(id=d_usage_id).one()
        except NoResultFound:
            raise DbHelperException("Couldn't add device with device usage id %s It does not exist" % d_usage_id)
        device = Device(name=self.__to_unicode(d_name), address=self.__to_unicode(d_address),
                        description=self.__to_unicode(d_description),
                        reference=self.__to_unicode(d_reference), device_type_id=d_type_id,
                        device_usage_id=d_usage_id)
        self.__session.add(device)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device

    def update_device(self, d_id, d_name=None, d_address=None, d_type_id=None,
                      d_usage_id=None, d_description=None, d_reference=None):
        """
        Update a device item
        If a param is None, then the old value will be kept
        @param d_id : Device id
        @param d_name : device name (optional)
        @param d_address : Item address (ex : 'A3' for x10/plcbus, '111.111111111' for 1wire) (optional)
        @param d_description : Extended item description (optional)
        @param d_type_id : type id (x10.Switch, x10.Dimmer, Computer.WOL...)
        @param d_usage : Item usage id (optional)
        @param d_room : Item room id (optional)
        @return the updated Device object
        """
        self.__session.expire_all()
        device = self.__session.query(Device).filter_by(id=d_id).first()
        if device is None:
            raise DbHelperException("Device with id %s couldn't be found" % d_id)
        if d_name is not None:
            device.name = self.__to_unicode(d_name)
        if d_address is not None:
            device.address = self.__to_unicode(d_address)
        if d_description is not None:
            if d_description == '': d_description = None
            device.description = self.__to_unicode(d_description)
        if d_reference is not None:
            if d_reference == '': d_reference = None
            device.reference = self.__to_unicode(d_reference)
        if d_type_id is not None:
            try:
                self.__session.query(DeviceType).filter_by(id=d_type_id).one()
            except NoResultFound:
                raise DbHelperException("Couldn't find device type id %s. It does not exist" % d_type_id)
            device.device_type_id = d_type_id
        if d_usage_id is not None:
            try:
              self.__session.query(DeviceUsage).filter_by(id=d_usage_id).one()
            except NoResultFound:
              raise DbHelperException("Couldn't find device usage id %s. It does not exist" % d_usage_id)
            device.device_usage = d_usage_id
        self.__session.add(device)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device

    def del_device(self, d_id):
        """
        Delete a device
        Warning : this deletes also the associated objects (DeviceConfig, DeviceStats, DeviceStatsValue)
        @param d_id : item id
        @return the deleted Device object
        """
        self.__session.expire_all()
        device = self.__session.query(Device).filter_by(id=d_id).first()
        if device is None:
            raise DbHelperException("Device with id %s couldn't be found" % d_id)

        device_d = device
        for device_conf in self.__session.query(DeviceConfig)\
                                         .filter_by(device_id=d_id).all():
            self.__session.delete(device_conf)

        for device_stats in self.__session.query(DeviceStats).filter_by(device_id=d_id).all():
            for device_stats_value in self.__session.query(DeviceStatsValue)\
                                                    .filter_by(device_stats_id=device_stats.id).all():
                self.__session.delete(device_stats_value)
            self.__session.delete(device_stats)
        for device_feat_asso in self.__session.query(DeviceFeatureAssociation).filter_by(device_id=d_id).all():
            self.__session.delete(device_feat_asso)
        self.__session.delete(device)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_d

####
# Device config
####
    def list_all_device_config(self):
        """
        List all device config parameters
        @return A list of DeviceConfig objects
        """
        return self.__session.query(DeviceConfig).all()

    def list_device_config(self, dc_device_id):
        """
        List all config keys of a device
        @param dc_device_id : device id
        @return A list of DeviceConfig objects
        """
        return self.__session.query(DeviceConfig).filter_by(device_id=dc_device_id).all()

    def get_device_config_by_key(self, dc_key, dc_device_id):
        """
        Get a key of a device configuration
        @param dc_key : key name
        @param dc_device_id : device id
        @return A DeviceConfig object
        """
        return self.__session.query(DeviceConfig).filter_by(key=dc_key, device_id=dc_device_id).first()


    def set_device_config(self, dc_key, dc_value, dc_device_id):
        """
        Add / update an device config key
        @param dc_key : key name
        @param dc_value : associated value
        @param dc_device_id : device id
        @return : the added/updated DeviceConfig object
        """
        self.__session.expire_all()
        device_config = self.__session.query(DeviceConfig).filter_by(key=dc_key, device_id=dc_device_id).first()
        if device_config is None:
            device_config = DeviceConfig(key=dc_key, value=self.__to_unicode(dc_value), device_id=dc_device_id)
        else:
            device_config.value = self.__to_unicode(dc_value)
        self.__session.add(device_config)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_config

    def del_device_config(self, dc_device_id):
        """
        Delete a device configuration key
        @param dc_device_id : device id
        @return The DeviceConfig object which was deleted
        """
        self.__session.expire_all()
        dc_list = self.__session.query(DeviceConfig).filter_by(device_id=dc_device_id).all()
        if dc_list is None:
            raise DbHelperException("Couldnt delete device config for device id %s : it doesn't exist" % dc_device_id)
        dc_list_d = []
        for device_config in dc_list:
            dc_list_d.append(device_config)
            self.__session.delete(device_config)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return dc_list_d

####
# Device stats
####
    def list_device_stats(self, d_device_id):
        """
        Return a list of all stats for a device
        @param d_device_id : the device id
        @return a list of DeviceStats objects
        """
        return self.__session.query(DeviceStats)\
                             .filter_by(device_id=d_device_id).all()

    def list_all_device_stats(self):
        """
        Return a list of all device stats
        @return a list of DeviceStats objects
        """
        return self.__session.query(DeviceStats).all()

    def list_device_stats_values(self, d_device_stats_id):
        """
        Return a list of all values associated to a device statistic
        @param d_device_stats_id : the device statistic id
        @return a list of DeviceStatsValue objects
        """
        return self.__session.query(DeviceStatsValue)\
                             .filter_by(device_stats_id=d_device_stats_id).all()

    def get_last_stat_of_device(self, d_device_id):
        """
        Fetch the last record of stats for a device
        @param d_device_id : device id
        @return a DeviceStat object
        """
        return self.__session.query(DeviceStats)\
                             .filter_by(device_id=d_device_id)\
                             .order_by(sqlalchemy.desc(DeviceStats.date)).first()

    def get_last_stat_of_devices(self, device_list):
        """
        Fetch the last record for all devices in d_list
        @param device_list : list of device ids
        @return a list of DeviceStats objects
        """
        assert type(device_list) is ListType
        result = []
        for d_id in device_list:
            last_record = self.__session.query(DeviceStats)\
                                        .filter_by(device_id=d_id)\
                                        .order_by(sqlalchemy.desc(DeviceStats.date)).first()
            result.append(last_record)
        return result

    def device_has_stats(self, d_device_id):
        """
        Check if the device has stats that were recorded
        @param d_device_id : device id
        @return True or False
        """
        return self.__session.query(DeviceStats)\
                             .filter_by(device_id=d_device_id).count() > 0

    def add_device_stat(self, d_id, ds_date, ds_values):
        """
        Add a device stat record
        @param d_id : device id
        @param ds_date : when the stat was gathered (timestamp)
        @param ds_value : dictionnary of statistics values
        @return the new DeviceStats object
        """
        self.__session.expire_all()
        try:
            self.__session.query(Device).filter_by(id=d_id).one()
        except NoResultFound:
            raise DbHelperException("Couldn't add device stat with device id %s. It does not exist" % d_id)
        device_stat = DeviceStats(device_id=d_id, date=ds_date)
        self.__session.add(device_stat)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        for ds_name in ds_values.keys():
            dsv = DeviceStatsValue(name=self.__to_unicode(ds_name), value=self.__to_unicode(ds_values[ds_name]),
                                   device_stats_id=device_stat.id)
            self.__session.add(dsv)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_stat

    def del_device_stat(self, ds_id):
        """
        Delete a stat record
        @param ds_id : record id
        @return the deleted DeviceStat object
        """
        self.__session.expire_all()
        device_stat = self.__session.query(DeviceStats).filter_by(id=ds_id).first()
        if device_stat:
            device_stat_d = device_stat
            self.__session.delete(device_stat)
            for device_stats_value in self.__session.query(DeviceStatsValue) \
                                                    .filter_by(device_stats_id=device_stat.id).all():
                self.__session.delete(device_stats_value)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return device_stat_d
        else:
            raise DbHelperException("Couldn't delete device stat with id %s : it doesn't exist" % ds_id)

    def del_all_device_stats(self, d_id):
        """
        Delete all stats for a device
        @param d_id : device id
        @return the list of DeviceStatsValue objects that were deleted
        """
        self.__session.expire_all()
        #TODO : this could be optimized
        device_stats = self.__session.query(DeviceStats).filter_by(device_id=d_id).all()
        device_stats_d_list = []
        for device_stat in device_stats:
            for device_stats_value in self.__session.query(DeviceStatsValue) \
                                                    .filter_by(device_stats_id=device_stat.id).all():
                self.__session.delete(device_stats_value)
            device_stats_d_list.append(device_stat)
            self.__session.delete(device_stat)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return device_stats_d_list

####
# Triggers
####
    def list_triggers(self):
        """
        Returns a list of all triggers
        @return a list of Trigger objects
        """
        return self.__session.query(Trigger).all()

    def get_trigger(self, t_id):
        """
        Returns a trigger information from id
        @param t_id : trigger id
        @return a Trigger object
        """
        return self.__session.query(Trigger).filter_by(id=t_id).first()

    def add_trigger(self, t_description, t_rule, t_result):
        """
        Add a trigger
        @param t_description : trigger description
        @param t_rule : trigger rule
        @param t_result : trigger result (list of strings)
        @return the new Trigger object
        """
        self.__session.expire_all()
        trigger = Trigger(description=self.__to_unicode(t_description), rule=self.__to_unicode(t_rule),
                          result=self.__to_unicode(';'.join(t_result)))
        self.__session.add(trigger)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return trigger

    def update_trigger(self, t_id, t_description=None, t_rule=None, t_result=None):
        """
        Update a trigger
        @param dt_id : trigger id to be updated
        @param t_description : trigger description
        @param t_rule : trigger rule
        @param t_result : trigger result (list of strings)
        @return a Trigger object
        """
        self.__session.expire_all()
        trigger = self.__session.query(Trigger).filter_by(id=t_id).first()
        if trigger is None:
            raise DbHelperException("Trigger with id %s couldn't be found" % t_id)
        if t_description is not None:
            if t_description == '': t_description = None
            trigger.description = self.__to_unicode(t_description)
        if t_rule is not None:
            trigger.rule = self.__to_unicode(t_rule)
        if t_result is not None:
            trigger.result = self.__to_unicode(';'.join(t_result))
        self.__session.add(trigger)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return trigger

    def del_trigger(self, t_id):
        """
        Delete a trigger
        @param t_id : trigger id
        @return the deleted Trigger object
        """
        self.__session.expire_all()
        trigger = self.__session.query(Trigger).filter_by(id=t_id).first()
        if trigger:
            trigger_d = trigger
            self.__session.delete(trigger)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return trigger_d
        else:
            raise DbHelperException("Couldn't delete trigger with id %s : it doesn't exist" % t_id)

####
# User accounts
####
    def list_user_accounts(self):
        """
        Returns a list of all accounts
        @return a list of UserAccount objects
        """
        list_sa = self.__session.query(UserAccount).all()
        for user_acc in list_sa:
            # I won't send the password, right?
            user_acc.password = None
        return list_sa

    def get_user_account(self, a_id):
        """
        Return user account information from id
        @param a_id : account id
        @return a UserAccount object
        """
        user_acc = self.__session.query(UserAccount)\
                                 .filter_by(id=a_id).first()
        if user_acc is not None:
            user_acc.password = None
        return user_acc

    def get_user_account_by_login(self, a_login):
        """
        Return user account information from login
        @param a_login : login
        @return a UserAccount object
        """
        user_acc = self.__session.query(UserAccount).filter_by(login=self.__to_unicode(a_login))\
                                                    .first()
        if user_acc is not None:
            user_acc.password = None
        return user_acc

    def get_user_account_by_login_and_pass(self, a_login, a_password):
        """
        Return user account information from login
        @param a_login : login
        @param a_pass : password (clear text)
        @return a UserAccount object or None if login / password is wrong
        """
        crypted_pass = self.__make_crypted_password(a_password)
        user_acc = self.__session.query(UserAccount)\
                                 .filter_by(login=self.__to_unicode(a_login),
                                            password=self.__to_unicode(crypted_pass))\
                                 .first()
        if user_acc is not None:
            user_acc.password = None
        return user_acc

    def get_user_account_by_person(self, p_id):
        """
        Return a user account associated to a person, if existing
        @param p_id : The person id
        @return a UserAccount object
        """
        user = self.__session.query(UserAccount).filter_by(person_id=p_id).first()
        if user is not None:
            user.password = None
        return user

    def authenticate(self, a_login, a_password):
        """
        Check if a user account with a_login, a_password exists
        @param a_login : Account login
        @param a_password : Account password (clear)
        @return True or False
        """
        self.__session.expire_all()
        user_acc = self.__session.query(UserAccount).filter_by(login=self.__to_unicode(a_login))\
                                                    .first()
        if user_acc is not None:
            password = hashlib.sha256()
            password.update(self.__to_unicode(a_password))
            if user_acc.password == password.hexdigest():
                return True
        return False

    def add_user_account(self, a_login, a_password, a_person_id, a_is_admin=False,
                         a_skin_used=''):
        """
        Add a user account
        @param a_login : Account login
        @param a_password : Account clear text password (will be hashed in sha256)
        @param a_person_id : id of the person associated to the account
        @param a_is_admin : True if it is an admin account, False otherwise (optional, default=False)
        @return the new UserAccount object or raise a DbHelperException if it already exists
        """
        self.__session.expire_all()
        user_account = self.__session.query(UserAccount).filter_by(login=self.__to_unicode(a_login)).first()
        if user_account is not None:
            raise DbHelperException("Error %s login already exists" % a_login)
        person = self.__session.query(Person).filter_by(id=a_person_id).first()
        if person is None:
            raise DbHelperException("Person id '%s' does not exist" % a_person_id)
        user_account = UserAccount(login=self.__to_unicode(a_login),
                                   password=self.__to_unicode(self.__make_crypted_password(a_password)),
                                   person_id=a_person_id,
                                   is_admin=a_is_admin, skin_used=self.__to_unicode(a_skin_used))
        self.__session.add(user_account)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        user_account.password = None
        return user_account

    def add_user_account_with_person(self, a_login, a_password, a_person_first_name,
                                     a_person_last_name, a_person_birthdate=None,
                                     a_is_admin=False, a_skin_used=''):
        """
        Add a user account and a person
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

    def update_user_account(self, a_id, a_new_login=None, a_person_id=None,
                            a_is_admin=None, a_skin_used=None):
        """
        Update a user account
        @param a_id : Account id to be updated
        @param a_new_login : The new login (optional)
        @param a_person_id : id of the person associated to the account
        @param a_is_admin : True if it is an admin account, False otherwise (optional)
        @param a_skin_used : name of the skin choosen by the user (optional, default='skins/default')
        @return a UserAccount object
        """
        self.__session.expire_all()
        user_acc = self.__session.query(UserAccount).filter_by(id=a_id).first()
        if user_acc is None:
            raise DbHelperException("UserAccount with id %s couldn't be found" % a_id)
        if a_new_login is not None:
            user_acc.login = self.__to_unicode(a_new_login)
        if a_person_id is not None:
            person = self.__session.query(Person).filter_by(id=a_person_id).first()
            if person is None:
                raise DbHelperException("Person id '%s' does not exist" % a_person_id)
            user_acc.person_id = a_person_id
        if a_is_admin is not None:
            user_acc.is_admin = a_is_admin
        if a_skin_used is not None:
            user_acc.skin_used = self.__to_unicode(a_skin_used)
        self.__session.add(user_acc)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        user_acc.password = None
        return user_acc

    def update_user_account_with_person(self, a_id, a_login=None, p_first_name=None,
                            p_last_name=None, p_birthdate=None, a_is_admin=None,
                            a_skin_used=None):
        """
        Update a user account a person information
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
        self.__session.expire_all()
        person = user_acc.person
        if p_first_name is not None:
            person.first_name = self.__to_unicode(p_first_name)
        if p_last_name is not None:
            person.last_name = self.__to_unicode(p_last_name)
        if p_birthdate is not None:
            person.birthdate = p_birthdate
        self.__session.add(person)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        user_acc.password = None
        return user_acc

    def change_password(self, a_id, a_old_password, a_new_password):
        """
        Change the password
        @param a_id : account id
        @param a_old_password : the password to change (the old one, in clear text)
        @param a_new_password : the new password, in clear text (will be hashed in sha256)
        @return True if the password could be changed, False otherwise (login or old_password is wrong)
        """
        self.__session.expire_all()
        old_pass = self.__make_crypted_password(a_old_password)
        user_acc = self.__session.query(UserAccount).filter_by(id=a_id, password=self.__to_unicode(old_pass)).first()
        if user_acc is None:
            return False
        user_acc.password = self.__to_unicode(self.__make_crypted_password(a_new_password))
        self.__session.add(user_acc)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return True

    def __make_crypted_password(self, clear_text_password):
        """
        Make a crypted password (using sha256)
        @param clear_text_password : password in clear text
        @return crypted password
        """
        password = hashlib.sha256()
        password.update(clear_text_password)
        return password.hexdigest()

    def add_default_user_account(self):
        """
        Add a default user account (login = admin, password = domogik, is_admin = True)
        @return a UserAccount object
        """
        person = self.add_person(p_first_name='Admin', p_last_name='Admin',
                                 p_birthdate=datetime.date(1900, 01, 01))
        return self.add_user_account(a_login='admin', a_password='123',
                                     a_person_id=person.id, a_is_admin=True)

    def del_user_account(self, a_id):
        """
        Delete a user account
        @param a_id : account id
        @return the deleted UserAccount object
        """
        self.__session.expire_all()
        user_account = self.__session.query(UserAccount).filter_by(id=a_id).first()
        if user_account:
            user_account_d = user_account
            self.__session.delete(user_account)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return user_account_d
        else:
            raise DbHelperException("Couldn't delete user account with id %s : it doesn't exist" % a_id)

####
# Persons
####
    def list_persons(self):
        """
        Returns the list of all persons
        @return a list of Person objects
        """
        return self.__session.query(Person).all()

    def get_person(self, p_id):
        """
        Returns person information
        @param p_id : person id
        @return a Person object
        """
        return self.__session.query(Person).filter_by(id=p_id).first()

    def add_person(self, p_first_name, p_last_name, p_birthdate=None):
        """
        Add a person
        @param p_first_name     : first name
        @param p_last_name      : last name
        @param p_birthdate      : birthdate, optional
        @param p_user_account   : Person account on the user (optional)
        @return the new Person object
        """
        self.__session.expire_all()
        person = Person(first_name=self.__to_unicode(p_first_name), last_name=self.__to_unicode(p_last_name),
                        birthdate=p_birthdate)
        self.__session.add(person)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return person

    def update_person(self, p_id, p_first_name=None, p_last_name=None,
                      p_birthdate=None):
        """
        Update a person
        @param p_id             : person id to be updated
        @param p_first_name     : first name (optional)
        @param p_last_name      : last name (optional)
        @param p_birthdate      : birthdate (optional)
        @return a Person object
        """
        self.__session.expire_all()
        person = self.__session.query(Person).filter_by(id=p_id).first()
        if person is None:
            raise DbHelperException("Person with id %s couldn't be found" % p_id)
        if p_first_name is not None:
            person.first_name = self.__to_unicode(p_first_name)
        if p_last_name is not None:
            person.last_name = self.__to_unicode(p_last_name)
        if p_birthdate is not None:
            if p_birthdate == '':
                p_birthdate = None
            person.birthdate = p_birthdate
        self.__session.add(person)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return person

    def del_person(self, p_id):
        """
        Delete a person and the associated user account if it exists
        @param p_id : person account id
        @return the deleted Person object
        """
        self.__session.expire_all()
        person = self.__session.query(Person).filter_by(id=p_id).first()
        if person is not None:
            user = self.__session.query(UserAccount).filter_by(person_id=p_id).first()
            if user is not None:
                self.__session.delete(user)
            person_d = person
            self.__session.delete(person)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return person_d
        else:
            raise DbHelperException("Couldn't delete person with id %s : it doesn't exist" % p_id)

####
# System stats
####
    def list_system_stats(self):
        """
        Return a list of all system stats
        @return a list of SystemStats objects
        """
        return self.__session.query(SystemStats).all()

    def list_system_stats_values(self, s_system_stats_id):
        """
        Return a list of all values associated to a system statistic
        @param s_system_stats_id : the system statistic id
        @return a list of SystemStatsValue objects
        """
        return self.__session.query(SystemStatsValue)\
                             .filter_by(system_stats_id=s_system_stats_id).all()

    def get_system_stat(self, s_id):
        """
        Return a system stat
        @param s_name : the name of the stat to be retrieved
        @return a SystemStats object
        """
        return self.__session.query(SystemStats).filter_by(id=s_id).first()

    def add_system_stat(self, s_name, s_hostname, s_date, s_values):
        """
        Add a system stat record
        @param s_name : name of the  plugin
        @param s_hostname : name of the  host
        @param s_date : when the stat was gathered (timestamp)
        @param s_values : a dictionnary of system statistics values
        @return the new SystemStats object
        """
        self.__session.expire_all()
        system_stat = SystemStats(plugin_name=self.__to_unicode(s_name), host_name=self.__to_unicode(s_hostname),
                                  date=s_date)
        self.__session.add(system_stat)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        for stat_value_name in s_values.keys():
            ssv = SystemStatsValue(name=self.__to_unicode(stat_value_name),
                                   value=self.__to_unicode(s_values[stat_value_name]),
                                   system_stats_id=system_stat.id)
            self.__session.add(ssv)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return system_stat

    def del_system_stat(self, s_name):
        """
        Delete a system stat record
        @param s_name : name of the stat that has to be deleted
        @return the deleted SystemStats object
        """
        self.__session.expire_all()
        system_stat = self.__session.query(SystemStats).filter_by(name=self.__to_unicode(s_name)).first()
        if system_stat:
            system_stat_d = system_stat
            system_stats_values = self.__session.query(SystemStatsValue)\
                                                .filter_by(system_stats_id=system_stat.id).all()
            for ssv in system_stats_values:
                self.__session.delete(ssv)
            self.__session.delete(system_stat)
            try:
                self.__session.commit()
            except Exception, sql_exception:
                self.__session.rollback()
                raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
            return system_stat_d
        else:
            raise DbHelperException("Couldn't delete system stat %s : it doesn't exist" % s_name)

    def del_all_system_stats(self):
        """
        Delete all stats of the system
        @return the list of deleted SystemStats objects
        """
        self.__session.expire_all()
        system_stats_list = self.__session.query(SystemStats).all()
        system_stats_d_list = []
        for system_stat in system_stats_list:
            system_stats_values = self.__session.query(SystemStatsValue)\
                                                .filter_by(system_stats_id=system_stat.id).all()
            for ssv in system_stats_values:
                self.__session.delete(ssv)
            system_stats_d_list.append(system_stat)
            self.__session.delete(system_stat)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return system_stats_d_list


###
# UIItemConfig
###

    def set_ui_item_config(self, ui_item_name, ui_item_reference, ui_item_key, ui_item_value):
        """
        Add / update an UI parameter
        @param ui_item_name : item name
        @param ui_item_reference : the item reference
        @param ui_item_key : key we want to add / update
        @param ui_item_value : key value we want to add / update
        @return : the updated UIItemConfig item
        """
        self.__session.expire_all()
        ui_item_config = self.get_ui_item_config(ui_item_name, ui_item_reference, ui_item_key)
        if ui_item_config is None:
            ui_item_config = UIItemConfig(name=self.__to_unicode(ui_item_name),
                                          reference=self.__to_unicode(ui_item_reference),
                                          key=self.__to_unicode(ui_item_key), value=self.__to_unicode(ui_item_value))
        else:
            ui_item_config.value = self.__to_unicode(ui_item_value)
        self.__session.add(ui_item_config)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return ui_item_config

    def get_ui_item_config(self, ui_item_name, ui_item_reference, ui_item_key):
        """
        Get a UI parameter of an item
        @param ui_item_name : item name
        @param ui_item_reference : item reference
        @param ui_item_key : key
        @return an UIItemConfig object
        """
        return self.__session.query(UIItemConfig)\
                             .filter_by(name=self.__to_unicode(ui_item_name),
                                        reference=self.__to_unicode(ui_item_reference),
                                        key=self.__to_unicode(ui_item_key))\
                             .first()

    def list_ui_item_config_by_ref(self, ui_item_name, ui_item_reference):
        """
        List all UI parameters of an item
        @param ui_item_name : item name
        @param ui_item_reference : item reference
        @return a list of UIItemConfig objects
        """
        return self.__session.query(UIItemConfig)\
                             .filter_by(name=self.__to_unicode(ui_item_name),
                                        reference=self.__to_unicode(ui_item_reference))\
                             .all()

    def list_ui_item_config_by_key(self, ui_item_name, ui_item_key):
        """
        List all UI parameters of an item
        @param ui_item_name : item name
        @param ui_item_key : item key
        @return a list of UIItemConfig objects
        """
        return self.__session.query(UIItemConfig)\
                             .filter_by(name=self.__to_unicode(ui_item_name),
                                        key=self.__to_unicode(ui_item_key))\
                             .all()

    def list_ui_item_config(self, ui_item_name):
        """
        List all UI parameters of an item
        @param ui_item_name : item name
        @return a list of UIItemConfig objects
        """
        return self.__session.query(UIItemConfig)\
                             .filter_by(name=self.__to_unicode(ui_item_name))\
                             .all()

    def list_all_ui_item_config(self):
        """
        List all UI parameters
        @return a list of UIItemConfig objects
        """
        return self.__session.query(UIItemConfig).all()

    def delete_ui_item_config(self, ui_item_name, ui_item_reference=None, ui_item_key=None):
        """
        Delete a UI parameter of an item
        @param ui_item_name : item name
        @param ui_item_reference : item reference, optional
        @param ui_item_key : key of the item, optional
        @return the deleted UIItemConfig object(s)
        """
        self.__session.expire_all()
        ui_item_config_list = []
        if ui_item_reference == None and ui_item_key == None:
            ui_item_config_list = self.__session.query(UIItemConfig)\
                                                .filter_by(name=self.__to_unicode(ui_item_name)).all()
        elif ui_item_key is None:
            ui_item_config_list = self.__session.query(UIItemConfig)\
                                                .filter_by(name=self.__to_unicode(ui_item_name),
                                                           reference=self.__to_unicode(ui_item_reference))\
                                                .all()
        elif ui_item_reference is None:
            ui_item_config_list = self.__session.query(UIItemConfig)\
                                                .filter_by(name=self.__to_unicode(ui_item_name),
                                                           key=self.__to_unicode(ui_item_key))\
                                                .all()
        else:
            ui_item_config = self.get_ui_item_config(ui_item_name, ui_item_reference, ui_item_key)
            if ui_item_config is not None:
                ui_item_config_list.append(ui_item_config)

        if len(ui_item_config_list) == 0:
            raise DbHelperException("Can't find item for (%s, %s, %s)" % (ui_item_name, ui_item_reference, ui_item_key))
        ui_item_config_list_d = ui_item_config_list
        for item in ui_item_config_list:
            self.__session.delete(item)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return ui_item_config_list_d

###
# SystemConfig
###
    def get_system_config(self):
        """
        Get current system configuration
        @return a SystemConfig object
        """
        try:
            return self.__session.query(SystemConfig).one()
        except MultipleResultsFound:
            raise DbHelperException("Error : SystemConfig has more than one line")
        except NoResultFound:
            pass

    def update_system_config(self, s_simulation_mode=None, s_debug_mode=None):
        """
        Update (or create) system configuration
        @param s_simulation_mode : True if the system is running in simulation mode (optional)
        @param s_debug_mode : True if the system is running in debug mode (optional)
        @return a SystemConfig object
        """
        self.__session.expire_all()
        system_config = self.__session.query(SystemConfig).first()
        if system_config is not None:
            if s_simulation_mode is not None:
                system_config.simulation_mode = s_simulation_mode
            if s_debug_mode is not None:
                system_config.debug_mode = s_debug_mode
        else:
            system_config = SystemConfig(simulation_mode=s_simulation_mode,
                                         debug_mode=s_debug_mode)
        self.__session.add(system_config)
        try:
            self.__session.commit()
        except Exception, sql_exception:
            self.__session.rollback()
            raise DbHelperException("SQL exception (commit) : %s" % sql_exception)
        return system_config
