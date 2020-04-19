from wifipumpkin3.core.common.terminal import ConsoleUI
from wifipumpkin3.core.controllers.defaultcontroller import *
from wifipumpkin3.core.config.globalimport import *

from wifipumpkin3.modules import *
from wifipumpkin3.modules import module_list, all_modules

# This file is part of the wifipumpkin3 Open Source Project.
# wifipumpkin3 is licensed under the Apache 2.0.

# Copyright 2020 P0cL4bs Team - Marcos Bomfim (mh4x0f)

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

approot = QtCore.QCoreApplication.instance()


class PumpkinShell(Qt.QObject, ConsoleUI):
    """
    :parameters
        options : parse_args
    """

    instances = []
    _all_modules = None

    @classmethod
    def getInstance(cls):
        return cls.instances[0]

    @property
    def getDefault(self):
        """ return DefaultWidget instance for load controllers """
        return DefaultController.getInstance()

    def __init__(self, parse_args):
        self.__class__.instances.append(weakref.proxy(self))
        self.parse_args = parse_args
        # load session parser
        self.currentSessionID = self.parse_args.session
        if not self.currentSessionID:
            self.currentSessionID = Refactor.generate_session_id()
        print(
            display_messages(
                "Session id: {} ".format(
                    setcolor(self.currentSessionID, color="red", underline=True)
                ),
                info=True,
            )
        )

        super(PumpkinShell, self).__init__(parse_args=self.parse_args)

    def initialize_core(self):
        """ this method is called in __init__ """
        # set current session unique id
        self.conf.set("accesspoint", "current_session", self.currentSessionID)
        if self.parse_args.interface:
            self.conf.set("accesspoint", "interface", self.parse_args.interface)

        self.all_modules = module_list

        # intialize the LoggerManager 
        #TODO: this change solve IndexError: list index out of range
        # but not a definitive solution 
        self.logger_manager = LoggerManager(self)
        self.coreui = DefaultController(self)

        # print(self.coreui.Plugins)
        self.proxy_controller = self.coreui.getController("proxy_controller")
        self.mitm_controller = self.coreui.getController("mitm_controller")
        self.wireless_controller = self.coreui.getController("wireless_controller")
        self.dhcp_controller = self.coreui.getController("dhcp_controller")
        self.dns_controller = self.coreui.getController("dns_controller")
        self.tableUI = self.coreui.getController("ui_controller")

        self.parser_list_func = {
            # parser_set_proxy is default extend class
            "parser_set_proxy": self.proxy_controller.pumpkinproxy,
            "parser_set_plugin": self.mitm_controller.sniffkin3,
            "parser_set_mode": self.wireless_controller.Settings,
            "parser_set_security": self.wireless_controller.Settings,
        }
        self.parser_autcomplete_func = {}

        # hook function (plugins and proxys)
        self.intialize_hook_func(self.proxy_controller)
        self.intialize_hook_func(self.mitm_controller)

        # register autocomplete set security command
        self.parser_autcomplete_func[
            "parser_set_security"
        ] = self.wireless_controller.Settings.getCommands

        self.commands = {
            "interface": "interface",
            "ssid": "ssid",
            "bssid": "bssid",
            "channel": "channel",
            "proxy": None,  # only for settings proxy
            "plugin": None,  # only for settings plugin
            "mode": None,  # only for settings mdoe
            "security": "enable_security",
        }

        # get all command plugins and proxys
        for ctr_name, ctr_instance in self.coreui.getController(None).items():
            if hasattr(ctr_instance, "getInfo"):
                for plugin_name, plugins_info in ctr_instance.getInfo().items():
                    self.commands[plugin_name] = ""

        self.Apthreads = {"RogueAP": []}

    @property
    def all_modules(self):
        return self._all_modules

    @all_modules.setter
    def all_modules(self, module_list):
        m_avaliable = {}
        for name, module in module_list().items():
            if hasattr(module, "ModPump"):
                m_avaliable[name] = module
        self._all_modules = m_avaliable

    def intialize_hook_func(self, controller):
        # load all parser funct and plguins command CLI for plugins
        for plugin_name in controller.getInfo():
            self.parser_list_func["parser_set_" + plugin_name] = getattr(
                controller, plugin_name
            )
            if getattr(controller, plugin_name).getPlugins != None:
                self.parser_autcomplete_func["parser_set_" + plugin_name] = getattr(
                    controller, plugin_name
                ).getPlugins

    def do_show(self, args):
        """ show available modules"""
        headers_table, output_table = ["Name", "Description"], []
        print(display_messages("Available Modules:", info=True, sublime=True))
        for name, module in self.all_modules.items():
            output_table.append([name, getattr(module, "ModPump").__doc__])
        return display_tabulate(headers_table, output_table)

    def do_mode(self, args):
        """ all wireless mode available """
        headers_table, output_table = ["ID", "Activate", "Description"], []
        print(display_messages("Available Wireless Mode:", info=True, sublime=True))
        for id_mode, info in self.wireless_controller.getInfo().items():
            output_table.append(
                [
                    id_mode,
                    setcolor("True", color="green")
                    if info["Checked"]
                    else setcolor("False", color="red"),
                    info["Name"],
                ]
            )
        return display_tabulate(headers_table, output_table)

    def do_use(self, args):
        """ select module for modules"""
        if args in self.all_modules.keys():
            module = module_list()[args].ModPump(self.parse_args, globals())
            module.cmdloop()

    def getAccessPointStatus(self, status):
        self.ui_table.startThreads()
        self.ui_monitor.startThreads()

    def do_start(self, args):
        """ start access point """

        self.interfaces = Linux.get_interfaces()
        if not self.conf.get(
            "accesspoint", self.commands["interface"]
        ) in self.interfaces.get("all"):
            print(display_messages("The interface not found! ", error=True))
            sys.exit(1)

        if self.wireless_controller.Start() != None:
            return
        for ctr_name, ctr_instance in self.coreui.getController(None).items():
            if ctr_name != "wireless_controller":
                ctr_instance.Start()

        self.Apthreads["RogueAP"].insert(0, self.wireless_controller.ActiveReactor)
        self.Apthreads["RogueAP"].insert(1, self.dhcp_controller.ActiveReactor)
        self.Apthreads["RogueAP"].insert(2, self.dns_controller.ActiveReactor)
        self.Apthreads["RogueAP"].extend(self.proxy_controller.ActiveReactor)
        self.Apthreads["RogueAP"].extend(self.mitm_controller.ActiveReactor)

        for thread in self.Apthreads["RogueAP"]:
            if thread is not None:
                QtCore.QThread.sleep(1)
                if not (isinstance(thread, list)):
                    thread.start()

    def addThreads(self, service):
        self.threadsAP.append(service)

    def killThreads(self):
        if not len(self.Apthreads["RogueAP"]) > 0:
            return
        self.conf.set("accesspoint", "status_ap", False)
        # get all command plugins and proxys
        for ctr_name, ctr_instance in self.coreui.getController(None).items():
            ctr_instance.Stop()

        for thread in self.Apthreads["RogueAP"]:
            if thread is not None:
                if isinstance(thread, list):
                    for sub_thread in thread:
                        if sub_thread != None:
                            sub_thread.stop()
                    continue
                thread.stop()

        for line in self.wireless_controller.Activated.getSettings().SettingsAP["kill"]:
            exec_bash(line)
        self.Apthreads["RogueAP"] = []

    def countThreads(self):
        return len(self.threadsAP["RougeAP"])

    def do_ignore(self, args):
        """ the message logger will be ignored """
        logger = self.logger_manager.get(args)
        if logger != None:
            return logger.setIgnore(True)
        print(display_messages("Logger class not found.", error=True))

    def do_restore(self, args):
        """ the message logger will be restored """
        logger = self.logger_manager.get(args)
        if logger != None:
            return logger.setIgnore(False)
        print(display_messages("Logger class not found.", error=True))

    def do_clients(self, args):
        """ show all clients connected on AP """
        self.tableUI.ui_table_mod.start()

    def do_stop(self, args):
        """ stop access point """
        self.killThreads()

    def do_jobs(self, args):
        """ show all threads/processes in background """
        if len(self.Apthreads["RogueAP"]) > 0:
            process_background = {}
            headers_table, output_table = ["ID", "PID"], []
            for ctr_name, ctr_instance in self.coreui.getController(None).items():
                if hasattr(ctr_instance, "getReactorInfo"):
                    process_background.update(ctr_instance.getReactorInfo())

            for id_controller, info in process_background.items():
                output_table.append([info["ID"], info["PID"]])

            print(
                display_messages(
                    "Background processes/threads:", info=True, sublime=True
                )
            )
            return display_tabulate(headers_table, output_table)
        print(display_messages("the AccessPoint is not running", info=True))

    def do_info(self, args):
        """ get info from the module/plugin"""
        try:
            command = args.split()[0]
            plugins = self.mitm_controller.getInfo().get(command)
            proxys = self.proxy_controller.getInfo().get(command)
            if plugins or proxys:
                print(
                    display_messages(
                        "Information {}: ".format(command), info=True, sublime=True
                    )
                )
            if plugins:
                for name, info in plugins.items():
                    if name != "Config":
                        print(
                            " {} : {}".format(
                                setcolor(name, color="blue"),
                                setcolor(info, color="yellow"),
                            )
                        )
            if proxys:
                for name, info in proxys.items():
                    if name != "Config":
                        print(
                            " {} : {}".format(
                                setcolor(name, color="blue"),
                                setcolor(info, color="yellow"),
                            )
                        )

                commands = proxys["Config"].get_all_childname("plugins")
                list_commands = []
                headers_table, output_table = ["Plugin", "Value"], []
                # search plugin of proxy has string "set_"
                for command in commands:
                    for sub_plugin in proxys["Config"].get_all_childname(
                        "set_{}".format(command)
                    ):
                        output_table.append(
                            [
                                setcolor(command, color="blue"),
                                proxys["Config"].get(
                                    "set_{}".format(command), sub_plugin
                                ),
                            ]
                        )
                if output_table != []:
                    print(display_messages("Plugins:", info=True, sublime=True))
                    return display_tabulate(headers_table, output_table)

            if plugins or proxys:
                print("\n")

        except IndexError:
            pass

    def do_ap(self, args):
        """ show all variable and status for settings AP """
        headers_table, output_table = (
            ["BSSID", "SSID", "Channel", "Iface", "StatusAP", "Security"],
            [],
        )
        print(display_messages("Settings AccessPoint:", info=True, sublime=True))
        status_ap = self.conf.get("accesspoint", "status_ap", format=bool)
        output_table.append(
            [
                self.conf.get("accesspoint", self.commands["bssid"]),
                self.conf.get("accesspoint", self.commands["ssid"]),
                self.conf.get("accesspoint", self.commands["channel"]),
                self.conf.get("accesspoint", self.commands["interface"]),
                setcolor("is Running", color="green")
                if status_ap
                else setcolor("not Running", color="red"),
                self.conf.get("accesspoint", self.commands["security"]),
            ]
        )
        display_tabulate(headers_table, output_table)
        enable_security = self.conf.get(
            "accesspoint", self.commands["security"], format=bool
        )

        if enable_security:
            headers_sec, output_sec = (
                ["wpa_algorithms", "wpa_sharedkey", "wpa_type"],
                [],
            )
            output_sec.append(
                [
                    self.conf.get("accesspoint", "wpa_algorithms"),
                    self.conf.get("accesspoint", "wpa_sharedkey"),
                    self.conf.get("accesspoint", "wpa_type"),
                ]
            )
            print(display_messages("Settings Security:", info=True, sublime=True))
            display_tabulate(headers_sec, output_sec)
            self.show_help_command("help_security_command")

    def do_set(self, args):
        """ set variable proxy,plugin and access point """
        try:
            command, value = args.split()[0], args.split()[1]
        except IndexError:
            return print(
                display_messages("unknown sintax : {} ".format(args), error=True)
            )

        if command in list(self.commands.keys()) and self.commands[command]:
            # settings accesspoint if command is not None
            self.conf.set("accesspoint", self.commands[command], value)
            return

        for func in self.parser_list_func:
            if command in func:
                return getattr(self.parser_list_func[func], func)(value, args)
        # hook function configure plugin
        for plugin in self.parser_autcomplete_func:
            if command in self.parser_autcomplete_func[plugin]:
                return getattr(self.parser_list_func[plugin], plugin)(value, command)

        print(display_messages("unknown command: {} ".format(command), error=True))

    def do_proxys(self, args):
        """ show all proxys available for attack  """
        headers_table, output_table = ["Proxy", "Active", "Port", "Description"], []
        plugin_info_activated = None
        config_instance = None
        headers_plugins, output_plugins = ["Name", "Active"], []

        for plugin_name, plugin_info in self.proxy_controller.getInfo().items():
            status_plugin = self.conf.get("proxy_plugins", plugin_name, format=bool)
            # save plugin activated infor
            if plugin_info["Config"] != None:
                if self.conf.get_name_activated_plugin("proxy_plugins") == plugin_name:
                    plugin_info_activated = plugin_info
                    config_instance = plugin_info_activated["Config"]

            output_table.append(
                [
                    plugin_name,
                    setcolor("True", color="green")
                    if status_plugin
                    else setcolor("False", color="red"),
                    plugin_info["Port"],
                    plugin_info["Description"][:50] + "..."
                    if len(plugin_info["Description"]) > 50
                    else plugin_info["Description"],
                ]
            )

        print(display_messages("Available Proxys:", info=True, sublime=True))
        display_tabulate(headers_table, output_table)
        # check plugin none
        if not plugin_info_activated:
            return
        # check if plugin selected is iquals the plugin config
        if plugin_info_activated["ID"] != self.conf.get_name_activated_plugin(
            "proxy_plugins"
        ):
            return
        all_plugins = plugin_info_activated["Config"].get_all_childname("plugins")
        for plugin_name in all_plugins:
            status_plugin = config_instance.get("plugins", plugin_name, format=bool)
            output_plugins.append(
                [
                    plugin_name,
                    setcolor("True", color="green")
                    if status_plugin
                    else setcolor("False", color="red"),
                ]
            )
        print(
            display_messages(
                "{} plugins:".format(plugin_info_activated["Name"]),
                info=True,
                sublime=True,
            )
        )
        return display_tabulate(headers_plugins, output_plugins)

    def do_plugins(self, args=str):
        """ show all plugins available for attack """
        headers_table, output_table = ["Name", "Active", "Description"], []
        headers_plugins, output_plugins = ["Name", "Active"], []
        all_plugins, config_instance = None, None
        for plugin_name, plugin_info in self.mitm_controller.getInfo().items():
            status_plugin = self.conf.get("mitm_modules", plugin_name, format=bool)
            output_table.append(
                [
                    plugin_name,
                    setcolor("True", color="green")
                    if status_plugin
                    else setcolor("False", color="red"),
                    plugin_info["Description"][:50] + "..."
                    if len(plugin_info["Description"]) > 50
                    else plugin_info["Description"],
                ]
            )
            if (
                self.mitm_controller.getInfo()[plugin_name]["Config"] != None
                and status_plugin
            ):
                config_instance = self.mitm_controller.getInfo()[plugin_name]["Config"]
                all_plugins = self.mitm_controller.getInfo()[plugin_name][
                    "Config"
                ].get_all_childname("plugins")

        print(display_messages("Available Plugins:", info=True, sublime=True))
        display_tabulate(headers_table, output_table)

        if not all_plugins:
            return

        for plugin_name in all_plugins:
            status_plugin = config_instance.get("plugins", plugin_name, format=bool)
            output_plugins.append(
                [
                    plugin_name,
                    setcolor("True", color="green")
                    if status_plugin
                    else setcolor("False", color="red"),
                ]
            )
        print(display_messages("Sniffkin3 plugins:", info=True, sublime=True))
        return display_tabulate(headers_plugins, output_plugins)

    def help_plugins(self):
        print(
            "\n".join(
                [
                    "usage: set plugin [module name ] [(True/False)]",
                    "wifipumpkin-ng: error: unrecognized arguments",
                ]
            )
        )

    def getColorStatusPlugins(self, status):
        if status:
            return setcolor(status, color="green")
        return setcolor(status, color="red")

    def complete_info(self, text, args, start_index, end_index):
        if text:
            return [
                command
                for command in list(self.commands.keys())
                if command.startswith(text)
            ]
        else:
            return list(self.commands.keys())

    def complete_ignore(self, text, args, start_index, end_index):
        if text:
            return [
                command
                for command in self.logger_manager.all()
                if command.startswith(text)
            ]
        else:
            return list(self.logger_manager.all())

    def complete_restore(self, text, args, start_index, end_index):
        if text:
            return [
                command
                for command in self.logger_manager.all()
                if command.startswith(text)
            ]
        else:
            return list(self.logger_manager.all())

    def complete_set(self, text, args, start_index, end_index):
        if text:
            command_list = []
            for func in self.parser_autcomplete_func:
                if text.startswith(func.split("_set_")[1]):
                    for command in self.parser_autcomplete_func[func]:
                        if command.startswith(text):
                            command_list.append(command)

            for command in self.commands:
                if command.startswith(text):
                    command_list.append(command)
            return command_list
        else:
            return list(self.commands.keys())

    def complete_use(self, text, args, start_index, end_index):
        if text:
            return [
                command
                for command in list(self.all_modules.keys())
                if command.startswith(text)
            ]
        else:
            return list(self.all_modules.keys())

    def do_exit(self, args):
        """ exit program and all threads"""
        self.killThreads()
        print("Exiting...")
        raise SystemExit