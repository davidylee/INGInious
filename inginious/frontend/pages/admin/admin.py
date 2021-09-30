# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Admin index page"""
import json

import flask
from flask import redirect, request
from inginious.frontend.pages.utils import INGIniousAdministratorPage


class AdministrationPage(INGIniousAdministratorPage):

    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ Display admin page """
        return self.show_page()

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ Display admin page """
        return self.show_page()

    def show_page(self):
        return self.template_helper.render("admin/admin_page.html")


class AdministrationUsersPage(INGIniousAdministratorPage):
    def GET_AUTH(self):  # pylint: disable=arguments-differ
        """ Display admin users page """
        return self.show_page()

    def POST_AUTH(self):  # pylint: disable=arguments-differ
        """ Display admin users page """
        return self.show_page()

    def show_page(self):
        all_users = self.user_manager.get_users()
        return self.template_helper.render("admin/admin_users.html", all_users=all_users)


class AdministrationUserActionPage(INGIniousAdministratorPage):
    def POST(self):
        username = request.form.get("username")
        activate_hash = self.user_manager.get_user_activate_hash(username)
        action = request.form.get("action")
        if action == "activate":
            self.user_manager.activate_user(activate_hash)
        elif action == "delete":
            print("COUCOU DELETE")
            self.user_manager.delete_user(username)
        return redirect("/administrator/users")


class AdministrationUserAddPage(INGIniousAdministratorPage):
    def GET(self):
        return self.template_helper.render("admin/admin_add_user.html")

    def POST(self):
        data = request.form  # a multidict containing POST data
        username = data["username"]
        realname = data["realname"]
        email = data["email"]
        password = data["password"]
        import hashlib
        feedback = self.user_manager.create_user({
                "username": username,
                "realname": realname,
                "email": email,
                "password": hashlib.sha512(password.encode("utf-8")).hexdigest(),
                "bindings": {},
                "language": "en"})
        if feedback:
            all_users = self.user_manager.get_users()
            return self.template_helper.render("admin/admin_users.html", all_users=all_users, feedback=feedback)
        return redirect("/administrator/users")
