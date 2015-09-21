"""styled_popup"""
import sublime
import sublime_plugin
import os
import hashlib
import time
import re

from plistlib import readPlistFromBytes

def show_popup(view, content, *args, **kwargs):
	"""Parse the color scheme if needed and show the styled pop-up."""

	if view == None:
		return

	manager = StyleSheetManager()
	color_scheme = view.settings().get("color_scheme")

	style_sheet = manager.get_stylesheet(color_scheme)["content"]

	html = "<html><body>"
	html += "<style>%s</style>" % (style_sheet)
	html += content
	html += "</body></html>"

	view.show_popup(html,  *args, **kwargs)


class StyleSheetManager():
	"""Handles loading and saving data to the file on disk as well as provides a simple interface for"""
	"""accessing the loaded style sheets. """
	style_sheets = {}

	def __init__(self):
		self.theme_file_path = os.path.join(sublime.packages_path(), "User", "scheme_styles.json")
		self.resource_path = "/".join(["Packages", "User", "scheme_styles.json"])
		self.style_sheets = {}
		settings = sublime.load_settings("Preferences.sublime-settings")
		self.cache_limit = settings.get("popup_style_cache_limit", 5)

	def is_stylesheet_parsed_and_current(self, color_scheme):
		"""Parse the color scheme if needed or if the color scheme file has changed."""

		if not self.has_stylesheet(color_scheme) or not self.is_file_hash_stale(color_scheme):
			return False

		return True

	def load_stylesheets_content(self):
		"""Load the content of the scheme_styles.json file."""

		content = ""
		if  os.path.isfile(self.theme_file_path):
			content = sublime.load_resource(self.resource_path)

		return content

	def get_stylesheets(self):
		"""Get the stylesheet dict from the file or return an empty dictionary no file contents."""

		if not len(self.style_sheets):
			content = self.load_stylesheets_content()
			if  len(content):
				self.style_sheets = sublime.decode_value(str(content))

		return self.style_sheets

	def count_stylesheets(self):
		return len(self.get_stylesheets())

	def save_stylesheets(self, style_sheets):
		"""Save the stylesheet dictionary to file"""

		content = sublime.encode_value(style_sheets, True)

		with open(self.theme_file_path, "w") as f:
			f.write(content)

		self.style_sheets = style_sheets

	def has_stylesheet(self, color_scheme):
		"""Check if the stylesheet dictionary has the current color scheme."""

		if color_scheme in self.get_stylesheets():
			return True

		return False

	def add_stylesheet(self, color_scheme, content):
		"""Add the parsed color scheme to the stylesheets dictionary."""

		style_sheets = self.get_stylesheets()

		if (self.count_stylesheets() >= self.cache_limit):
			self.drop_oldest_stylesheet()

		file_hash = self.get_file_hash(color_scheme)
		style_sheets[color_scheme] = {"content": content, "hash": file_hash, "time": time.time()}
		self.save_stylesheets(style_sheets)

	def get_stylesheet(self, color_scheme):
		"""Get the supplied color scheme stylesheet if it exists."""
		active_sheet = None

		if not self.is_stylesheet_parsed_and_current(color_scheme):
			scheme_css = SchemeParser().run(color_scheme)
			self.add_stylesheet(color_scheme, scheme_css)

		active_sheet = self.get_stylesheets()[color_scheme]


		return active_sheet

	def drop_oldest_stylesheet(self):
		style_sheets = self.get_stylesheets()

		def sortByTime(item):
			return style_sheets[item]["time"]

		keys = sorted(style_sheets, key = sortByTime)

		while len(style_sheets) >= self.cache_limit:
			del style_sheets[keys[0]]
			del keys[0]

		self.save_stylesheets(style_sheets)

	def get_file_hash(self, color_scheme):
		"""Generate an MD5 hash of the color scheme file to be compared for changes."""

		content = sublime.load_binary_resource(color_scheme)
		file_hash = hashlib.md5(content).hexdigest()
		return file_hash

	def is_file_hash_stale(self, color_scheme):
		"""Check if the color scheme file has changed on disk."""

		stored_hash = ""
		current_hash = self.get_file_hash(color_scheme)
		styles_heets = self.get_stylesheets()

		if color_scheme in styles_heets:
			# stored_hash = styles_heets[color_scheme]["hash"]
			stored_hash = styles_heets[color_scheme]["hash"]

		return (current_hash == stored_hash)


class SchemeParser():
	"""Parses color scheme and builds css file"""

	def run(self, color_scheme):
		"""Parse the color scheme for the active view."""

		print ("Styled Popup: Parsing color scheme")

		content = self.load_color_scheme(color_scheme)
		scheme = self.read_scheme(content)
		css_stack = StackBuilder().build_stack(scheme["settings"])
		style_sheet = self.generate_style_sheet_content(css_stack)
		return style_sheet

	def load_color_scheme(self, color_scheme):
		"""Read the color_scheme user settings and load the file contents."""

		content  = sublime.load_binary_resource(color_scheme)
		return content

	def read_scheme(self, scheme):
		"""Converts supplied scheme(bytes) to python dict."""

		return  readPlistFromBytes(scheme)

	def generate_style_sheet_content(self, properties):
		file_content = ""
		formatted_properties = []
		sorted(properties, key=str.lower)

		for css_class in properties:
			properties_string = CSSFactory.generate_properties_string(css_class, properties)
			formatted_properties.append("%s { %s } " % (css_class, properties_string))

		file_content = "".join(formatted_properties)

		return file_content


class StackBuilder():
	stack = {}

	def __init__(self):
		self.clear_stack()

	def clear_stack(self):
		self.stack = {}

	def is_valid_node(self, node):
		if "settings" not in node:
			return False

		if not len(node["settings"]):
			return False

		return True

	def is_base_style(self, node):
		if "scope" in node:
			return False

		return True

	def build_stack(self, root):
		"""Parse scheme dictionary into css classes and properties."""

		self.clear_stack()
		for node in root:
			css_properties = {}

			if not self.is_valid_node(node):
				continue

			styles = node["settings"]
			css_properties = self.generate_css_properties(styles)

			if not len(css_properties):
				continue

			if self.is_base_style(node):
				if "html" not in self.stack:
					self.set_base_style(css_properties)
			else:
				classes = self.get_node_classes_from_scope(node["scope"])
				classes = self.filter_non_supported_classes(classes)
				self.apply_properties_to_classes(classes, css_properties)

		return self.stack

	def generate_css_properties(self, styles):
		properties = {}
		for key in styles:
			for value in styles[key].split():
				new_property = CSSFactory.generate_new_property(key, value)
				properties.update(new_property)

		return properties

	def set_base_style(self, css_style):
		css_background_property = CSSFactory.CSS_NAME_MAP["background"]
		css_style[css_background_property] = ColorFactory().getTintedColor(css_style[css_background_property], 10)
		self.stack["html"] = css_style

	def apply_properties_to_classes(self, classes, properties):
		for css_class in classes:
			css_class = css_class.strip()
			if (not css_class.startswith(".")):
				css_class = "." + css_class

			self.set_class_properties(css_class, properties)

	def set_class_properties(self, css_class, properties):
		self.stack[css_class] = properties

	def get_node_classes_from_scope(self, scope):
		scope = "." + scope.lower().strip()
		scope = scope.replace(" - ","")
		scope = scope.replace(" ", ",")
		scope = scope.replace("|",",")
		scopes = scope.split(",")
		return scopes

	def filter_non_supported_classes(self, in_classes):
		out_classes = []
		regex = r"""\A\.(
				comment(\.(line(\.(double-slash|double-dash))?|block(\.documentation)?))?|
				constant(\.(numeric|character(\.escape)?|language|other))?|
				entity(\.(name(\.(function|type|tag|section))?|other(\.(inherited-class|attribute-name))?))?|
				invalid(\.(illegal|deprecated))?|
				keyword(\.(control|operator|other))?|
				markup(\.(underline(\.(link))?|bold|heading|italic|list(\.(numbered|unnumbered))?|quote|raw|other))?|
				meta|
				storage(\.(type|modifier))?|
				string(\.(quoted(\.(single|double|triple|other))?|unquoted|interpolated|regexp|other))?|
				support(\.(function|class|type|constant|variable|other))?|
				variable(\.(parameter|language|other))?)"""

		for css_class in in_classes:
			match = re.search(regex, css_class, re.IGNORECASE + re.VERBOSE) 
			if (match):
				out_classes.append(css_class)

		return out_classes

class CSSFactory():

	CSS_NAME_MAP = {
		"background": "background-color",
		"foreground": "color"
	}

	CSS_DEFAULT_VALUES = {
		"font-style": "normal",
		"font-weight": "normal",
		"text-decoration": "none"
	}

	@staticmethod
	def generate_new_property(key, value):
		new_property = {}
		value = value.strip()

		property_name = CSSFactory.get_property_name(key, value)

		if (property_name == None):
			return new_property

		if len(value):
			new_property[property_name] = value
		else:
			new_property[property_name] = CSSFactory.get_property_default(property_name, value)

		return new_property

	@staticmethod
	def generate_properties_string(css_class, dict):
		"""Build a list of css properties and return as string."""

		property_list = []
		properties = ""
		for prop in dict[css_class]:
			property_list.append("%s: %s; " % (prop, dict[css_class][prop]))

		properties = "".join(property_list)

		return properties

	@staticmethod
	def get_property_name(name, value):
		"""Get the css name of a scheme value if supported."""

		# fontStyle can be mapped to font-style and font-weight. Need to handle both
		if name == "fontStyle":
			if value == "bold":
				return "font-weight"

			if value == "underline":
				return "text-decoration"

			return "font-style"

		if name in CSSFactory.CSS_NAME_MAP:
			return CSSFactory.CSS_NAME_MAP[name]

		return None

	@staticmethod
	def get_property_default(prop):
		if prop in CSSFactory.CSS_DEFAULT_VALUES:
			return CSSFactory.CSS_DEFAULT_VALUES[prop]

		return None

class ColorFactory():
	"""Helper class responsible for all color based calculations and conversions."""

	def getTintedColor(self, color, percent):
		"""Adjust the average color by the supplied percent."""

		rgb = self.hex_to_rgb(color)
		average = self.get_rgb_average(rgb)
		mode = 1 if average < 128 else -1

		delta = ((256 * (percent / 100)) * mode)
		rgb = (rgb[0] + delta, rgb[1] + delta, rgb[2] + delta)
		color = self.rgb_to_hex(rgb)

		return color

	def get_rgb_average(self, rgb):
		"""Find the average value for the curren rgb color."""

		return int( sum(rgb) / len(rgb) )

	def hex_to_rgb(self, color):
		"""Convert a hex color to rgb value"""

		hex_code = color.lstrip("#")
		hex_length = len(hex_code)

		#Break the hex_code into the r, g, b hex values and convert to decimal values.
		rgb = tuple(int(hex_code[i:i + hex_length // 3], 16) for i in range(0,hex_length,hex_length //3))

		return rgb

	def rgb_to_hex(self, rgb):
		""" Convert the supplied rgb tuple into hex color value"""

		return "#%02x%02x%02x" % rgb


class StyleSheet():
	content=""
	hash=""
	time=0
