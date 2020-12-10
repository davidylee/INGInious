# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Course page """
import web

from inginious.frontend.pages.utils import INGIniousAuthPage

def handle_course_unavailable(app_homepath, template_helper, user_manager, course):
    """ Displays the course_unavailable page or the course registration page """
    reason = user_manager.course_is_open_to_user(course, lti=False, return_reason=True)
    if reason == "unregistered_not_previewable":
        username = user_manager.session_username()
        user_info = user_manager.get_user_info(username)
        if course.is_registration_possible(user_info):
            raise web.seeother(app_homepath + "/register/" + course.get_id())
    return template_helper.render("course_unavailable.html", reason=reason)


class CoursePage(INGIniousAuthPage):
    """ Course page """

    def preview_allowed(self, courseid):
        course = self.get_course(courseid)
        return course.get_accessibility().is_open() and course.allow_preview()

    def get_course(self, courseid):
        """ Return the course """
        try:
            course = self.course_factory.get_course(courseid)
        except:
            raise self.app.notfound(message=_("Course not found."))

        return course

    def POST_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ POST request """
        course = self.get_course(courseid)

        user_input = web.input()
        if "unregister" in user_input and course.allow_unregister():
            self.user_manager.course_unregister_user(course, self.user_manager.session_username())
            raise web.seeother(self.app.get_homepath() + '/mycourses')

        return self.show_page(course)

    def GET_AUTH(self, courseid):  # pylint: disable=arguments-differ
        """ GET request """
        course = self.get_course(courseid)
        return self.show_page(course)

    def show_page(self, course):
        """ Prepares and shows the course page """
        username = self.user_manager.session_username()
        if not self.user_manager.course_is_open_to_user(course, lti=False):
            return handle_course_unavailable(self.app.get_homepath(), self.template_helper, self.user_manager, course)
        else:
            tasks = course.get_tasks()

            # Get 5 last submissions
            last_submissions = []
            for submission in self.submission_manager.get_user_last_submissions(5, {"courseid": course.get_id(), "taskid": {"$in": list(tasks.keys())}}):
                if self.user_manager.task_is_visible_by_user(tasks[submission['taskid']], username, False):
                    submission["taskname"] = tasks[submission['taskid']].get_name(self.user_manager.session_language())
                    last_submissions.append(submission)

            # Compute course/tasks scores
            tasks_data = {}
            user_tasks = self.database.user_tasks.find({"username": username, "courseid": course.get_id(), "taskid": {"$in": list(tasks.keys())}})
            is_admin = self.user_manager.has_staff_rights_on_course(course, username)
            tasks_score = [0.0, 0.0]

            for taskid, task in tasks.items():
                tasks_data[taskid] = {"visible": self.user_manager.task_is_visible_by_user(task, username, False), "succeeded": False,
                                      "grade": 0.0}
                tasks_score[1] += task.get_grading_weight() if tasks_data[taskid]["visible"] else 0

            for user_task in user_tasks:
                tasks_data[user_task["taskid"]]["succeeded"] = user_task["succeeded"]
                tasks_data[user_task["taskid"]]["grade"] = user_task["grade"]

                weighted_score = user_task["grade"]*tasks[user_task["taskid"]].get_grading_weight()
                tasks_score[0] += weighted_score if tasks_data[user_task["taskid"]]["visible"] else 0

            course_grade = round(tasks_score[0]/tasks_score[1]) if tasks_score[1] > 0 else 0

            # Get tag list
            tag_list = course.get_tags()

            # Get user info
            user_info = self.user_manager.get_user_info(username)

            return self.template_helper.get_renderer().course(user_info, course, last_submissions, tasks_data, course_grade, tag_list)
