# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2009-2013 Stephan Raue (stephan@openelec.tv)
# Copyright (C) 2013 Lutz Fiebach (lufie@openelec.tv)
# Copyright (C) 2019-present Team LibreELEC (https://libreelec.tv)

import log
import modules
import oe
import os
import xbmc
import xbmcgui
import time
import dbus
import dbus.service
import threading
import oeWindows


class bluetooth(modules.Module):

    menu = {'6': {
        'name': 32331,
        'menuLoader': 'menu_connections',
        'listTyp': 'btlist',
        'InfoText': 704,
        }}
    ENABLED = False
    OBEX_ROOT = None
    OBEX_DAEMON = None
    BLUETOOTH_DAEMON = None
    D_OBEXD_ROOT = None

    @log.log_function()
    def __init__(self, oeMain):
        super().__init__()
        self.visible = False
        self.listItems = {}
        self.dbusBluezAdapter = None

    def do_init(self):
        try:
            oe.dbg_log('bluetooth::do_init', 'enter_function', oe.LOGDEBUG)
            self.visible = True
            oe.dbg_log('bluetooth::do_init', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::do_init', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def start_service(self):
        try:
            oe.dbg_log('bluetooth::start_service', 'enter_function', oe.LOGDEBUG)
            if 'org.bluez' in oe.dbusSystemBus.list_names():
                self.init_adapter()
            oe.dbg_log('bluetooth::start_service', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::start_service', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def stop_service(self):
        try:
            oe.dbg_log('bluetooth::stop_service', 'enter_function', oe.LOGDEBUG)
            if hasattr(self, 'discovery_thread'):
                try:
                    self.discovery_thread.stop()
                    del self.discovery_thread
                except AttributeError:
                    pass
            if hasattr(self, 'dbusBluezAdapter'):
                self.dbusBluezAdapter = None
            oe.dbg_log('bluetooth::stop_service', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::stop_service', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def exit(self):
        try:
            oe.dbg_log('bluetooth::exit', 'enter_function', oe.LOGDEBUG)
            if hasattr(self, 'discovery_thread'):
                try:
                    self.discovery_thread.stop()
                    del self.discovery_thread
                except AttributeError:
                    pass
            self.clear_list()
            self.visible = False
            oe.dbg_log('bluetooth::exit', 'exit_function', oe.LOGDEBUG)
            pass
        except Exception as e:
            oe.dbg_log('bluetooth::exit', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    # ###################################################################
    # # Bluetooth Adapter
    # ###################################################################

    def init_adapter(self):
        try:
            oe.dbg_log('bluetooth::init_adapter', 'enter_function', oe.LOGDEBUG)
            dbusBluezManager = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
            dbusManagedObjects = dbusBluezManager.GetManagedObjects()
            for (path, ifaces) in dbusManagedObjects.items():
                self.dbusBluezAdapter = ifaces.get('org.bluez.Adapter1')
                if self.dbusBluezAdapter != None:
                    self.dbusBluezAdapter = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', path), 'org.bluez.Adapter1')
                    break
            dbusManagedObjects = None
            dbusBluezManager = None
            if self.dbusBluezAdapter != None:
                self.adapter_powered(self.dbusBluezAdapter, 1)
            oe.dbg_log('bluetooth::init_adapter', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::init_adapter', 'ERROR: (' + repr(e) + ')')

    def adapter_powered(self, adapter, state=1):
        try:
            oe.dbg_log('bluetooth::adapter_powered', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::adapter_powered::adapter', repr(adapter), oe.LOGDEBUG)
            oe.dbg_log('bluetooth::adapter_powered::state', repr(state), oe.LOGDEBUG)
            if int(self.adapter_info(self.dbusBluezAdapter, 'Powered')) != state:
                oe.dbg_log('bluetooth::adapter_powered', 'set state (' + str(state) + ')', oe.LOGDEBUG)
                adapter_interface = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', adapter.object_path),
                                                   'org.freedesktop.DBus.Properties')
                adapter_interface.Set('org.bluez.Adapter1', 'Alias', dbus.String(os.environ.get('HOSTNAME', 'libreelec')))
                adapter_interface.Set('org.bluez.Adapter1', 'Powered', dbus.Boolean(state))
                adapter_interface = None
            oe.dbg_log('bluetooth::adapter_powered', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::adapter_powered', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def adapter_info(self, adapter, name):
        try:
            oe.dbg_log('bluetooth::adapter_info', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::adapter_info::adapter', repr(adapter), oe.LOGDEBUG)
            oe.dbg_log('bluetooth::adapter_info::name', repr(name), oe.LOGDEBUG)
            adapter_interface = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', adapter.object_path),
                                               'org.freedesktop.DBus.Properties')
            res = adapter_interface.Get('org.bluez.Adapter1', name)
            adapter_interface = None
            oe.dbg_log('bluetooth::adapter_info', 'exit_function', oe.LOGDEBUG)
            return res
        except Exception as e:
            oe.dbg_log('bluetooth::adapter_info', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def start_discovery(self, listItem=None):
        try:
            oe.dbg_log('bluetooth::start_discovery', 'enter_function', oe.LOGDEBUG)
            self.dbusBluezAdapter.StartDiscovery()
            self.discovering = True
            oe.dbg_log('bluetooth::start_discovery', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::start_discovery', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def stop_discovery(self, listItem=None):
        try:
            oe.dbg_log('bluetooth::stop_discovery', 'enter_function', oe.LOGDEBUG)
            if hasattr(self, 'discovering'):
                del self.discovering
                self.dbusBluezAdapter.StopDiscovery()
            oe.dbg_log('bluetooth::stop_discovery', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::stop_discovery', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    # ###################################################################
    # # Bluetooth Device
    # ###################################################################

    def get_devices(self):
        try:
            oe.dbg_log('bluetooth::get_devices', 'enter_function', oe.LOGDEBUG)
            devices = {}
            dbusBluezManager = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
            managedObjects = dbusBluezManager.GetManagedObjects()
            for (path, interfaces) in managedObjects.items():
                if 'org.bluez.Device1' in interfaces:
                    devices[path] = interfaces['org.bluez.Device1']
            managedObjects = None
            dbusBluezManager = None
            oe.dbg_log('bluetooth::get_devices', 'exit_function', oe.LOGDEBUG)
            return devices
        except Exception as e:
            oe.dbg_log('bluetooth::get_devices::__init__', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def init_device(self, listItem=None):
        try:
            oe.dbg_log('bluetooth::init_device', 'exit_function', oe.LOGDEBUG)
            if listItem is None:
                listItem = oe.winOeMain.getControl(oe.listObject['btlist']).getSelectedItem()
            if listItem is None:
                return
            if listItem.getProperty('Paired') != '1':
                self.pair_device(listItem.getProperty('entry'))
            else:
                self.connect_device(listItem.getProperty('entry'))
            oe.dbg_log('bluetooth::init_device', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::init_device', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def trust_connect_device(self, listItem=None):
        try:

            # ########################################################
            # # This function is used to Pair PS3 Remote without auth
            # ########################################################

            oe.dbg_log('bluetooth::trust_connect_device', 'exit_function', oe.LOGDEBUG)
            if listItem is None:
                listItem = oe.winOeMain.getControl(oe.listObject['btlist']).getSelectedItem()
            if listItem is None:
                return
            self.trust_device(listItem.getProperty('entry'))
            self.connect_device(listItem.getProperty('entry'))
            oe.dbg_log('bluetooth::trust_connect_device', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::trust_connect_device', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def enable_device_standby(self, listItem=None):
        try:
            oe.dbg_log('bluetooth::enable_device_standby', 'exit_function', oe.LOGDEBUG)
            devices = oe.read_setting('bluetooth', 'standby')
            if not devices == None:
                devices = devices.split(',')
            else:
                devices = []
            if not listItem.getProperty('entry') in devices:
                devices.append(listItem.getProperty('entry'))
            oe.write_setting('bluetooth', 'standby', ','.join(devices))
            oe.dbg_log('bluetooth::enable_device_standby', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::enable_device_standby', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def disable_device_standby(self, listItem=None):
        try:
            oe.dbg_log('bluetooth::disable_device_standby', 'exit_function', oe.LOGDEBUG)
            devices = oe.read_setting('bluetooth', 'standby')
            if not devices == None:
                devices = devices.split(',')
            else:
                devices = []
            if listItem.getProperty('entry') in devices:
                devices.remove(listItem.getProperty('entry'))
            oe.write_setting('bluetooth', 'standby', ','.join(devices))
            oe.dbg_log('bluetooth::disable_device_standby', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::disable_device_standby', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def pair_device(self, path):
        try:
            oe.dbg_log('bluetooth::pair_device', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::pair_device::path', repr(path), oe.LOGDEBUG)
            device = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', path), 'org.bluez.Device1')
            device.Pair(reply_handler=self.pair_reply_handler, error_handler=self.dbus_error_handler)
            device = None
            oe.dbg_log('bluetooth::pair_device', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::pair_device', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def pair_reply_handler(self):
        try:
            oe.dbg_log('bluetooth::pair_reply_handler', 'enter_function', oe.LOGDEBUG)
            listItem = oe.winOeMain.getControl(oe.listObject['btlist']).getSelectedItem()
            if listItem is None:
                return
            self.trust_device(listItem.getProperty('entry'))
            self.connect_device(listItem.getProperty('entry'))
            self.menu_connections()
            oe.dbg_log('bluetooth::pair_reply_handler', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::pair_reply_handler', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def trust_device(self, path):
        try:
            oe.dbg_log('bluetooth::trust_device', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::trust_device::path', repr(path), oe.LOGDEBUG)
            prop = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', path), 'org.freedesktop.DBus.Properties')
            prop.Set('org.bluez.Device1', 'Trusted', dbus.Boolean(1))
            prop = None
            oe.dbg_log('bluetooth::trust_device', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::trust_device', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def is_device_connected(self, path):
        try:
            oe.dbg_log('bluetooth::is_device_connected', 'enter_function', oe.LOGDEBUG)
            props = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', path), 'org.freedesktop.DBus.Properties')
            res = props.Get('org.bluez.Device1', 'Connected')
            props = None
            oe.dbg_log('bluetooth::is_device_connected', 'exit_function', oe.LOGDEBUG)
            return res
        except Exception as e:
            oe.dbg_log('bluetooth::is_device_connected', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def connect_device(self, path):
        try:
            oe.dbg_log('bluetooth::connect_device', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::connect_device::path', repr(path), oe.LOGDEBUG)
            device = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', path), 'org.bluez.Device1')
            device.Connect(reply_handler=self.connect_reply_handler, error_handler=self.dbus_error_handler)
            device = None
            oe.dbg_log('bluetooth::connect_device', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::connect_device', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def connect_reply_handler(self):
        try:
            oe.dbg_log('bluetooth::connect_reply_handler', 'enter_function', oe.LOGDEBUG)
            self.menu_connections()
            oe.dbg_log('bluetooth::connect_reply_handler', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::connect_reply_handler', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def disconnect_device_by_path(self, path):
        try:
            oe.dbg_log('bluetooth::disconnect_device_by_path', 'enter_function', oe.LOGDEBUG)
            device = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', path), 'org.bluez.Device1')
            device.Disconnect(reply_handler=self.disconnect_reply_handler, error_handler=self.dbus_error_handler)
            device = None
            oe.dbg_log('bluetooth::disconnect_device_by_path', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::disconnect_device_by_path', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def disconnect_device_by(self, listItem=None):
        try:
            oe.dbg_log('bluetooth::disconnect_device', 'enter_function', oe.LOGDEBUG)
            if listItem is None:
                listItem = oe.winOeMain.getControl(oe.listObject['btlist']).getSelectedItem()
            if listItem is None:
                return
            self.disconnect_device_by_path(listItem.getProperty('entry'))
            oe.dbg_log('bluetooth::disconnect_device', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::disconnect_device', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def disconnect_reply_handler(self):
        try:
            oe.dbg_log('bluetooth::disconnect_reply_handler', 'enter_function', oe.LOGDEBUG)
            self.menu_connections()
            oe.dbg_log('bluetooth::disconnect_reply_handler', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::disconnect_reply_handler', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def remove_device(self, listItem=None):
        try:
            oe.dbg_log('bluetooth::remove_device', 'enter_function', oe.LOGDEBUG)
            if listItem is None:
                listItem = oe.winOeMain.getControl(oe.listObject['btlist']).getSelectedItem()
            if listItem is None:
                return
            oe.dbg_log('bluetooth::remove_device->entry::', listItem.getProperty('entry'), oe.LOGDEBUG)
            path = listItem.getProperty('entry')
            self.dbusBluezAdapter.RemoveDevice(path)
            self.disable_device_standby(listItem)
            self.menu_connections(None)
            oe.dbg_log('bluetooth::remove_device', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::remove_device', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    # ###################################################################
    # # Bluetooth Error Handler
    # ###################################################################

    def dbus_error_handler(self, error):
        try:
            oe.dbg_log('bluetooth::dbus_error_handler', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::dbus_error_handler::error', repr(error), oe.LOGDEBUG)
            err_message = error.get_dbus_message()
            oe.dbg_log('bluetooth::dbus_error_handler::err_message', repr(err_message), oe.LOGDEBUG)
            oe.notify('Bluetooth error', err_message.split('.')[0], 'bt')
            if hasattr(self, 'pinkey_window'):
                self.close_pinkey_window()
            oe.dbg_log('bluetooth::dbus_error_handler', 'ERROR: (' + err_message + ')', oe.LOGERROR)
            oe.dbg_log('bluetooth::dbus_error_handler', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::dbus_error_handler', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    # ###################################################################
    # # Bluetooth GUI
    # ###################################################################

    def clear_list(self):
        try:
            oe.dbg_log('bluetooth::clear_list', 'enter_function', oe.LOGDEBUG)
            remove = [entry for entry in self.listItems]
            for entry in remove:
                del self.listItems[entry]
            oe.dbg_log('bluetooth::clear_list', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::clear_list', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def menu_connections(self, focusItem=None):
        try:
            if not hasattr(oe, 'winOeMain'):
                return 0
            if not oe.winOeMain.visible:
                return 0
            oe.dbg_log('bluetooth::menu_connections', 'enter_function', oe.LOGDEBUG)
            if not 'org.bluez' in oe.dbusSystemBus.list_names():
                oe.winOeMain.getControl(1301).setLabel(oe._(32346))
                self.clear_list()
                oe.winOeMain.getControl(int(oe.listObject['btlist'])).reset()
                oe.dbg_log('bluetooth::menu_connections', 'exit_function (BT Disabled)', oe.LOGDEBUG)
                return
            if self.dbusBluezAdapter == None:
                oe.winOeMain.getControl(1301).setLabel(oe._(32338))
                self.clear_list()
                oe.winOeMain.getControl(int(oe.listObject['btlist'])).reset()
                oe.dbg_log('bluetooth::menu_connections', 'exit_function (No Adapter)', oe.LOGDEBUG)
                return
            if int(self.adapter_info(self.dbusBluezAdapter, 'Powered')) != 1:
                oe.winOeMain.getControl(1301).setLabel(oe._(32338))
                self.clear_list()
                oe.winOeMain.getControl(int(oe.listObject['btlist'])).reset()
                oe.dbg_log('bluetooth::menu_connections', 'exit_function (No Adapter Powered)', oe.LOGDEBUG)
                return
            oe.winOeMain.getControl(1301).setLabel(oe._(32339))
            if not hasattr(self, 'discovery_thread'):
                self.start_discovery()
                self.discovery_thread = discoveryThread(oe)
                self.discovery_thread.start()
            else:
                if self.discovery_thread.stopped:
                    del self.discovery_thread
                    self.start_discovery()
                    self.discovery_thread = discoveryThread(oe)
                    self.discovery_thread.start()
            dictProperties = {}

            # type 1=int, 2=string, 3=array, 4=bool

            properties = {
                0: {
                    'type': 4,
                    'value': 'Paired',
                    },
                1: {
                    'type': 2,
                    'value': 'Adapter',
                    },
                2: {
                    'type': 4,
                    'value': 'Connected',
                    },
                3: {
                    'type': 2,
                    'value': 'Address',
                    },
                5: {
                    'type': 1,
                    'value': 'Class',
                    },
                6: {
                    'type': 4,
                    'value': 'Trusted',
                    },
                7: {
                    'type': 2,
                    'value': 'Icon',
                    },
                }

            rebuildList = 0
            self.dbusDevices = self.get_devices()
            for dbusDevice in self.dbusDevices:
                rebuildList = 1
                oe.winOeMain.getControl(int(oe.listObject['btlist'])).reset()
                self.clear_list()
                break
            for dbusDevice in self.dbusDevices:
                dictProperties = {}
                apName = ''
                dictProperties['entry'] = dbusDevice
                dictProperties['modul'] = self.__class__.__name__
                dictProperties['action'] = 'open_context_menu'
                if 'Name' in self.dbusDevices[dbusDevice]:
                    apName = self.dbusDevices[dbusDevice]['Name']
                if not 'Icon' in self.dbusDevices[dbusDevice]:
                    dictProperties['Icon'] = 'default'
                for prop in properties:
                    name = properties[prop]['value']
                    if name in self.dbusDevices[dbusDevice]:
                        value = self.dbusDevices[dbusDevice][name]
                        if name == 'Connected':
                            if value:
                                dictProperties['ConnectedState'] = oe._(32334)
                            else:
                                dictProperties['ConnectedState'] = oe._(32335)
                        if properties[prop]['type'] == 1:
                            value = str(int(value))
                        if properties[prop]['type'] == 2:
                            value = str(value)
                        if properties[prop]['type'] == 3:
                            value = str(len(value))
                        if properties[prop]['type'] == 4:
                            value = str(int(value))
                        dictProperties[name] = value
                if rebuildList == 1:
                    self.listItems[dbusDevice] = oe.winOeMain.addConfigItem(apName, dictProperties, oe.listObject['btlist'])
                else:
                    if self.listItems[dbusDevice] != None:
                        self.listItems[dbusDevice].setLabel(apName)
                        for dictProperty in dictProperties:
                            self.listItems[dbusDevice].setProperty(dictProperty, dictProperties[dictProperty])
            oe.dbg_log('bluetooth::menu_connections', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::menu_connections', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def open_context_menu(self, listItem):
        try:
            oe.dbg_log('bluetooth::show_options', 'enter_function', oe.LOGDEBUG)
            values = {}
            if listItem is None:
                listItem = oe.winOeMain.getControl(oe.listObject['btlist']).getSelectedItem()
            if listItem.getProperty('Paired') != '1':
                values[1] = {
                    'text': oe._(32145),
                    'action': 'init_device',
                    }
                if listItem.getProperty('Trusted') != '1':
                    values[2] = {
                        'text': oe._(32358),
                        'action': 'trust_connect_device',
                        }
            if listItem.getProperty('Connected') == '1':
                values[3] = {
                    'text': oe._(32143),
                    'action': 'disconnect_device',
                    }
                devices = oe.read_setting('bluetooth', 'standby')
                if not devices == None:
                    devices = devices.split(',')
                else:
                    devices = []
                if listItem.getProperty('entry') in devices:
                    values[4] = {
                        'text': oe._(32389),
                        'action': 'disable_device_standby',
                        }
                else:
                    values[4] = {
                        'text': oe._(32388),
                        'action': 'enable_device_standby',
                        }
            elif listItem.getProperty('Paired') == '1':
                values[1] = {
                    'text': oe._(32144),
                    'action': 'init_device',
                    }
            elif listItem.getProperty('Trusted') == '1':
                values[2] = {
                    'text': oe._(32144),
                    'action': 'trust_connect_device',
                    }
            values[5] = {
                'text': oe._(32141),
                'action': 'remove_device',
                }
            values[6] = {
                'text': oe._(32142),
                'action': 'menu_connections',
                }
            items = []
            actions = []
            for key in list(values.keys()):
                items.append(values[key]['text'])
                actions.append(values[key]['action'])
            select_window = xbmcgui.Dialog()
            title = oe._(32012)
            result = select_window.select(title, items)
            if result >= 0:
                getattr(self, actions[result])(listItem)
            oe.dbg_log('bluetooth::show_options', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::show_options', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def open_pinkey_window(self, runtime=60, title=32343):
        try:
            oe.dbg_log('bluetooth::open_pinkey_window', 'enter_function', oe.LOGDEBUG)
            self.pinkey_window = oeWindows.pinkeyWindow('service-LibreELEC-Settings-getPasskey.xml', oe.__cwd__, 'Default')
            self.pinkey_window.show()
            self.pinkey_window.set_title(oe._(title))
            self.pinkey_timer = pinkeyTimer(self, runtime)
            self.pinkey_timer.start()
            oe.dbg_log('bluetooth::open_pinkey_window', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::open_pinkey_window', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def close_pinkey_window(self):
        try:
            oe.dbg_log('bluetooth::close_pinkey_window', 'enter_function', oe.LOGDEBUG)
            if hasattr(self, 'pinkey_timer'):
                self.pinkey_timer.stop()
                self.pinkey_timer = None
                del self.pinkey_timer
            if hasattr(self, 'pinkey_window'):
                self.pinkey_window.close()
                self.pinkey_window = None
                del self.pinkey_window
            oe.dbg_log('bluetooth::close_pinkey_window', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::close_pinkey_window', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def standby_devices(self):
        try:
            oe.dbg_log('bluetooth::standby_devices', 'enter_function', oe.LOGDEBUG)
            if self.dbusBluezAdapter != None:
                devices = oe.read_setting('bluetooth', 'standby')
                if not devices == None:
                    oe.input_request = True
                    for device in devices.split(','):
                        if self.is_device_connected(device):
                            self.disconnect_device_by_path(device)
                    oe.input_request = False
            oe.dbg_log('bluetooth::standby_devices', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::standby_devices', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    # ###################################################################
    # # Bluetooth monitor and agent subclass
    # ###################################################################

    class monitor:

        def __init__(self, oeMain, parent):
            try:
                oeMain.dbg_log('bluetooth::monitor::__init__', 'enter_function', oeMain.LOGDEBUG)
                self.signal_receivers = []
                self.NameOwnerWatch = None
                self.ObexNameOwnerWatch = None
                self.btAgentPath = '/LibreELEC/bt_agent'
                self.obAgentPath = '/LibreELEC/ob_agent'
                self.parent = parent
                oe.dbg_log('bluetooth::monitor::__init__', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::__init__', 'ERROR: (' + repr(e) + ')')

        def add_signal_receivers(self):
            try:
                oe.dbg_log('bluetooth::monitor::add_signal_receivers', 'enter_function', oe.LOGDEBUG)
                self.signal_receivers.append(oe.dbusSystemBus.add_signal_receiver(self.InterfacesAdded, bus_name='org.bluez',
                                             dbus_interface='org.freedesktop.DBus.ObjectManager', signal_name='InterfacesAdded'))
                self.signal_receivers.append(oe.dbusSystemBus.add_signal_receiver(self.InterfacesRemoved, bus_name='org.bluez',
                                             dbus_interface='org.freedesktop.DBus.ObjectManager', signal_name='InterfacesRemoved'))
                self.signal_receivers.append(oe.dbusSystemBus.add_signal_receiver(self.AdapterChanged,
                                             dbus_interface='org.freedesktop.DBus.Properties', signal_name='PropertiesChanged',
                                             arg0='org.bluez.Adapter1', path_keyword='path'))
                self.signal_receivers.append(oe.dbusSystemBus.add_signal_receiver(self.PropertiesChanged,
                                             dbus_interface='org.freedesktop.DBus.Properties', signal_name='PropertiesChanged',
                                             arg0='org.bluez.Device1', path_keyword='path'))
                self.signal_receivers.append(oe.dbusSystemBus.add_signal_receiver(self.TransferChanged,
                                             dbus_interface='org.freedesktop.DBus.Properties', arg0='org.bluez.obex.Transfer1'))
                self.NameOwnerWatch = oe.dbusSystemBus.watch_name_owner('org.bluez', self.bluezNameOwnerChanged)
                self.ObexNameOwnerWatch = oe.dbusSystemBus.watch_name_owner('org.bluez.obex', self.bluezObexNameOwnerChanged)
                oe.dbg_log('bluetooth::monitor::add_signal_receivers', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::add_signal_receivers', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def remove_signal_receivers(self):
            try:
                oe.dbg_log('bluetooth::monitor::remove_signal_receivers', 'enter_function', oe.LOGDEBUG)
                for signal_receiver in self.signal_receivers:
                    signal_receiver.remove()
                    signal_receiver = None

                # Remove will cause xbmc freeze
                # bluez bug ?
                # does this work now ? 2014-01-19 / LUFI

                self.ObexNameOwnerWatch.cancel()
                self.ObexNameOwnerWatch = None
                self.NameOwnerWatch.cancel()
                self.NameOwnerWatch = None
                if hasattr(self, 'obAgent'):
                    self.remove_obex_agent()
                if hasattr(self, 'btAgent'):
                    self.remove_agent()
                oe.dbg_log('bluetooth::monitor::remove_signal_receivers', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::remove_signal_receivers', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def bluezNameOwnerChanged(self, proxy):
            try:
                oe.dbg_log('bluetooth::monitorLoop::bluezNameOwnerChanged', 'enter_function', oe.LOGDEBUG)
                if proxy:
                    self.initialize_agent()
                else:
                    self.remove_agent()
                oe.dbg_log('bluetooth::monitor::bluezNameOwnerChanged', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::bluezNameOwnerChanged', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def initialize_agent(self):
            try:
                oe.dbg_log('bluetooth::monitor::initialize_agent', 'enter_function', oe.LOGDEBUG)
                self.btAgent = bluetoothAgent(oe.dbusSystemBus, self.btAgentPath)
                self.btAgent.parent = self.parent
                dbusBluezManager = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', '/org/bluez'), 'org.bluez.AgentManager1')
                dbusBluezManager.RegisterAgent(self.btAgentPath, 'KeyboardDisplay')
                dbusBluezManager.RequestDefaultAgent(self.btAgentPath)
                dbusBluezManager = None
                oe.dbg_log('bluetooth::monitor::initialize_agent', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::initialize_agent', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def remove_agent(self):
            try:
                oe.dbg_log('bluetooth::monitor::remove_agent', 'enter_function', oe.LOGDEBUG)
                if hasattr(self, 'btAgent'):
                    self.btAgent.remove_from_connection(oe.dbusSystemBus, self.btAgentPath)
                    try:
                        dbusBluezManager = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', '/org/bluez'), 'org.bluez.AgentManager1')
                        dbusBluezManager.UnregisterAgent(self.btAgentPath)
                        dbusBluezManager = None
                    except:
                        dbusBluezManager = None
                        pass
                    del self.btAgent
                oe.dbg_log('bluetooth::monitor::remove_agent', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::remove_agent', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def bluezObexNameOwnerChanged(self, proxy):
            try:
                oe.dbg_log('bluetooth::monitorLoop::bluezObexNameOwnerChanged', 'enter_function', oe.LOGDEBUG)
                if proxy:
                    self.initialize_obex_agent()
                else:
                    self.remove_obex_agent()
                oe.dbg_log('bluetooth::monitor::bluezObexNameOwnerChanged', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::bluezObexNameOwnerChanged', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def initialize_obex_agent(self):
            try:
                oe.dbg_log('bluetooth::monitor::initialize_obex_agent', 'enter_function', oe.LOGDEBUG)
                self.obAgent = obexAgent(oe.dbusSystemBus, self.obAgentPath)
                self.obAgent.parent = self.parent
                dbusBluezObexManager = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez.obex', '/org/bluez/obex'),
                                                      'org.bluez.obex.AgentManager1')
                dbusBluezObexManager.RegisterAgent(self.obAgentPath)
                dbusBluezObexManager = None
                oe.dbg_log('bluetooth::monitor::initialize_obex_agent', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::initialize_obex_agent', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def remove_obex_agent(self):
            try:
                oe.dbg_log('bluetooth::monitor::remove_obex_agent', 'enter_function', oe.LOGDEBUG)
                if hasattr(self, 'obAgent'):
                    self.obAgent.remove_from_connection(oe.dbusSystemBus, self.obAgentPath)
                    try:
                        dbusBluezObexManager = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez.obex', '/org/bluez/obex'),
                                                              'org.bluez.obex.AgentManager1')
                        dbusBluezObexManager.UnregisterAgent(self.obAgentPath)
                        dbusBluezObexManager = None
                    except:
                        dbusBluezObexManager = None
                        pass
                    del self.obAgent
                oe.dbg_log('bluetooth::monitor::remove_obex_agent', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::remove_obex_agent', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def InterfacesAdded(self, path, interfaces):
            try:
                oe.dbg_log('bluetooth::monitor::InterfacesAdded', 'enter_function', oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::InterfacesAdded::path', repr(path), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::InterfacesAdded::interfaces', repr(interfaces), oe.LOGDEBUG)
                if 'org.bluez.Adapter1' in interfaces:
                    self.parent.dbusBluezAdapter = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez', path), 'org.bluez.Adapter1')
                    self.parent.adapter_powered(self.parent.dbusBluezAdapter, 1)
                if hasattr(self.parent, 'pinkey_window'):
                    if path == self.parent.pinkey_window.device:
                        self.parent.close_pinkey_window()
                if self.parent.visible:
                    self.parent.menu_connections()
                oe.dbg_log('bluetooth::monitor::InterfacesAdded', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::InterfacesAdded', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def InterfacesRemoved(self, path, interfaces):
            try:
                oe.dbg_log('bluetooth::monitor::InterfacesRemoved', 'enter_function', oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::InterfacesRemoved::path', repr(path), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::InterfacesRemoved::interfaces', repr(interfaces), oe.LOGDEBUG)
                if 'org.bluez.Adapter1' in interfaces:
                    self.parent.dbusBluezAdapter = None
                if self.parent.visible and not hasattr(self.parent, 'discovery_thread'):
                    self.parent.menu_connections()
                oe.dbg_log('bluetooth::monitor::InterfacesRemoved', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::InterfacesRemoved', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def AdapterChanged(self, interface, changed, invalidated, path):
            try:
                oe.dbg_log('bluetooth::monitor::AdapterChanged', 'enter_function', oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::AdapterChanged::interface', repr(interface), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::AdapterChanged::changed', repr(changed), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::AdapterChanged::invalidated', repr(invalidated), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::AdapterChanged::path', repr(path), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::AdapterChanged', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::AdapterChanged', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def PropertiesChanged(self, interface, changed, invalidated, path):
            try:
                oe.dbg_log('bluetooth::monitor::PropertiesChanged', 'enter_function', oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::PropertiesChanged::interface', repr(interface), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::PropertiesChanged::changed', repr(changed), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::PropertiesChanged::invalidated', repr(invalidated), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::PropertiesChanged::path', repr(path), oe.LOGDEBUG)
                if self.parent.visible:
                    properties = [
                        'Paired',
                        'Adapter',
                        'Connected',
                        'Address',
                        'Class',
                        'Trusted',
                        'Icon',
                        ]
                    if path in self.parent.listItems:
                        for prop in changed:
                            if prop in properties:
                                self.parent.listItems[path].setProperty(str(prop), str(changed[prop]))
                    else:
                        self.parent.menu_connections()
                oe.dbg_log('bluetooth::monitor::PropertiesChanged', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::PropertiesChanged', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

        def TransferChanged(self, path, interface, dummy):
            try:
                oe.dbg_log('bluetooth::monitor::TransferChanged', 'enter_function', oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::TransferChanged::path', repr(path), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::TransferChanged::interface', repr(interface), oe.LOGDEBUG)
                oe.dbg_log('bluetooth::monitor::TransferChanged::dummy', repr(dummy), oe.LOGDEBUG)
                if 'Status' in interface:
                    if interface['Status'] == 'active':
                        self.parent.download_start = time.time()
                        self.parent.download = xbmcgui.DialogProgress()
                        self.parent.download.create('Bluetooth Filetransfer', f'{oe._(32181)}: {self.parent.download_file}')
                    else:
                        if hasattr(self.parent, 'download'):
                            self.parent.download.close()
                            del self.parent.download
                            del self.parent.download_path
                            del self.parent.download_size
                            del self.parent.download_start
                        if interface['Status'] == 'complete':
                            xbmcDialog = xbmcgui.Dialog()
                            answer = xbmcDialog.yesno('Bluetooth Filetransfer', oe._(32383))
                            if answer == 1:
                                fil = f'{oe.DOWNLOAD_DIR}/{self.parent.download_file}'
                                if 'image' in self.parent.download_type:
                                    xbmc.executebuiltin(f'showpicture({fil})')
                                else:
                                    xbmc.Player().play(fil)
                            del self.parent.download_type
                            del self.parent.download_file
                if hasattr(self.parent, 'download'):
                    if 'Transferred' in interface:
                        transferred = int(interface['Transferred'] / 1024)
                        speed = transferred / (time.time() - self.parent.download_start)
                        percent = int(round(100 / self.parent.download_size * (interface['Transferred'] / 1024), 0))
                        message = f'{oe._(32181)}: {self.parent.download_file}\n{oe._(32382)}: {speed} KB/s'
                        self.parent.download.update(percent, message)
                    if self.parent.download.iscanceled():
                        obj = oe.dbusSystemBus.get_object('org.bluez.obex', self.parent.download_path)
                        itf = dbus.Interface(obj, 'org.bluez.obex.Transfer1')
                        itf.Cancel()
                        obj = None
                        itf = None
                oe.dbg_log('bluetooth::monitor::TransferChanged', 'exit_function', oe.LOGDEBUG)
            except Exception as e:
                oe.dbg_log('bluetooth::monitor::TransferChanged', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)


####################################################################
## Bluetooth Agent class
####################################################################

class Rejected(dbus.DBusException):

    _dbus_error_name = 'org.bluez.Error.Rejected'


class bluetoothAgent(dbus.service.Object):

    def busy(self):
        oe.input_request = False

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Release(self):
        try:
            oe.dbg_log('bluetooth::btAgent::Release', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::Release', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::btAgent::Release', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid):
        try:
            oe.dbg_log('bluetooth::btAgent::AuthorizeService', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::AuthorizeService::device=', repr(device), oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::AuthorizeService::uuid=', repr(uuid), oe.LOGDEBUG)
            oe.input_request = True
            xbmcDialog = xbmcgui.Dialog()
            answer = xbmcDialog.yesno('Bluetooth', f'Authorize service {uuid}?')
            oe.dbg_log('bluetooth::btAgent::AuthorizeService::answer=', repr(answer), oe.LOGDEBUG)
            self.busy()
            oe.dbg_log('bluetooth::btAgent::AuthorizeService', 'exit_function', oe.LOGDEBUG)
            if answer == 1:
                oe.dictModules['bluetooth'].trust_device(device)
                return
            raise Rejected('Connection rejected!')
        except Exception as e:
            oe.dbg_log('bluetooth::btAgent::AuthorizeService', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='s')
    def RequestPinCode(self, device):
        try:
            oe.dbg_log('bluetooth::btAgent::RequestPinCode', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::RequestPinCode::device=', repr(device), oe.LOGDEBUG)
            oe.input_request = True
            xbmcKeyboard = xbmc.Keyboard('', 'Enter PIN code')
            xbmcKeyboard.doModal()
            pincode = xbmcKeyboard.getText()
            self.busy()
            oe.dbg_log('bluetooth::btAgent::RequestPinCode', 'return->' + pincode, oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::RequestPinCode', 'exit_function', oe.LOGDEBUG)
            return dbus.String(pincode)
        except Exception as e:
            oe.dbg_log('bluetooth::btAgent::RequestPinCode', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='u')
    def RequestPasskey(self, device):
        try:
            oe.dbg_log('bluetooth::btAgent::RequestPasskey', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::RequestPasskey::device=', repr(device), oe.LOGDEBUG)
            oe.input_request = True
            xbmcDialog = xbmcgui.Dialog()
            passkey = int(xbmcDialog.numeric(0, 'Enter passkey (number in 0-999999)', '0'))
            oe.dbg_log('bluetooth::btAgent::RequestPasskey::passkey=', repr(passkey), oe.LOGDEBUG)
            self.busy()
            oe.dbg_log('bluetooth::btAgent::RequestPasskey', 'exit_function', oe.LOGDEBUG)
            return dbus.UInt32(passkey)
        except Exception as e:
            oe.dbg_log('bluetooth::btAgent::RequestPasskey', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.Agent1', in_signature='ouq', out_signature='')
    def DisplayPasskey(self, device, passkey, entered):
        try:
            oe.dbg_log('bluetooth::btAgent::DisplayPasskey', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::DisplayPasskey::device=', repr(device), oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::DisplayPasskey::passkey=', repr(passkey), oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::DisplayPasskey::entered=', repr(entered), oe.LOGDEBUG)
            if not hasattr(self.parent, 'pinkey_window'):
                self.parent.open_pinkey_window()
                self.parent.pinkey_window.device = device
                self.parent.pinkey_window.set_label1('Passkey: %06u' % (passkey))
            oe.dbg_log('bluetooth::btAgent::DisplayPasskey', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::btAgent::DisplayPasskey', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.Agent1', in_signature='os', out_signature='')
    def DisplayPinCode(self, device, pincode):
        try:
            oe.dbg_log('bluetooth::btAgent::DisplayPinCode', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::DisplayPinCode::device=', repr(device), oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::DisplayPinCode::pincode=', repr(pincode), oe.LOGDEBUG)
            if hasattr(self.parent, 'pinkey_window'):
                self.parent.close_pinkey_window()
            self.parent.open_pinkey_window(runtime=30)
            self.parent.pinkey_window.device = device
            self.parent.pinkey_window.set_label1(f'PIN code: {pincode}')
            oe.dbg_log('bluetooth::btAgent::DisplayPinCode', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::btAgent::DisplayPinCode', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.Agent1', in_signature='ou', out_signature='')
    def RequestConfirmation(self, device, passkey):
        try:
            oe.dbg_log('bluetooth::btAgent::RequestConfirmation', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::RequestConfirmation::device=', repr(device), oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::RequestConfirmation::passkey=', repr(passkey), oe.LOGDEBUG)
            oe.input_request = True
            xbmcDialog = xbmcgui.Dialog()
            answer = xbmcDialog.yesno('Bluetooth', f'Confirm passkey {passkey}')
            oe.dbg_log('bluetooth::btAgent::RequestConfirmation::answer=', repr(answer), oe.LOGDEBUG)
            self.busy()
            oe.dbg_log('bluetooth::btAgent::RequestConfirmation', 'exit_function', oe.LOGDEBUG)
            if answer == 1:
                oe.dictModules['bluetooth'].trust_device(device)
                return
            raise Rejected("Passkey doesn't match")
        except Exception as e:
            oe.dbg_log('bluetooth::btAgent::RequestConfirmation', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.Agent1', in_signature='o', out_signature='')
    def RequestAuthorization(self, device):
        try:
            oe.dbg_log('bluetooth::btAgent::RequestAuthorization', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::btAgent::RequestAuthorization::device=', repr(device), oe.LOGDEBUG)
            oe.input_request = True
            xbmcDialog = xbmcgui.Dialog()
            answer = xbmcDialog.yesno('Bluetooth', 'Accept pairing?')
            oe.dbg_log('bluetooth::btAgent::RequestAuthorization::answer=', repr(answer), oe.LOGDEBUG)
            self.busy()
            oe.dbg_log('bluetooth::btAgent::RequestAuthorization', 'exit_function', oe.LOGDEBUG)
            if answer == 1:
                oe.dictModules['bluetooth'].trust_device(device)
                return
            raise Rejected('Pairing rejected')
        except Exception as e:
            oe.dbg_log('bluetooth::btAgent::RequestAuthorization', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.Agent1', in_signature='', out_signature='')
    def Cancel(self):
        try:
            oe.dbg_log('bluetooth::btAgent::Cancel', 'enter_function', oe.LOGDEBUG)
            if hasattr(self.parent, 'pinkey_window'):
                self.parent.close_pinkey_window()
            oe.dbg_log('bluetooth::btAgent::Cancel', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::btAgent::Cancel', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)


####################################################################
## Obex Agent class
####################################################################

class obexAgent(dbus.service.Object):

    def busy(self):
        oe.input_request = False

    @dbus.service.method('org.bluez.obex.Agent1', in_signature='', out_signature='')
    def Release(self):
        try:
            oe.dbg_log('bluetooth::obexAgent::Release', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::obexAgent::Release', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::obexAgent::Release', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.obex.Agent1', in_signature='o', out_signature='s')
    def AuthorizePush(self, path):
        try:
            oe.dbg_log('bluetooth::obexAgent::AuthorizePush', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::obexAgent::AuthorizePush::path=', repr(path), oe.LOGDEBUG)
            transfer = dbus.Interface(oe.dbusSystemBus.get_object('org.bluez.obex', path), 'org.freedesktop.DBus.Properties')
            properties = transfer.GetAll('org.bluez.obex.Transfer1')
            oe.input_request = True
            xbmcDialog = xbmcgui.Dialog()
            answer = xbmcDialog.yesno('Bluetooth', f"{oe._(32381)}\n\n{properties['Name']}")
            oe.dbg_log('bluetooth::obexAgent::AuthorizePush::answer=', repr(answer), oe.LOGDEBUG)
            self.busy()
            if answer != 1:
                properties = None
                transfer = None
                raise dbus.DBusException('org.bluez.obex.Error.Rejected: Not Authorized')
            self.parent.download_path = path
            self.parent.download_file = properties['Name']
            self.parent.download_size = properties['Size'] / 1024
            if 'Type' in properties:
                self.parent.download_type = properties['Type']
            else:
                self.parent.download_type = None
            res = properties['Name']
            properties = None
            transfer = None
            oe.dbg_log('bluetooth::obexAgent::AuthorizePush', 'exit_function', oe.LOGDEBUG)
            return res
        except Exception as e:
            oe.dbg_log('bluetooth::obexAgent::AuthorizePush', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    @dbus.service.method('org.bluez.obex.Agent1', in_signature='', out_signature='')
    def Cancel(self):
        try:
            oe.dbg_log('bluetooth::obexAgent::Cancel', 'enter_function', oe.LOGDEBUG)
            oe.dbg_log('bluetooth::obexAgent::Cancel', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::obexAgent::Cancel', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)


class discoveryThread(threading.Thread):

    def __init__(self, oeMain):
        try:
            oeMain.dbg_log('bluetooth::discoveryThread::__init__', 'enter_function', oeMain.LOGDEBUG)
            self.last_run = 0
            self.stopped = False
            self.main_menu = oe.winOeMain.getControl(oe.winOeMain.guiMenList)
            threading.Thread.__init__(self)
            oe.dbg_log('bluetooth::discoveryThread::__init__', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::discoveryThread::__init__', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def stop(self):
        self.stopped = True
        oe.dictModules['bluetooth'].stop_discovery()

    def run(self):
        try:
            oe.dbg_log('bluetooth::discoveryThread::run', 'enter_function', oe.LOGDEBUG)
            while not self.stopped and not oe.xbmcm.abortRequested():
                current_time = time.time()
                if current_time > self.last_run + 5:
                    if self.main_menu.getSelectedItem().getProperty('modul') != 'bluetooth' or not hasattr(oe.dictModules['bluetooth'], 'discovery_thread'):
                        oe.dictModules['bluetooth'].menu_connections(None)
                    self.last_run = current_time
                if self.main_menu.getSelectedItem().getProperty('modul') != 'bluetooth':
                    self.stop()
                oe.xbmcm.waitForAbort(1)
            oe.dbg_log('bluetooth::discoveryThread::run', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::discoveryThread::run', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)


class pinkeyTimer(threading.Thread):

    def __init__(self, parent, runtime=60):
        try:
            parent.oe.dbg_log('bluetooth::pinkeyTimer::__init__', 'enter_function', parent.oe.LOGDEBUG)
            self.parent = parent
            self.start_time = time.time()
            self.last_run = time.time()
            self.stopped = False
            self.runtime = runtime
            threading.Thread.__init__(self)
            oe.dbg_log('bluetooth::pinkeyTimer::__init__', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::pinkeyTimer::__init__', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)

    def stop(self):
        self.stopped = True

    def run(self):
        try:
            oe.dbg_log('bluetooth::pinkeyTimer::run', 'enter_function', oe.LOGDEBUG)
            self.endtime = self.start_time + self.runtime
            while not self.stopped and not oe.xbmcm.abortRequested():
                current_time = time.time()
                percent = round(100 / self.runtime * (self.endtime - current_time), 0)
                self.parent.pinkey_window.getControl(1704).setPercent(percent)
                if current_time >= self.endtime:
                    self.stopped = True
                    self.parent.close_pinkey_window()
                else:
                    oe.xbmcm.waitForAbort(1)
            oe.dbg_log('bluetooth::pinkeyTimer::run', 'exit_function', oe.LOGDEBUG)
        except Exception as e:
            oe.dbg_log('bluetooth::pinkeyTimer::run', 'ERROR: (' + repr(e) + ')', oe.LOGERROR)
