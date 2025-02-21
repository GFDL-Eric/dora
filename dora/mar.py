"""mar.py : module to execute jupyter notebooks"""

import base64
import datetime
import glob
import io
import os
import subprocess
import traceback
from io import BytesIO
from operator import itemgetter

import gfdlnb
import matplotlib.pyplot as plt
import nbformat
import om4labs
from flask import Response, render_template, request, send_file
from IPython.display import Image, display
from nbconvert.preprocessors import ExecutePreprocessor

from dora import dora
from flask_login import current_user

from .Experiment import Experiment
from .frepptools import Filegroup, in_daterange, optimize_filegroup_selection

# This environment variable prevents annoying error messages when running
# the Jupyter notebook preprocessor
os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"

import re


# This function makes a nicer formatted error should a notebook fail
def clean_exception_string(exception_str):
    # Remove ANSI color codes
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    cleaned_str = ansi_escape.sub("", exception_str)

    # Split the string into lines
    lines = cleaned_str.split("\n")

    # Remove the ASCII box around the code
    if "-----------------" in lines:
        start = lines.index("-----------------")
        end = lines[start + 1 :].index("-----------------") + start + 1
        code_lines = lines[start + 1 : end]
        lines = lines[:start] + code_lines + lines[end + 1 :]

    # Remove extra whitespace
    lines = [line.strip() for line in lines if line.strip()]

    # Join the lines back together
    cleaned_str = "\n".join(lines)

    return cleaned_str


# Example usage:
# cleaned_exception = clean_exception_string(your_exception_string)
class CaptureFigurePreprocessor(ExecutePreprocessor):
    def __init__(self, envvars=None, *args, **kwargs):
        if envvars is not None:
            custom_env = {**os.environ, **envvars}
        else:
            custom_env = os.environ.copy()
        super().__init__(*args, **kwargs, env=custom_env)
        self.captured_figures = []  # To store captured figures

    def preprocess(self, nb, resources=None):
        return super().preprocess(nb, resources)

    def preprocess_cell(self, cell, resources, cell_index):
        outputs = super().preprocess_cell(cell, resources, cell_index)
        # Check for and capture figure output
        for output in cell.get("outputs", []):
            if output.output_type == "execute_result":
                for data in output.data.get("image/png", []):
                    img_data = BytesIO(base64.b64decode(data))
                    fig = plt.figure()
                    ax = fig.add_subplot(111)
                    ax.imshow(plt.imread(img_data))
                    ax.axis("off")  # Hide axes
                    self.captured_figures.append(fig)
        return outputs


class StopExecutionPreprocessor(ExecutePreprocessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_executed_cell = -1

    def preprocess_cell(self, cell, resources, cell_index):
        if "stop_here" in cell.metadata.get("tags", []):
            raise ValueError("Stopping execution", "stop_here tag found", "")
        result = super().preprocess_cell(cell, resources, cell_index)
        self.last_executed_cell = cell_index
        return result


@dora.route("/analysis/mar", methods=["GET"])
def mar_execute():
    """Flask route for calling MAR

    Returns
    -------
    Jinja template name and variables for rendering
    """

    # Get the experiment ID number from the URL or provide user with
    # a form to enter a post-processing path directly
    idnum = request.args.get("id")
    if idnum is None:
        return render_template("mar-splash.html")

    # Multiple experiments may be specified by separating with a
    # comma. Break them apart at this step
    idnums = str(idnum).split(",")

    # Fetch an Experiment object that houses all of the
    # experiment metadata
    experiments = [Experiment(x) for x in idnums]

    # Make sure the experiment is valid
    for n, experiment in enumerate(experiments):
        if len(experiment.to_dict()) == 0:
            return render_template(
                "page-500.html",
                msg=f"Experiment does not exist in database: {idnums[n]}",
            )
        if experiment.validate_path("pathPP") is False:
            return render_template(
                "page-500.html", msg=f"Unable to reach {experiment.pathPP}."
            )

    # Get the requested analysis from the URL or provide user with
    # a menu of available diagnostics in MAR
    analysis = request.args.getlist("analysis")
    if analysis == []:

        year_range = experiment.year_range()

        # Determine where the MAR notebooks live
        if "MAR_NB_ROOT" in os.environ.keys():
            mar_nb_root = os.environ["MAR_NB_ROOT"]
        else:
            mar_nb_root = "/mar"
        avail_diags = glob.glob(f"{mar_nb_root}/**/*.ipynb", recursive=True)

        # Determine if precalculated results already exist
        preexist = os.path.exists(f"/nbhome/John.Krasting/mar-results/{experiment.id}")

        return render_template(
            "mar-start.html",
            avail_diags=avail_diags,
            idnum=idnum,
            experiment=experiment,
            year_range=year_range,
            preexist=preexist,
        )

    startyr = str(request.args.get("startyr"))
    endyr = str(request.args.get("endyr"))

    # Set parameter vars
    os.environ["MAR_PATHPP"] = experiment.pathPP
    os.environ["MAR_DORA_ID"] = idnum
    os.environ["MAR_STARTYR"] = startyr
    os.environ["MAR_ENDYR"] = endyr
    os.environ["DORA_EXECUTE"] = "1"

    # Initialize an empty list for output images
    images = []

    # Load the notebook
    notebook_filename = analysis[0]

    # User-specified notebook for testing purposes
    if notebook_filename == "custom":
        assert (
            current_user.is_authenticated
        ), "You must be logged in to run custom notebooks."
        assert (
            current_user.admin
        ), "Administrator privileges are required to run custom notebooks."
        notebook_filename = request.args.get("customPath")

    with open(notebook_filename, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    # See if the user acknowleged the need to pre-dmget the files
    validated = request.args.get("validated")

    infiles = []

    # If the user has *not* validated the files, execute the notebook
    # enough in order to display a list of files that the user should
    # dmget on their own
    if validated is None:
        # Execute the notebook
        executor = StopExecutionPreprocessor(timeout=600, kernel_name="python3")
        try:
            executor.preprocess(nb, {"metadata": {"path": "/"}})
        except ValueError as e:
            last_cell = executor.last_executed_cell
            # last_cell is a dictionary; the "outputs" key is a list-type
            last_cell = nb.cells[last_cell]
            files = last_cell["outputs"][0]["text"]
            files = files.replace("\n", " ")
            infiles = files.split(" ")

    else:
        try:
            executor = CaptureFigurePreprocessor(timeout=600, kernel_name="python3")
            res = executor.preprocess(nb, {"metadata": {"path": "/"}})
        except Exception as exc:
            exc = str(exc)
            if "An error occurred while executing the following cell" in exc:
                exc = clean_exception_string(exc)
            return render_template("page-500-pre.html", msg=f"{exc}")

        images = []
        for cell in res[0]["cells"]:
            if cell["cell_type"] == "code":
                if len(cell["outputs"]) > 0:
                    for output in cell["outputs"]:
                        if "data" in output.keys():
                            if "image/png" in output["data"].keys():
                                image = output["data"]["image/png"]
                                images.append(image)

    return render_template(
        "mar-results.html",
        analysis=analysis[0],
        idnum=idnum,
        images=images,
        infiles=infiles,
        startyr=startyr,
        endyr=endyr,
    )


@dora.route("/update-mar")
def update_mar():
    cmd = f"git -C /mar pull"
    output = subprocess.check_output(cmd.split(" "))
    output = output.decode()
    return Response(output, mimetype="text/plain")
