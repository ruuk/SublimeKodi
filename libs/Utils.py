import os
from lxml import etree as ET


def checkPaths(paths):
    for path in paths:
        if os.path.exists(path):
            log("found path: %s" % path)
            return path
    return ""


def findWord(view):
    for region in view.sel():
        if region.begin() == region.end():
            word = view.word(region)
        else:
            word = region
        if not word.empty():
            return view.substr(word)
        else:
            return ""


def jump_to_label_declaration(view, label_id):
    view.run_command("insert", {"characters": label_id})
    view.hide_popup()


def log(string):
    print("SublimeKodi: " + string)


def get_tags_from_file(path):
    nodes = []
    if os.path.exists(path):
        parser = ET.XMLParser(remove_blank_text=True)
        tree = ET.parse(path, parser)
        root = tree.getroot()
        for node in root.findall(path):
            if "name" in node.attrib:
                include = {"name": node.attrib["name"],
                           "file": path,
                           "line": node.sourceline}
                nodes.append(include)
    return nodes