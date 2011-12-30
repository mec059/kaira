#
#    Copyright (C) 2011 Stanislav Bohm
#    Copyright (C) 2011 Ondrej Meca
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
import utils
import os
import paths
from project import Project, ExternType, Function

class ProjectCpp(Project):

    def __init__(self, file_name):
        Project.__init__(self, file_name)
        self.build_options = {
            "CC" : "g++",
            "CFLAGS" : "-O2",
            "LIBS" : ""
        }

    @classmethod
    def get_extenv_name(self):
        return "C++"

    def get_exttype_class(self):
        return ExternTypeCpp

    def get_function_class(self):
        return FunctionCpp

    def get_syntax_highlight_key(self):
        """return language for GtkSourceView"""
        return "cpp"

    def get_emitted_source_filename(self):
        return self.get_filename_without_ext() + ".cpp"

    def get_head_filename(self):
        return os.path.join(self.get_directory(), "head.cpp")

    def get_initial_head_file_content(self):
        return "/* This file is included at the beginning of the main source file,\n" \
               "   so definitions from this file can be used in functions in\n" \
               "   transitions and places. */\n\n"

    def type_to_raw_type(self, t):
        if t == "__Context":
            return "CaContext"
        if t == "Int":
            return "int"
        if t == "Array(Int)":
            return "std::vector<int>"
        if t == "(Int, Array(Int))":
            return "Tuple2_int_Array_int"
        if t == "Array((Int, Array(Int)))":
            return "std::vector<Tuple2_Int_Array1_Int>"
        if t == "Bool":
            return "bool"
        if t == "Float":
            return "float"
        if t == "Double":
            return "double"
        if t == "String":
            return "std::string"
        for et in self.extern_types:
            if et.get_name() == t:
                return et.get_raw_type()
        return t

    def get_source_file_patterns(self):
        return ["*.cpp", "*.cc", "*.c"]

    def write_makefile(self):
        makefile = utils.Makefile()
        makefile.set_top_comment("This file is autogenerated.\nDo not edit directly this file.")
        makefile.set("CC", self.get_build_option("CC"))
        makefile.set("CFLAGS", self.get_build_option("CFLAGS"))
        makefile.set("LIBDIR", "-L" + paths.CAILIE_LIB_DIR)
        makefile.set("LIBS", "-lcailie -lpthread -lrt " + self.get_build_option("LIBS"))
        makefile.set("MPILIBS", "-lcailiempi -lpthread -lrt " + self.get_build_option("LIBS"))
        makefile.set("INCLUDE", "-I" + paths.CAILIE_DIR)
        makefile.set("MPICC", "mpic++")
        makefile.set("MPILIBDIR", "-L" + paths.CAILIE_MPI_LIB_DIR)

        if self.get_build_option("OTHER_FILES"):
            other_deps = [ os.path.splitext(f)[0] + ".o" for f in self.get_build_option("OTHER_FILES").split("\n") ]
        else:
            other_deps = []

        name_o = self.get_name() + ".o"
        name_cpp = self.get_name() + ".cpp"
        name_debug = self.get_name() + "_debug"
        name_debug_o = self.get_name() + "_debug.o"
        name_mpi_o = self.get_name() + "_mpi.o"
        name_mpi_debug_o = self.get_name() + "_mpi_debug.o"

        makefile.rule("all", [self.get_name()])
        makefile.rule("debug", [name_debug])
        makefile.rule("mpi", [self.get_name() + "_mpi"])
        makefile.rule("mpidebug", [self.get_name() + "_mpidebug"])

        deps = [ name_o ] + other_deps
        deps_debug = [ name_debug_o ] + other_deps
        deps_mpi = [ name_mpi_o ] + other_deps
        deps_mpi_debug = [ name_mpi_debug_o ] + other_deps
        makefile.rule(self.get_name(), deps, "$(CC) " + " ".join(deps) + " -o $@ $(CFLAGS) $(INCLUDE) $(LIBDIR) $(LIBS) " )

        makefile.rule(name_debug, deps_debug, "$(CC) " + " ".join(deps_debug) + " -o $@ $(CFLAGS) $(INCLUDE) $(LIBDIR) $(LIBS) " )

        makefile.rule(self.get_name() + "_mpi", deps_mpi, "$(MPICC) -D CA_MPI " + " ".join(deps_mpi)
            + " -o $@ $(CFLAGS) $(INCLUDE) $(MPILIBDIR) $(MPILIBS)" )
        makefile.rule(self.get_name() + "_mpidebug", deps_mpi_debug, "$(MPICC) -D CA_MPI " + " ".join(deps_mpi_debug)
            + " -o $@ $(CFLAGS) $(INCLUDE) $(MPILIBDIR) $(MPILIBS)" )

        makefile.rule(name_o, [ name_cpp, "head.cpp" ], "$(CC) $(CFLAGS) $(INCLUDE) -c {0} -o {1}".format(name_cpp, name_o))
        makefile.rule(name_debug_o, [ name_cpp, "head.cpp" ], "$(CC) -DCA_LOG $(CFLAGS) $(INCLUDE) -c {0} -o {1}".format(name_cpp, name_debug_o))
        makefile.rule(name_mpi_o, [ name_cpp, "head.cpp" ], "$(MPICC) -DCA_MPI $(CFLAGS) $(INCLUDE) -c {0} -o {1}".format(name_cpp, name_mpi_o))
        makefile.rule(name_mpi_debug_o, [ name_cpp, "head.cpp" ], "$(MPICC) -DCA_MPI -DCA_LOG $(CFLAGS) $(INCLUDE) -c {0} -o {1}".format(name_cpp, name_mpi_debug_o))
        all = deps + [ name_o, name_mpi_o, name_debug_o, name_mpi_debug_o ]
        makefile.rule("clean", [], "rm -f {0} {0}_debug {0}_mpi {0}_mpidebug {1}".format(self.get_name()," ".join(all)))
        makefile.rule(".cpp.o", [], "$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@")
        makefile.rule(".cc.o", [], "$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@")
        makefile.rule(".c.o", [], "$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@")
        makefile.write_to_file(os.path.join(self.get_directory(), "makefile"))

class ExternTypeCpp(ExternType):

    def __init__(self, name = "", raw_type = "", transport_mode = "Disabled"):
        ExternType.__init__(self, name, raw_type, transport_mode)


    def get_default_function_code(self):
        return "\treturn \"" + self.name + "\";\n"

    def get_function_declaration(self, name):
        if name == "getstring":
            return "std::string getstring(const " + self.raw_type + " &obj)"
        elif name == "getsize":
            return "size_t getsize(const " + self.raw_type + " &obj)"
        elif name == "pack":
            return "void pack(CaPacker &packer, const " + self.raw_type + " &obj)"
        elif name == "unpack":
            return self.raw_type + " unpack(CaUnpacker &unpacker)"

class FunctionCpp(Function):

    def __init__(self, id = None):
        Function.__init__(self, id)

    def get_function_declaration(self):
        return self.get_raw_return_type() + " " + self.name + "(" + self.get_raw_parameters() + ")"

    def get_raw_parameters(self):
        p = self.split_parameters()
        if p is None:
            return "Invalid format of parameters"
        else:
            params_str =    [ self.project.type_to_raw_type(t) + " &" + n for (t, n) in p ]
            if self.with_context:
                params_str.insert(0, "CaContext &ctx")
            return ", ".join(params_str)

    def get_raw_return_type(self):
        return self.project.type_to_raw_type(self.return_type)
