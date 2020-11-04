# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" TemplateManager """
import os
from functools import lru_cache

import web
from jinja2 import Environment, FileSystemLoader, select_autoescape
import inginious
import json

class TemplateHelper(object):
    """ Class accessible from templates that calls function defined in the Python part of the code. """

    # _WEB_CTX_KEY is the name of the key in web.ctx that stores entries made available to the whole
    # current thread. It allows to store javascript/css "addons" that will be displayed later when the
    # templates are rendered
    _WEB_CTX_KEY = "inginious_tpl_helper"

    def __init__(self, plugin_manager, user_manager, default_template_dir, default_layout, default_layout_lti, use_minified=True):
        """
        Init the Template Helper
        :param plugin_manager: an instance of a PluginManager
        :param user_manager: an instance of UserManager. Can be None; in this case, LTI layout detection will never be used.
        :param default_template_dir: the path to the template dir. If it is not absolute, it will be taken from the root of the inginious package.
        :param default_layout: the path to the layout. If it is not absolute, it will be taken from the root of the inginious package.
        :param default_layout_lti: same but for the lti layout
        :param use_minified: weither to use minified js/css or not. Use True in production, False in dev envs.
        """

        self._base_helpers = {"header_hook": (lambda **kwargs: self._generic_hook('header_html', **kwargs)),
                              "main_menu": (lambda **kwargs: self._generic_hook('main_menu', **kwargs)),
                              "course_menu": (lambda **kwargs: self._generic_hook('course_menu', **kwargs)),
                              "task_menu": (lambda **kwargs: self._generic_hook('task_menu', **kwargs)),
                              "welcome_text": (lambda **kwargs: self._generic_hook('welcome_text', **kwargs)),
                              "javascript_header": (lambda **_: self._javascript_helper("header")),
                              "javascript_footer": (lambda **_: self._javascript_helper("footer")),
                              "css": (lambda **_: self._css_helper())}
        self._plugin_manager = plugin_manager
        self._template_dir = default_template_dir
        self._user_manager = user_manager # can be None!
        self._layout = default_layout
        self._layout_lti = default_layout_lti
        self._template_globals = {}

        # include is only needed in webpy templates as jinja supports it by default
        self.add_to_template_globals("include", self.get_custom_renderer(self._template_dir, layout=False))

        self.add_to_template_globals("template_helper", self)
        self.add_to_template_globals("plugin_manager", plugin_manager)
        self.add_to_template_globals("use_minified", use_minified)
        self.add_to_template_globals("is_lti", self.is_lti)
        self.add_to_template_globals("json", self._json_safe_dump)

    def is_lti(self):
        """ True if the current session is an LTI one """
        return self._user_manager is not None and self._user_manager.session_lti_info() is not None

    def add_to_template_globals(self, name, value):
        """ Add a variable to will be accessible in the templates """
        self._template_globals[name] = value

    def render(self, path, base_template_folder=None, **tpl_kwargs):
        """
        Parse the Jinja template named "path" and render it with args *tpl_args and **tpl_kwargs
        :param path: Path of the template, relative to the base folder
        :param base_template_folder: base folder. If none, the base template folder is used. Use functools.partial to
            create custom renderers.
        :param tpl_kwargs: named args sent to the template
        :return: the rendered template, as a str
        """
        return self._get_jinja_renderer(base_template_folder).get_template(path).render(**tpl_kwargs)

    @lru_cache(None)
    def _get_jinja_renderer(self, base_template_folder=None):
        if base_template_folder is None:
            base_template_folder = self._template_dir
        # if base_template_folder is not an absolute path, take it wrt INGInious root folder
        base_template_folder = os.path.join(inginious.get_root_path(), base_template_folder)

        env = Environment(loader=FileSystemLoader(base_template_folder),
                          autoescape=select_autoescape(['html', 'htm', 'xml']))
        env.globals.update(self._template_globals)

        return env

    def get_renderer(self, with_layout=True):
        """ Get the default renderer. This function is deprecated, use render() (that uses Jinja) instead. """
        if with_layout and self.is_lti():
            return self.get_custom_renderer(self._template_dir, layout=self._layout_lti)
        elif with_layout:
            return self.get_custom_renderer(self._template_dir)
        else:
            return self.get_custom_renderer(self._template_dir, layout=False)

    def get_custom_renderer(self, dir_path, layout=True):
        """
        Create a template renderer on templates in the directory specified, and returns it.

        See the web.py documentation.
        This function is deprecated, use render() (that uses Jinja) instead.

        :param dir_path: the path to the template dir. If it is not absolute, it will be taken from the root of the inginious package.
        :param layout: can either be True (use the base layout of the running app), False (use no layout at all), or the path to the layout to use.
                       If this path is relative, it is taken from the INGInious package root.
        """

        # if dir_path/base is a absolute path, os.path.join(something, an_absolute_path) returns an_absolute_path.
        root_path = inginious.get_root_path()

        if isinstance(layout, str):
            layout_path = os.path.join(root_path, layout)
        elif layout is True:
            layout_path = os.path.join(root_path, self._layout)
        else:
            layout_path = None

        return web.template.render(os.path.join(root_path, dir_path),
                                  globals=self._template_globals,
                                  base=layout_path)

    def call(self, name, **kwargs):
        helpers = dict(list(self._base_helpers.items()) + self._plugin_manager.call_hook("template_helper"))
        if helpers.get(name, None) is None:
            return ""
        else:
            return helpers[name](**kwargs)

    def add_javascript(self, link, position="footer"):
        """ Add a javascript file to load. Position can either be "header" or "footer" """
        self._get_ctx()["javascript"][position].append(link)

    def add_css(self, link):
        """ Add a css file to load """
        self._get_ctx()["css"].append(link)

    def add_other(self, name, func):
        """ Add another callback to the template helper """
        self._base_helpers[name] = func

    def _javascript_helper(self, position):
        """ Add javascript links for the current page and for the plugins """
        if position not in ["header", "footer"]:
            position = "footer"

        # Load javascript files from plugins
        if position == "header":
            entries = [entry for entry in self._plugin_manager.call_hook("javascript_header") if entry is not None]
        else:
            entries = [entry for entry in self._plugin_manager.call_hook("javascript_footer") if entry is not None]
        # Load javascript for the current page
        entries += self._get_ctx()["javascript"][position]
        entries = ["<script src='" + entry + "' type='text/javascript' charset='utf-8'></script>" for entry in entries]
        return "\n".join(entries)

    def _css_helper(self):
        """ Add CSS links for the current page and for the plugins """
        entries = [entry for entry in self._plugin_manager.call_hook("css") if entry is not None]
        # Load javascript for the current page
        entries += self._get_ctx()["css"]
        entries = ["<link href='" + entry + "' rel='stylesheet'>" for entry in entries]
        return "\n".join(entries)

    def _get_ctx(self):
        """ Get web.ctx object for the Template helper """
        if self._WEB_CTX_KEY not in web.ctx:
            web.ctx[self._WEB_CTX_KEY] = {
                "javascript": {"footer": [], "header": []},
                "css": []}
        return web.ctx.get(self._WEB_CTX_KEY)

    def _generic_hook(self, name, **kwargs):
        """ A generic hook that links the TemplateHelper with PluginManager """
        entries = [entry for entry in self._plugin_manager.call_hook(name, **kwargs) if entry is not None]
        return "\n".join(entries)

    def _json_safe_dump(self, data):
        """ Make a json dump of `data`, that can be used directly in a `<script>` tag. Available as json() inside templates """
        return json.dumps(data).replace(u'<', u'\\u003c') \
            .replace(u'>', u'\\u003e') \
            .replace(u'&', u'\\u0026') \
            .replace(u"'", u'\\u0027')