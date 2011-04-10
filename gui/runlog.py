#
#    Copyright (C) 2011 Stanislav Bohm
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

import project
import simulation
import utils
import copy
import os

CACHE_FRAME_PERIOD = 200

class LogFrame:

	full_frame = True

	def __init__(self, time, place_content, name):
		self.time = time
		self.place_content = place_content
		self.running = []
		self.started = []
		self.ended = []
		self.name = name

	def get_tokens(self, place, iid = None):
		if iid is None:
			return self.place_content[place.get_id()]
		else:
			return self.place_content[place.get_id()][iid]

	def get_time(self):
		return self.time

	def copy(self):
		return copy.deepcopy(self)


class LogFrameDiff:

	full_frame = False

	def __init__(self, time, actions):
		self.time = time
		self.actions = actions

	def apply_on_frame(self, frame, project):
		frame.time = self.time
		frame.started = []
		frame.ended = []
		frame.blocked = []
		for action in self.actions.split("\n"):
			self.parse_action(frame, action)

		for transition_id, iid in frame.started: # Reset input packing edges
			for edge in project.get_net().get_item(transition_id).edges_to(postprocess = True):
				if edge.is_packing_edge():
					frame.place_content[edge.from_item.get_id()][iid] = []

		return frame

	def parse_action(self, frame, action):
		action_type = action[0]
		if action_type == "A":
			iid, place_id, token_name = action.split(" ", 3)
			iid = int(iid[1:])
			place_id = int(place_id)
			frame.place_content[place_id][iid].append(token_name)
		if action_type == "R":
			iid, place_id, token_name = action.split(" ", 3)
			iid = int(iid[1:])
			place_id = int(place_id)
			frame.place_content[place_id][iid].remove(token_name)

		if action_type == "S":
			iid, transition_id = action.split(" ", 2)
			iid = int(iid[1:])
			transition_id = int(transition_id)
			item = (transition_id, iid)
			frame.running.append(item)
			frame.started.append(item)
			frame.name = "S"

		if action_type == "E":
			iid, transition_id = action.split(" ", 2)
			iid = int(iid[1:])
			transition_id = int(transition_id)
			item = (transition_id, iid)
			if item in frame.running:
				frame.running.remove(item)
			frame.ended.append(item)
			frame.name = "E"

		if action_type == "C":
			frame.name = "R"

		if action_type == "T":
			args = action.split(" ")
			node = int(args[0][1:])
			frame.blocked += [ (node, int(t)) for t in args[1:] ]

	def get_time(self):
		return self.time


class Log:

	def __init__(self, filename):
		basename = os.path.basename(filename)
		self.name, ext = os.path.splitext(basename)
		self.load(filename)

	def get_name(self):
		return self.name

	def load(self, filename):
		with open(filename,"r") as f:
			f.readline() # Skip first line
			settings = xml.fromstring(f.readline())
			lines_count = int(settings.get("description-lines"))
			self.process_count = int(settings.get("process-count"))
			proj = xml.fromstring("\n".join([ f.readline() for i in xrange(lines_count) ]))
			self.project = project.load_project_from_xml(proj, "")

			self.node_to_process = {}

			lines = [ f.readline() for i in xrange(self.process_count) ]
			place_content, self.areas_instances, transitions, self.node_to_process = \
				simulation.join_reports(lines)

			frame = LogFrame(0, place_content, "I")
			self.frames = [ frame.copy() ]

			next_time = self.parse_time(f.readline())
			inf = float("inf")
			if next_time < inf:
				diff, next_time = self.load_frame_diff(f, next_time)
				frame = diff.apply_on_frame(frame, self.project)
				while next_time < inf:
					if len(self.frames) % CACHE_FRAME_PERIOD == 0:
						self.frames.append(frame.copy())
					else:
						self.frames.append(diff)
					diff, next_time = self.load_frame_diff(f, next_time)
					frame = diff.apply_on_frame(frame, self.project)
				self.frames.append(diff)
			self.maxtime = self.frames[-1].get_time()

	def nodes_count(self):
		return sum( [ len(instances) for instances in self.areas_instances.values() ] )

	def frames_count(self):
		return len(self.frames)

	def parse_time(self, string):
		if string == "":
			return float("inf")
		else:
			return int(string)

	def load_frame_diff(self, f, time):
		lines = []
		line = f.readline()
		while line and not line[0].isdigit():
			lines.append(line.strip())
			line = f.readline()
		return (LogFrameDiff(time, "\n".join(lines)), self.parse_time(line))

	def get_area_instances_number(self, area):
		return len(self.areas_instances[area.get_id()])

	def get_instance_node(self, area, iid):
		for i, node, running in self.areas_instances[area.get_id()]:
			if iid == i:
				return node

	def get_frame(self, pos):
		frame = self.frames[pos]
		if frame.full_frame:
			return frame.copy()
		else:
			return frame.apply_on_frame(self.get_frame(pos - 1), self.project)

	def get_time_string(self, frame):
		maxtime = time_to_string(self.maxtime)
		return "{0:0>{1}}".format(time_to_string(frame.get_time()), len(maxtime))

	def get_default_area_id(self):
		x = [ area.get_id() for area in self.project.net.areas() ]
		y = [ i for i in self.areas_instances if i not in x ]
		if y:
			return y[0]
		else:
			return None

	def area_address(self, area_id):
		for iid, node, running in self.areas_instances[area_id]:
			if iid == 0:
				return node

	def transition_to_node_table(self):
		default_id = self.get_default_area_id()
		result = {}
		for transition in self.project.net.transitions():
			area = transition.area()
			if area is None:
				area_id = default_id
			else:
				area_id = area.get_id()
			address = self.area_address(area_id)
			result[transition.get_id()] = [ i + address for i in xrange(len(self.areas_instances[area_id])) ]
		return result

	def get_mapping(self):
		result = []
		for area_id, area_content in self.areas_instances.items():
			area = self.project.get_item(area_id)
			if area:
				area_name = area.get_name()
			else:
				area_name = "Default area"
			for iid, node, running in area_content:
				result.append((node, iid, area_name, self.node_to_process[node]))
		result.sort(key=lambda i: i[0])
		return result


	def get_statistics(self):
		places = self.project.net.places()
		init = self.frames[0]
		tokens = []
		tokens_names = []
		nodes = [ [] for i in xrange(self.nodes_count()) ]
		nodes_names = [ "node={0}".format(i) for i in xrange(self.nodes_count()) ]
		processes = [ [] for i in xrange(self.process_count) ]
		processes_names = [ "process={0}".format(i) for i in xrange(self.process_count) ]
		transition_table = self.transition_to_node_table()

		transitions = []
		transitions_names = []
		transitions_pos = {}

		for t in self.project.net.transitions():
			instances = transition_table[t.get_id()]
			for i, node in enumerate(instances):
				transitions_names.append("{0}@{1}".format(t.get_name(), i))
				transitions_pos[(t.get_id(), node)] = len(transitions)
				transitions.append([])

		for p in places:
			content = init.place_content[p.get_id()]
			for iid in content:
				tokens.append([(0,len(content[iid]))])
				tokens_names.append(str(p.get_id()) + "@" + str(iid))

		f = init.copy()
		for frame in self.frames[1:]:
			if frame.full_frame:
				f = frame.copy()
			else:
				f = frame.apply_on_frame(f, self.project)
			i = 0
			time = f.get_time()
			for p in places:
				content = f.place_content[p.get_id()]
				for iid in content:
					t, v = tokens[i][-1]
					if len(content[iid]) != v:
						tokens[i].append((time, len(content[iid])))
					i += 1
			for transition_id, iid in f.started:
				node = transition_table[transition_id][iid]
				value = (time, 0)
				nodes[node].append(value)
				processes[self.node_to_process[node]].append(value)
				transitions[transitions_pos[(transition_id, node)]].append(value)

			for transition_id, iid in f.ended:
				node = transition_table[transition_id][iid]
				value = (time, None)
				nodes[node].append(value)
				processes[self.node_to_process[node]].append(value)
				transitions[transitions_pos[(transition_id, node)]].append(value)

			written = []
			value1 = (time, 1)
			value2 = (time, 2)
			for node, transition_id in f.blocked:
				if nodes[node] and nodes[node][-1][1] == 0:
					v = value2
				else:
					v = value1
				t = transitions_pos[(transition_id, node)]
				if not transitions[t] or transitions[t][-1][1] != v[1]:
					transitions[t].append(v)
				if node not in written:
					if not nodes[node] or nodes[node][-1][1] != 1:
						nodes[node].append(value1)
					written.append(node)

		result = {}
		result["tokens"] = tokens
		result["tokens_names"] = tokens_names
		result["nodes"] = nodes
		result["nodes_names"] = nodes_names
		result["processes"] = processes
		result["processes_names"] = processes_names
		result["transitions"] = transitions
		result["transitions_names"] = transitions_names
		return result

def time_to_string(nanosec):
	s = nanosec / 1000000000
	nsec = nanosec % 1000000000
	sec = s % 60
	minutes = (s / 60) % 60
	hours = s / 60 / 60
	return "{0}:{1:0>2}:{2:0>2}:{3:0>9}".format(hours, minutes, sec, nsec)