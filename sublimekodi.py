import sublime_plugin
import sublime
import re
import os
import sys
import cgi
__file__ = os.path.normpath(os.path.abspath(__file__))
__path__ = os.path.dirname(__file__)
libs_path = os.path.join(__path__, 'libs')
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)
from polib import polib
from lxml import etree as ET
from InfoProvider import InfoProvider
from Utils import *
import webbrowser
import string
INFOS = InfoProvider()
# sublime.log_commands(True)
APP_NAME = "kodi"
if sublime.platform() == "linux":
    KODI_PRESET_PATH = "/usr/share/%s/" % APP_NAME
elif sublime.platform() == "windows":
    KODI_PRESET_PATH = "C:/%s/" % APP_NAME
else:
    KODI_PRESET_PATH = ""
SETTINGS_FILE = 'sublimekodi.sublime-settings'


class SublimeKodi(sublime_plugin.EventListener):

    def __init__(self, **kwargs):
        self.actual_project = None
        self.prev_selection = None
        self.is_modified = False
        self.settings_loaded = False

    def on_selection_modified_async(self, view):
        if len(view.sel()) > 1:
            return None
        try:
            region = view.sel()[0]
            folder = view.file_name().split(os.sep)[-2]
        except:
            return None
        if region == self.prev_selection:
            return None
        elif not INFOS.addon_xml_file:
            return None
        flags = sublime.CLASS_WORD_START | sublime.CLASS_WORD_END
        popup_label = ""
        identifier = ""
        info_type = ""
        info_id = ""
        self.prev_selection = region
        view.hide_popup()
        scope_name = view.scope_name(region.b)
        line = view.line(region)
        line_contents = view.substr(line).lower()
        label_region = view.expand_by_class(region, flags, '$],')
        bracket_region = view.expand_by_class(region, flags, '<>')
        selected_content = view.substr(view.expand_by_class(region, flags, '<>"[]'))
        if label_region.begin() > bracket_region.begin() and label_region.end() < bracket_region.end():
            identifier = view.substr(label_region)
            info_type = identifier.split("[", 1)[0]
            info_id = identifier.split("[", 1)[1]
        if "source.python" in scope_name:
            if "lang" in line_contents or "label" in line_contents or "string" in line_contents:
                popup_label = INFOS.return_label(selected_content)
        elif "text.xml" in scope_name:
            if info_type in ["INFO", "VAR", "LOCALIZE"]:
                popup_label = INFOS.translate_square_bracket(info_type=info_type, info_id=info_id, folder=folder)
            elif "<include" in line_contents and "name=" not in line_contents:
                node_content = str(INFOS.return_node_content(get_node_content(view, flags), folder=folder))
                ind1 = node_content.find('\\n')
                popup_label = cgi.escape(node_content[ind1 + 2:-15]).replace("\\n", "<br>"). replace(" ", "&nbsp;")
                if popup_label:
                    popup_label = "&nbsp;" + popup_label
            elif "<font" in line_contents:
                node_content = str(INFOS.return_node_content(get_node_content(view, flags), folder=folder))
                ind1 = node_content.find('\\n')
                popup_label = cgi.escape(node_content[ind1 + 4:-12]).replace("\\n", "<br>")
                if popup_label:
                    popup_label = "&nbsp;" + popup_label
            elif "<label" in line_contents or "<property" in line_contents or "<altlabel" in line_contents or "localize" in line_contents:
                popup_label = INFOS.return_label(selected_content)
            if "<color" in line_contents or "color>" in line_contents or "[color" in line_contents or "<value" in line_contents:
                if not popup_label:
                    for item in INFOS.color_list:
                        if item["name"] == selected_content:
                            color_hex = "#" + item["content"][2:]
                            cont_color = get_cont_col(color_hex)
                            alpha_percent = round(int(item["content"][:2], 16) / (16 * 16) * 100)
                            popup_label += '%s&nbsp;<a style="background-color:%s;color:%s">%s</a> %d %% alpha<br>' % (os.path.basename(item["filename"]), color_hex, cont_color, item["content"], alpha_percent)
                    if not popup_label:
                            if all(c in string.hexdigits for c in selected_content) and len(selected_content) == 8:
                                color_hex = "#" + selected_content[2:]
                                cont_color = get_cont_col(color_hex)
                                alpha_percent = round(int(selected_content[:2], 16) / (16 * 16) * 100)
                                popup_label += '<a style="background-color:%s;color:%s">%d %% alpha</a>' % (color_hex, cont_color, alpha_percent)
            elif "<fadetime" in line_contents:
                popup_label = str(INFOS.return_node_content(get_node_content(view, flags), folder=folder))[2:-3]
            elif "<texture" in line_contents or "<alttexture" in line_contents or "<bordertexture" in line_contents or "<icon" in line_contents or "<thumb" in line_contents:
                popup_label = INFOS.get_image_info(selected_content)
            elif "<control " in line_contents:
                # todo: add positioning based on parent nodes
                popup_label = str(INFOS.return_node_content(findWord(view), folder=folder))[2:-3]
        if popup_label and self.settings.get("tooltip_delay", 0) > -1:
            sublime.set_timeout_async(lambda: self.show_tooltip(view, popup_label), self.settings.get("tooltip_delay", 0))

    def show_tooltip(self, view, tooltip_label):
        view.show_popup(tooltip_label, sublime.COOPERATE_WITH_AUTO_COMPLETE,
                        location=-1, max_width=self.settings.get("tooltip_width", 1000), max_height=self.settings.get("height", 300), on_navigate=lambda label_id, view=view: jump_to_label_declaration(view, label_id))

    def on_modified_async(self, view):
        if INFOS.project_path and view.file_name() and view.file_name().endswith(".xml"):
            self.is_modified = True

    def on_load_async(self, view):
        self.check_project_change()

    def on_activated_async(self, view):
        self.check_project_change()

    def on_deactivated_async(self, view):
        view.hide_popup()

    def on_post_save_async(self, view):
        if INFOS.project_path and view.file_name() and view.file_name().endswith(".xml"):
            if self.is_modified:
                if self.settings.get("auto_reload_skin", True):
                    self.is_modified = False
                    view.window().run_command("execute_builtin", {"builtin": "ReloadSkin()"})
                INFOS.reload_skin_after_save(view.file_name())
                if self.settings.get("auto_skin_check", True):
                    view.window().run_command("check_variables", {"check_type": "file"})
        if view.file_name().endswith(".po"):
            INFOS.update_labels()

    def check_project_change(self):
        if not self.settings_loaded:
            self.settings = sublime.load_settings(SETTINGS_FILE)
            INFOS.get_settings(self.settings)
            INFOS.get_builtin_label()
            self.settings_loaded = True
        view = sublime.active_window().active_view()
        if view and view.window() is not None:
            variables = view.window().extract_variables()
            if "folder" in variables:
                project_folder = variables["folder"]
                if project_folder and project_folder != self.actual_project:
                    self.actual_project = project_folder
                    log("project change detected: " + project_folder)
                    INFOS.init_addon(project_folder)
            else:
                log("Could not find folder path in project file")


class SetKodiFolderCommand(sublime_plugin.WindowCommand):

    def run(self):
        self.window.show_input_panel("Set Kodi folder", KODI_PRESET_PATH, self.set_kodi_folder, None, None)

    def set_kodi_folder(self, path):
        if os.path.exists(path):
            sublime.load_settings(SETTINGS_FILE).set("kodi_path", path)
            sublime.save_settings(SETTINGS_FILE)
        else:
            sublime.message_dialog("Folder %s does not exist." % path)


class ExecuteBuiltinPromptCommand(sublime_plugin.WindowCommand):

    def run(self):
        self.settings = sublime.load_settings(SETTINGS_FILE)
        self.window.show_input_panel("Execute builtin", self.settings.get("prev_json_builtin", ""), self.execute_builtin, None, None)

    def execute_builtin(self, builtin):
        self.settings.set("prev_json_builtin", builtin)
        self.window.run_command("execute_builtin", {"builtin": builtin})


class ExecuteBuiltinCommand(sublime_plugin.WindowCommand):

    def run(self, builtin):
        settings = sublime.load_settings(SETTINGS_FILE)
        data = '{"jsonrpc":"2.0","id":1,"method":"Addons.ExecuteAddon","params":{"addonid":"script.toolbox", "params": { "info": "builtin", "id": "%s"}}}' % builtin
        kodi_json_request(data, settings=settings)


class ReloadKodiLanguageFilesCommand(sublime_plugin.WindowCommand):

    def run(self):
        INFOS.get_settings(sublime.load_settings(SETTINGS_FILE))
        INFOS.get_builtin_label()
        INFOS.update_labels()


class QuickPanelCommand(sublime_plugin.WindowCommand):

    def is_visible(self):
        if INFOS.addon_xml_file:
            return True
        else:
            return False

    def on_done(self, index):
        if index == -1:
            return None
        self.window.open_file("%s:%i" % (self.nodes[index]["file"], self.nodes[index]["line"]), sublime.ENCODED_POSITION)

    def show_preview(self, index):
        self.window.open_file("%s:%i" % (self.nodes[index]["file"], self.nodes[index]["line"]), sublime.ENCODED_POSITION | sublime.TRANSIENT)


class ShowFontRefsCommand(QuickPanelCommand):

    def run(self):
        listitems = []
        self.nodes = []
        view = self.window.active_view()
        INFOS.update_xml_files()
        font_refs = INFOS.get_font_refs()
        self.folder = view.file_name().split(os.sep)[-2]
        for ref in font_refs[self.folder]:
            if ref["name"] == "Font_Reg28":
                listitems.append(ref["name"])
                self.nodes.append(ref)
        if listitems:
            self.window.show_quick_panel(listitems, lambda s: self.on_done(s), selected_index=0, on_highlight=lambda s: self.show_preview(s))
        else:
            sublime.message_dialog("No references found")


class SearchFileForLabelsCommand(QuickPanelCommand):

    def run(self):
        listitems = []
        self.nodes = []
        regexs = [r"\$LOCALIZE\[([0-9].*?)\]", r"(?:label|property|altlabel|label2)>([0-9].*?)<"]
        view = self.window.active_view()
        path = view.file_name()
        labels = [s["string"] for s in INFOS.string_list]
        label_ids = [s["id"] for s in INFOS.string_list]
        # view.substr(sublime.Region(0, view.size()))
        with open(path, encoding="utf8") as f:
            for i, line in enumerate(f.readlines()):
                for regex in regexs:
                    for match in re.finditer(regex, line):
                        label_id = "#" + match.group(1)
                        if label_id in label_ids:
                            index = label_ids.index(label_id)
                            listitems.append("%s (%s)" % (labels[index], label_id))
                        node = {"file": path,
                                "line": i + 1}
                        self.nodes.append(node)
        if listitems:
            self.window.show_quick_panel(listitems, lambda s: self.on_done(s), selected_index=0, on_highlight=lambda s: self.show_preview(s))
        else:
            sublime.message_dialog("No references found")


class CheckVariablesCommand(QuickPanelCommand):

    def run(self, check_type):
        INFOS.update_xml_files()
        if check_type == "variable":
            self.nodes = INFOS.check_variables()
        elif check_type == "include":
            self.nodes = INFOS.check_includes()
        elif check_type == "font":
            self.nodes = INFOS.check_fonts()
        elif check_type == "label":
            self.nodes = INFOS.check_labels()
        elif check_type == "id":
            self.nodes = INFOS.check_ids()
        elif check_type == "general":
            self.nodes = INFOS.check_values()
        elif check_type == "file":
            self.nodes = INFOS.check_file(self.window.active_view().file_name())
        listitems = []
        for item in self.nodes:
            filename = os.path.basename(item["file"])
            listitems.append([item["message"], filename + ": " + str(item["line"])])
        if listitems:
            self.window.show_quick_panel(listitems, lambda s: self.on_done(s), selected_index=0, on_highlight=lambda s: self.show_preview(s))
        elif not check_type == "file":
            sublime.message_dialog("No errors detected")


class GetInfoLabelsPromptCommand(sublime_plugin.WindowCommand):

    def run(self):
        self.settings = sublime.load_settings(SETTINGS_FILE)
        self.window.show_input_panel("Get InfoLabels (comma-separated)", self.settings.get("prev_infolabel", ""), self.show_info_label, None, None)

    def show_info_label(self, label_string):
        self.settings.set("prev_infolabel", label_string)
        words = label_string.split(",")
        labels = ', '.join('"{0}"'.format(w) for w in words)
        data = '{"jsonrpc":"2.0","method":"XBMC.GetInfoLabels","params":{"labels": [%s] },"id":1}' % labels
        result = send_json_request(data, self.settings)
        if result:
            key, value = result["result"].popitem()
            sublime.message_dialog(str(value))


class SearchForLabelCommand(sublime_plugin.WindowCommand):

    def is_visible(self):
        if INFOS.string_list:
            return True
        else:
            return False

    def run(self):
        label_list = []
        for item in INFOS.string_list:
            label_list.append(["%s (%s)" % (item["string"], item["id"]), item["comment"]])
        self.window.show_quick_panel(label_list, lambda s: self.label_search_ondone_action(s), selected_index=0)

    def label_search_ondone_action(self, index):
        if index == -1:
            return None
        view = self.window.active_view()
        scope_name = view.scope_name(view.sel()[0].b)
        label_id = int(INFOS.string_list[index]["id"][1:])
        if "text.xml" in scope_name and INFOS.addon_type == "python" and 32000 <= label_id <= 33000:
            lang_string = "$ADDON[%s %i]" % (INFOS.addon_name, label_id)
        elif "text.xml" in scope_name:
            lang_string = "$LOCALIZE[%i]" % label_id
        else:
            lang_string = label_id
        view.run_command("insert", {"characters": lang_string})


class OpenKodiLogCommand(sublime_plugin.WindowCommand):

    def run(self):
        settings = sublime.load_settings(SETTINGS_FILE)
        if sublime.platform() == "linux":
            self.log_file = os.path.join(os.path.expanduser("~"), ".%s" % APP_NAME, "temp", "%s.log" % APP_NAME)
        elif sublime.platform() == "windows":
            if settings.get("portable_mode"):
                self.log_file = os.path.join(settings.get("kodi_path"), "portable_data", "%s.log" % APP_NAME)
            else:
                self.log_file = os.path.join(os.getenv('APPDATA'), "%s" % APP_NAME, "%s.log" % APP_NAME)
        self.window.open_file(self.log_file)


class OpenSourceFromLog(sublime_plugin.TextCommand):

    def run(self, edit):
        for region in self.view.sel():
            if region.empty():
                line = self.view.line(region)
                line_contents = self.view.substr(line)
                ma = re.search('File "(.*?)", line (\d*), in .*', line_contents)
                if ma:
                    target_filename = ma.group(1)
                    target_line = ma.group(2)
                    sublime.active_window().open_file("%s:%s" % (target_filename, target_line), sublime.ENCODED_POSITION)
                    return
                ma = re.search(r"', \('(.*?)', (\d+), (\d+), ", line_contents)
                if ma:
                    target_filename = ma.group(1)
                    target_line = ma.group(2)
                    target_col = ma.group(3)
                    sublime.active_window().open_file("%s:%s:%s" % (target_filename, target_line, target_col), sublime.ENCODED_POSITION)
                    return
            else:
                self.view.insert(edit, region.begin(), self.view.substr(region))


class PreviewImageCommand(sublime_plugin.TextCommand):

    def is_visible(self):
        if INFOS.media_path():
            flags = sublime.CLASS_WORD_START | sublime.CLASS_WORD_END
            content = get_node_content(self.view, flags)
            if "/" in content or "\\" in content:
                return True
        return False

    def run(self, edit):
        flags = sublime.CLASS_WORD_START | sublime.CLASS_WORD_END
        path = get_node_content(self.view, flags)
        imagepath = INFOS.translate_path(path)
        if os.path.exists(imagepath):
            if os.path.isdir(imagepath):
                self.files = []
                for (dirpath, dirnames, filenames) in os.walk(imagepath):
                    self.files.extend(filenames)
                    break
                self.files = [imagepath + s for s in self.files]
            else:
                self.files = [imagepath]
            sublime.active_window().show_quick_panel(self.files, lambda s: self.on_done(s), selected_index=0, on_highlight=lambda s: self.show_preview(s))

    def on_done(self, index):
        sublime.active_window().focus_view(self.view)

    def show_preview(self, index):
        if index >= 0:
            file_path = self.files[index]
            sublime.active_window().open_file(file_path, sublime.TRANSIENT)


class GoToTagCommand(sublime_plugin.WindowCommand):

    def run(self):
        flags = sublime.CLASS_WORD_START | sublime.CLASS_WORD_END
        view = self.window.active_view()
        keyword = get_node_content(view, flags)
        folder = view.file_name().split(os.sep)[-2]
        position = INFOS.go_to_tag(keyword, folder)
        if position:
            self.window.open_file(position, sublime.ENCODED_POSITION)


class SearchForImageCommand(sublime_plugin.TextCommand):

    def is_visible(self):
        if INFOS.media_path():
            return True
        else:
            return False

    def run(self, edit):
        path, filename = os.path.split(self.view.file_name())
        self.imagepath = INFOS.media_path()
        if not self.imagepath:
            log("Could not find file " + self.imagepath)
        self.files = []
        for path, subdirs, files in os.walk(self.imagepath):
            if "studio" in path or "recordlabel" in path:
                continue
            for filename in files:
                image_path = os.path.join(path, filename).replace(self.imagepath, "").replace("\\", "/")
                if image_path.startswith("/"):
                    image_path = image_path[1:]
                self.files.append(image_path)
        sublime.active_window().show_quick_panel(self.files, lambda s: self.on_done(s), selected_index=0, on_highlight=lambda s: self.show_preview(s))

    def on_done(self, index):
        items = ["Insert path", "Open Image"]
        if index >= 0:
            sublime.active_window().show_quick_panel(items, lambda s: self.insert_char(s, index), selected_index=0)
        else:
            sublime.active_window().focus_view(self.view)

    def insert_char(self, index, fileindex):
        if index == 0:
            self.view.run_command("insert", {"characters": self.files[fileindex]})
        elif index == 1:
            os.system("start " + os.path.join(self.imagepath, self.files[fileindex]))
        sublime.active_window().focus_view(self.view)

    def show_preview(self, index):
        if index >= 0:
            file_path = os.path.join(self.imagepath, self.files[index])
        sublime.active_window().open_file(file_path, sublime.TRANSIENT)


class SearchForFontCommand(sublime_plugin.TextCommand):

    def is_visible(self):
        if INFOS.fonts:
            return True
        else:
            return False

    def run(self, edit):
        self.font_entries = []
        folder = self.view.file_name().split(os.sep)[-2]
        for node in INFOS.fonts[folder]:
            string_array = [node["name"], node["size"] + "  -  " + node["filename"]]
            self.font_entries.append(string_array)
        sublime.active_window().show_quick_panel(self.font_entries, lambda s: self.on_done(s), selected_index=0)

    def on_done(self, index):
        if index >= 0:
            self.view.run_command("insert", {"characters": self.font_entries[index][0]})
        sublime.active_window().focus_view(self.view)


class GoToOnlineHelpCommand(sublime_plugin.TextCommand):

    def is_visible(self):
        region = self.view.sel()[0]
        line_contents = self.view.substr(self.view.line(region))
        scope_name = self.view.scope_name(region.b)
        return "text.xml" in scope_name and "<control " in line_contents

    def run(self, edit):
        controls = {"group": "http://kodi.wiki/view/Group_Control",
                    "grouplist": "http://kodi.wiki/view/Group_List_Control",
                    "label": "http://kodi.wiki/view/Label_Control",
                    "fadelabel": "http://kodi.wiki/view/Fade_Label_Control",
                    "image": "http://kodi.wiki/view/Image_Control",
                    "largeimage": "http://kodi.wiki/view/Large_Image_Control",
                    "multiimage": "http://kodi.wiki/view/MultiImage_Control",
                    "button": "http://kodi.wiki/view/Button_control",
                    "radiobutton": "http://kodi.wiki/view/Radio_button_control",
                    "selectbutton": "http://kodi.wiki/view/Group_Control",
                    "togglebutton": "http://kodi.wiki/view/Toggle_button_control",
                    "multiselect": "http://kodi.wiki/view/Multiselect_control",
                    "spincontrol": "http://kodi.wiki/view/Spin_Control",
                    "spincontrolex": "http://kodi.wiki/view/Settings_Spin_Control",
                    "progress": "http://kodi.wiki/view/Progress_Control",
                    "list": "http://kodi.wiki/view/List_Container",
                    "wraplist": "http://kodi.wiki/view/Wrap_List_Container",
                    "fixedlist": "http://kodi.wiki/view/Fixed_List_Container",
                    "panel": "http://kodi.wiki/view/Text_Box",
                    "rss": "http://kodi.wiki/view/RSS_feed_Control",
                    "visualisation": "http://kodi.wiki/view/Visualisation_Control",
                    "videowindow": "http://kodi.wiki/view/Video_Control",
                    "edit": "http://kodi.wiki/view/Edit_Control",
                    "epggrid": "http://kodi.wiki/view/EPGGrid_control",
                    "mover": "http://kodi.wiki/view/Mover_Control",
                    "resize": "http://kodi.wiki/view/Resize_Control"
                    }
        # control_types = "|".join(controls.keys())
        region = self.view.sel()[0]
        line = self.view.line(region)
        line_contents = self.view.substr(line)
        try:
            root = ET.fromstring(line_contents + "</control>")
            control_type = root.attrib["type"]
            webbrowser.open_new(controls[control_type])
        except:
            log("error when trying to open from %s" % line_contents)


class MoveToLanguageFile(sublime_plugin.TextCommand):

    def is_visible(self):
        scope_name = self.view.scope_name(self.view.sel()[0].b)
        if INFOS.project_path and INFOS.addon_lang_path:
            if "text.xml" in scope_name or "source.python" in scope_name:
                if self.view.sel()[0].b != self.view.sel()[0].a:
                    return True
        return False

    def run(self, edit):
        available_ids = []
        self.labels = []
        self.label_ids = []
        region = self.view.sel()[0]
        if region.begin() == region.end():
            sublime.message_dialog("Please select the complete label")
            return False
        word = self.view.substr(region)
        for label in INFOS.string_list:
            if label["string"].lower() == word.lower():
                available_ids.append(label)
                self.labels.append(["%s (%s)" % (label["string"], label["id"]), label["comment"]])
                self.label_ids.append(label["id"])
        if available_ids:
            self.labels.append("Create new label")
            sublime.active_window().show_quick_panel(self.labels, lambda s: self.on_done(s, region), selected_index=0)
        else:
            label_id = self.create_new_label(word)
            self.view.run_command("replace_text", {"label_id": label_id})

    def on_done(self, index, region):
        if index == -1:
            return None
        if self.labels[index] == "Create new label":
            label_id = self.create_new_label(self.view.substr(region))
        else:
            label_id = self.label_ids[index][1:]
        self.view.run_command("replace_text", {"label_id": label_id})

    def create_new_label(self, word):
        if INFOS.addon_type == "skin":
            start_id = 31000
            index_offset = 0
        else:
            start_id = 32000
            index_offset = 2
        po = polib.pofile(INFOS.addon_lang_path)
        string_ids = []
        for i, entry in enumerate(po):
            try:
                string_ids.append(int(entry.msgctxt[1:]))
            except:
                string_ids.append(entry.msgctxt)
        for label_id in range(start_id, start_id + 1000):
            if label_id not in string_ids:
                log("first free: " + str(label_id))
                break
        msgstr = "#" + str(label_id)
        new_entry = polib.POEntry(msgid=word, msgstr="", msgctxt=msgstr)
        po_index = int(label_id) - start_id + index_offset
        po.insert(po_index, new_entry)
        po.save(INFOS.addon_lang_path)
        INFOS.update_labels()
        return label_id


class ReplaceTextCommand(sublime_plugin.TextCommand):

    def run(self, edit, label_id):
        for region in self.view.sel():
            scope_name = self.view.scope_name(region.b)
            label_id = int(label_id)
            if "text.xml" in scope_name and INFOS.addon_type == "python" and 32000 <= label_id <= 33000:
                new = "$ADDON[%s %i]" % (INFOS.addon_name, label_id)
            elif "text.xml" in scope_name:
                new = "$LOCALIZE[%i]" % label_id
            else:
                new = str(label_id)
            self.view.replace(edit, region, new)


class CreateElementRowCommand(sublime_plugin.WindowCommand):

    def run(self):
        self.window.show_input_panel("Enter number of items to generate", "1", on_done=self.generate_items, on_change=None, on_cancel=None)

    def generate_items(self, num_items):
        self.window.run_command("replace_xml_elements", {"num_items": num_items})


class ReplaceXmlElementsCommand(sublime_plugin.TextCommand):

    def run(self, edit, num_items):
        selected_text = self.view.substr(self.view.sel()[0])
        # new_text = selected_text + "\n"
        new_text = ""
        for i in range(1, int(num_items) + 1):
            new_text = new_text + selected_text.replace("[X]", str(i)) + "\n"
            i += 1
        for region in self.view.sel():
            self.view.replace(edit, region, new_text)
            break


class SwitchXmlFolderCommand(sublime_plugin.TextCommand):

    def is_visible(self):
        return len(INFOS.xml_folders) > 1

    def run(self, edit):
        self.element = None
        self.file = self.view.file_name()
        root = get_root_from_file(self.file)
        tree = ET.ElementTree(root)
        line, column = self.view.rowcol(self.view.sel()[0].b)
        elements = [e for e in tree.iter()]
        for e in elements:
            if line < e.sourceline:
                self.element = e
                break
    # if len(INFOS.xml_folders) > 2:
        sublime.active_window().show_quick_panel(INFOS.xml_folders, lambda s: self.on_done(s), selected_index=0, on_highlight=lambda s: self.show_preview(s))

    def show_preview(self, index):
        path = os.path.join(INFOS.project_path, INFOS.xml_folders[index], os.path.basename(self.file))
        sublime.active_window().open_file("%s:%i" % (path, self.element.sourceline), sublime.ENCODED_POSITION | sublime.TRANSIENT)
        # sublime.active_window().focus_view(self.view)

    def on_done(self, index):
        if index == -1:
            return None
        path = os.path.join(INFOS.project_path, INFOS.xml_folders[index], os.path.basename(self.file))
        sublime.active_window().open_file("%s:%i" % (path, self.element.sourceline), sublime.ENCODED_POSITION)

# def plugin_loaded():
#     INFOS.check_project_change()
