#!/usr/bin/python
#-*- encoding: utf-8 -*-


import sublime
import sublime_plugin
import threading
import styled_popup
import urllib.request as request
import urllib.parse  as urlparse
from copy import deepcopy
from xml.dom.minidom import parseString

class TrsInfo(object):
    word = ""
    trans = ""
    web_trans = ""
    phonetic = ""

class Youdao(object):

    def __init__(self):
        self._trs_info = TrsInfo()

    def _init_trs(self):
        self._trs_info.word = ""
        self._trs_info.trans = "没有找到相关的汉英互译结果。"
        self._trs_info.web_trans = ""
        self._trs_info.phonetic = ""

    def auto_translate(self, words):
        self._init_trs()
        self._trs_info.word = words
        words = words.replace("_", " ")
        url = "http://dict.youdao.com/search"
        data = {"keyfrom" : "deskdict.mini", "q" : words, "doctype" : "xml", "xmlVersion" : 8.2,
                "client" : "deskdict", "id" : "fef0101011fbaf8c", "vendor": "unknown", 
                "in" : "YoudaoDict", "appVer" : "5.4.46.5554", "appZengqiang" : 0, "le" : "eng", "LTH" : 140}

        url = "%s?%s" % (url, urlparse.urlencode(data));
        req = request.Request(url)
        req.add_header('User-Agent','Youdao Desktop Dict (Windows 6.1.7601)')
        sublime.status_message(url)
        try:
            ret = request.urlopen(req, timeout=10).read()
        except Exception as e:
            sublime.status_message(e)
            return self._trs_info
        dom = parseString(ret)
        web_trans = self.parser_web_trans(dom)
        simple_dict_nodes = dom.getElementsByTagName("simple-dict")
        if not simple_dict_nodes:
            if web_trans:
                self._trs_info.trans = web_trans
            return self._trs_info
        simple_dict_node = simple_dict_nodes[0]
        trs = self.parse_trs(simple_dict_node) 
        if not trs:
            return self._trs_info
        self._trs_info.trans = trs
        self._trs_info.phonetic = self.parse_phonetic(simple_dict_node)
        return self._trs_info

    def parser_web_trans(self, node):
        web_nodes = node.getElementsByTagName("web-translation")
        if not web_nodes:
            return ""   
        value_nodes = web_nodes[0].getElementsByTagName("value")
        if not value_nodes:
            return ""
        return "<br>".join([node.firstChild.wholeText for node in value_nodes if node.firstChild])

    def get_node_text(self, node, tag):
        nodes = node.getElementsByTagName(tag)
        if not nodes:
            return ""
        if not nodes[0].firstChild:
            return ""
        return nodes[0].firstChild.wholeText

    def parse_phonetic(self, node):
        phonetics = ""
        ukphone = self.get_node_text(node, "ukphone")
        if ukphone: phonetics  += "英[%s] " % ukphone
        usphone = self.get_node_text(node, "usphone")
        if usphone: phonetics += "美[%s]" % usphone
        phone = self.get_node_text(node, "phone")
        if phone: phonetics += "[%s]" % phone
        return phonetics

    def parse_trs(self, node):
        if not node:
            return ""
        trs_node = node.getElementsByTagName("trs") 
        if not trs_node:
            return ""
        i_nodes = trs_node[0].getElementsByTagName("i")
        try:
            ret_string = "<br>".join([node.firstChild.wholeText for node in i_nodes if node.firstChild])
        except Exception:
            ret_string = ""
        return ret_string           


youdao = Youdao()
global_thread_flag = 1

class ThreadRun(threading.Thread):
    '''class docs'''
    def __init__(self,fetch_func, render_func, args=[], render_args=[], thread_flag=0):
        '''init docs'''
        super(ThreadRun, self).__init__()
        self.setDaemon(True)
        self.fetch_func = fetch_func
        self.render_func = render_func
        self.args = args
        self.render_args = render_args
        self.thread_flag = thread_flag

    def run(self):
        if self.args:
            result = self.fetch_func(*self.args)
        else:    
            result = self.fetch_func()
         
        if self.thread_flag != global_thread_flag:
            return

        if self.render_args:    
            self.render_func(result, *self.render_args)
        else:    
            self.render_func(result)



class AutoTranslateCommand(sublime_plugin.WindowCommand):

    @property
    def current_word(self):
        view = self.window.active_view()
        current_region = view.sel()[0]
        if current_region.a != current_region.b:
            return view.substr(current_region)
        word = view.word(current_region)
        return view.substr(word)

    # encode
    def run(self):
        global global_thread_flag
        global_thread_flag += 1
        flag = deepcopy(global_thread_flag)
        ThreadRun(youdao.auto_translate, self.render_popup, [self.current_word], thread_flag=flag).start()


    def render_popup(self, trs_info):
        html = """<span class="keyword">{t.word}</span> <span class="storage type">{t.phonetic}</span><br><br><span class="string quoted">{t.trans}</span><br>""".format(t=trs_info)
        styled_popup.show_popup(self.window.active_view(), html)       
