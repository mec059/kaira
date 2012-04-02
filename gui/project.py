#
#    Copyright (C) 2010, 2011 Stanislav Bohm
#                  2011       Ondrej Meca
#
#    This file is part of Kaira.
#
#    Kaira is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License, or
#    (at your option) any later version.
#
#    Kaira is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Kaira.  If not, see <http://www.gnu.org/licenses/>.
#

import xml.etree.ElementTree as xml
import utils
import os
import ptp

from events import EventSource
from simconfig import SimConfig

class Project(EventSource):
    """
        Events: changed, netlist_changed filename_changed
    """

    force_packers = False

    def __init__(self, file_name):
        assert file_name is not None
        EventSource.__init__(self)
        self.id_counter = 100
        self.set_filename(file_name)
        self.nets = []
        self.parameters = []
        self.extern_types = []
        self.simconfig = SimConfig()
        self.error_messages = {}
        self.functions = []
        self.generator = None

    def get_build_option(self, name):
        if name in self.build_options:
            return self.build_options[name]
        else:
            return ""

    def get_generator(self):
        if self.generator:
            return self.generator
        self.generator = ptp.get_generator_from_xml(self.export_xml())
        return self.generator

    def set_build_option(self, name, value):
        self.build_options[name] = value
        self.changed()

    def new_id(self):
        self.id_counter += 1
        return self.id_counter

    def add_net(self, net):
        self.nets.append(net)
        net.set_change_callback(self._net_changed)
        self.emit_event("netlist_changed")

    def find_net(self, id):
        for net in self.nets:
            if net.id == id:
                return net

    def remove_net(self, net):
        self.nets.remove(net)
        self.emit_event("netlist_changed")

    def get_simconfig(self):
        return self.simconfig

    def get_nets(self):
        return self.nets

    def get_nets_with_interface(self):
        if self.nets[0].is_module():
            return self.nets
        else:
            return self.nets[1:] # Only first network has no interface

    def get_name(self):
        d, fname = os.path.split(self.filename)
        name, ext = os.path.splitext(fname)
        return name

    def reset_param_values(self):
        self.simconfig.reset_param_values()

    def get_filename(self):
        return self.filename

    def get_filename_without_ext(self):
        name, ext = os.path.splitext(self.filename)
        return name

    def get_executable_filename(self):
        return self.get_filename_without_ext()

    def get_exported_filename(self):
        return self.get_filename_without_ext() + ".xml"

    def get_directory(self):
        return os.path.dirname(self.filename)

    def set_filename(self, filename):
        self.filename = os.path.abspath(filename)
        self.emit_event("filename_changed")

    def set_error_messages(self, messages):
        self.error_messages = messages
        self.changed()

    def get_item(self, id):
        for function in self.functions:
            if function.id == id:
                return function
        for net in self.nets:
            item = net.get_item(id)
            if item is not None:
                return item

    def has_error_messages(self, item):
        return item.get_id() in self.error_messages

    def get_error_messages(self, item):
        if item.get_id() in self.error_messages:
            return self.error_messages[item.get_id()]
        else:
            return None

    def changed(self):
        self.generator = None # Invalidate generator cache
        self.emit_event("changed")

    def set_force_packers(self, value):
        self.force_packers = value
        self.changed()

    def _net_changed(self, net):
        self.changed()

    def as_xml(self):
        root = xml.Element("project")
        root.set("extenv", self.get_extenv_name())
        root.append(self._configuration_element(False))
        for net in self.nets:
            root.append(net.as_xml())
        return root

    def save(self):
        assert self.filename is not None
        f = open(self.filename, "w")
        try:
            f.write(xml.tostring(self.as_xml()))
        finally:
            f.close()

    def export_xml(self):
        root = xml.Element("project")
        root.set("extenv", self.get_extenv_name())

        root.append(self._configuration_element(True))

        description = xml.Element("description")
        description.text = xml.tostring(self.as_xml())
        root.append(description)

        for net in self.nets:
            root.append(net.export_xml())
        return root

    def export_to_file(self, filename):
        content = xml.tostring(self.export_xml())
        f = open(filename, "w")
        try:
            f.write(content)
        finally:
            f.close()

    def get_extern_types(self):
        return self.extern_types

    def get_functions(self):
        return self.functions

    def add_extern_type(self, obj):
        self.extern_types.append(obj)
        self.changed()

    def remove_extern_type(self, obj):
        self.extern_types.remove(obj)
        self.changed()

    def find_extern_type(self, typename):
        for t in self.extern_types:
            if t.name == typename:
                return t

    def add_function(self, obj):
        obj.set_project(self)
        self.functions.append(obj)
        self.changed()

    def remove_function(self, obj):
        self.functions.remove(obj)
        self.changed()

    def add_parameter(self, obj):
        obj.project = self
        self.reset_param_values()
        self.parameters.append(obj)
        self.changed()

    def get_parameters(self):
        return self.parameters

    def remove_parameter(self, parameter):
        self.reset_param_values()
        self.parameters.remove(parameter)
        self.changed()

    def write_project_files(self):
        self.write_makefile()
        utils.write_file_if_not_exists(self.get_head_filename(), self.get_initial_head_file_content())

    def create_extern_type(self, extern_type_name):
        if extern_type_name == "native":
            return self.create_native_extern_type()
        if extern_type_name == "protobuffer":
            return ProtobufferExternType()
        raise Exception("Unknown externtype's type")

    def _build_option_as_xml(self, name):
        element = xml.Element("build-option")
        element.set("name", name)
        element.text = self.get_build_option(name)
        return element

    def _configuration_element(self, export):
        e = xml.Element("configuration")
        for p in self.parameters:
            e.append(p.as_xml())
        for t in self.extern_types:
            e.append(t.as_xml())
        for t in self.functions:
            e.append(t.as_xml())
        for t in self.build_options:
            e.append(self._build_option_as_xml(t))

        if export:
            f = xml.Element("force-packers")
            f.set("value", str(self.force_packers))
            e.append(f)
        return e

class Parameter:
    project = None

    def __init__(self):
        self.name = ""
        self.type = "Int"
        self.description = ""
        self.default = "0"

    def set_name(self, name):
        self.name = name
        self.changed()

    def get_name(self):
        return self.name

    def set_type(self, type):
        self.type = type
        self.changed()

    def get_type(self):
        return self.type

    def get_description(self):
        return self.description

    def get_default(self):
        return self.default

    def set_description(self, description):
        self.description = description
        self.changed()

    def set_default(self, default):
        self.default = default
        self.changed()

    def changed(self):
        if self.project:
            self.project.reset_param_values()

    def as_xml(self):
        e = xml.Element("parameter")
        e.set("name", self.name)
        e.set("type", self.type)
        e.set("description", self.description)
        e.set("default", self.default)
        return e

class ExternTypeBase:

    def __init__(self):
        self.name = ""

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name

    def as_xml(self):
        e = xml.Element("extern-type")
        e.set("name", self.name)
        e.set("type", self.get_type())
        return e

class ProtobufferExternType(ExternTypeBase):

    def __init__(self):
        ExternTypeBase.__init__(self)
        self.code = ""

    def get_type(self):
        return "protobuffer"

    def get_note(self):
        return ""

    def as_xml(self):
        e = ExternTypeBase.as_xml(self)
        e.text = self.code
        return e

    def get_header(self):
        return ""

    def get_code(self):
        if self.code:
            return self.code
        else:
            return "\t\n"

    def get_sections(self):
        head = "message {0} {{\n".format(self.name)
        return [ ("", head, self.get_code(), "}\n") ]

    def set_sections_content(self, values):
        self.code = values[""]


class NativeExternType(ExternTypeBase):
    """
        Transport modes: "Disabled", "Direct", "Custom"
    """

    def __init__(self):
        ExternTypeBase.__init__(self)
        self.name = ""
        self.raw_type = ""
        self.transport_mode = "Disabled"

        self.functions = {
            "getstring": "",
            "getsize": "",
            "pack": "",
            "unpack": ""
        }

    def get_type(self):
        return "native"

    def get_note(self):
        return "Raw type: {0}, Transport: {1}".format(self.raw_type, self.transport_mode)

    def get_raw_type(self):
        return self.raw_type

    def get_transport_mode(self):
        return self.transport_mode

    def set_raw_type(self, value):
        self.raw_type = value

    def set_transport_mode(self, value):
        self.transport_mode = value

    def set_function_code(self, function, code):
        self.functions[function] = code

    def set_sections_content(self, values):
        self.functions = values

    def has_function(self, name):
        return "" != self.functions[name].strip()

    def get_function_code(self, name):
        if self.has_function(name):
            return self.functions[name]
        return self.get_default_function_code(name)

    def get_function_names(self):
        lst = [ "getstring" ]
        if self.transport_mode == "Custom":
            lst.append("getsize")
            lst.append("pack")
            lst.append("unpack")
        return lst

    def as_xml(self):
        e = ExternTypeBase.as_xml(self)
        e.set("raw-type", self.raw_type)
        e.set("transport-mode", self.transport_mode)

        for name in self.functions:
            if self.has_function(name):
                fe = xml.Element("code")
                fe.set("name", name)
                fe.text = self.functions[name]
                e.append(fe)

        return e

    def get_header(self):
        return "/*\n * Type '{0}'\n */\n\n".format(self.name)

    def get_sections(self):
        """ Returns list of sections (name, start, middle, end) for CodeEditor """
        sections = []
        for name in self.get_function_names():
            start = self.get_function_declaration(name) + "\n{\n"
            middle = self.get_function_code(name)
            end = "}\n\n\n"
            sections.append((name, start, middle, end))
        return sections

class Function():

    project = None

    def __init__(self, id = None):
        self.name = ""
        self.code = ""

        self.return_type = ""
        self.parameters = ""
        self.with_context = False
        self.id = id

    def changed(self):
        if self.project:
            self.project.changed()

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name
        self.changed()

    def set_function_code(self, code):
        if code is None:
            code = ""
        self.code = code
        self.changed()

    def get_function_code(self):
        if self.has_code():
            return self.code
        else:
            return "\t\n"

    def has_code(self):
        return self.code.strip() != ""

    def set_project(self, project):
        self.project = project
        if self.id is None:
            self.id = project.new_id()

    def get_parameters(self):
        return self.parameters

    def set_parameters(self, parameters):
        self.parameters = parameters
        self.changed()

    def get_return_type(self):
        return self.return_type

    def set_return_type(self, return_type):
        self.return_type = return_type

    def get_with_context(self):
        return self.with_context

    def set_with_context(self, value):
        self.with_context = value

    def get_function_header(self):
        return self.project.get_generator().get_user_function_header(self.name)

    def check_definition(self):
        return self.get_function_header() is not None

    def split_parameters(self):
        return [ x.split() for x in self.parameters.split(", ") if x.strip() != ""]

    def as_xml(self):
        e = xml.Element("function")
        e.set("id", str(self.id))
        e.set("name", self.name)
        e.set("return-type", self.return_type)
        e.set("parameters", self.parameters)
        e.set("with-context", str(self.with_context))
        e.text = self.code
        return e
