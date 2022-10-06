# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""


import json
import lxml
import os
import pymysql
import requests
import sqlite3
import yaml
import subprocess

import flask

from datetime import timedelta

from flask import (
    g,
    Flask,
    Response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)


from flask_login import current_user

from jinja2 import TemplateNotFound
from datetime import datetime
from dora.user import User

from .xml import parse_xml

from .om4 import *
from .diffmaps import *
from .auth import *
from .api import *
from .extpkg import *
from .globals import *
from .paramdiff import *
from .projects import *
from .experiments import *
from .scalar import *
from .stats import *
from .user import user_experiment_count
from .usertools import *
from .parameters import *

# App modules
from dora import dora


@dora.before_request
def before_request():
    flask.session.permanent = True
    dora.permanent_session_lifetime = timedelta(hours=10)
    flask.session.modified = False


# App main route + generic routing
@dora.route("/", defaults={"path": "index.html"}, methods=["GET"])
@dora.route("/<path>", methods=["GET"])
def index(path):
    try:
        # Serve the file (if exists) from dora/templates/FILE.html
        if current_user.is_authenticated:
            user_params = {
                "username": current_user.name,
                "userpic": current_user.profile_pic,
            }
        else:
            user_params = {"username": "", "userpic": ""}

        try:
            result = render_template(path, **user_params)
        except Exception as e:
            return "Site is under maintenance. " + str(e)

        return result

    except TemplateNotFound:
        return render_template("page-404.html"), 404


@dora.route("/profile/")
@login_required
def show_user():
    username = current_user.firstlast
    numexp = user_experiment_count(username)
    db = get_db()
    cursor = db.cursor()
    sql = f"SELECT id,expName from master where userName='{username}' or owner='{username}'"
    cursor.execute(sql)
    result = cursor.fetchall()
    print(current_user.firstlast)
    return render_template(
        "profile.html", numexp=numexp, tables=["aaa"], experiments=result
    )


@dora.route("/backup")
def dump_database():
    cmd = f"mysqldump {os.environ['DB_DATABASE']} -h {os.environ['DB_HOSTNAME']} -u {os.environ['DB_USERNAME']} --password={os.environ['DB_PASSWORD']}"
    output = subprocess.check_output(cmd.split(" "))
    output = output.decode()
    return Response(output, mimetype="text/plain")


@dora.teardown_appcontext
def teardown_db(exception):
    db = g.pop("db", None)

    if db is not None:
        db.close()


if __name__ == "__main__":
    dora.run(ssl_context="adhoc")
