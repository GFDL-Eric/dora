""" mar.py : module to execute jupyter notebooks """

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

from .Experiment import Experiment
from .frepptools import Filegroup, in_daterange, optimize_filegroup_selection

# This environment variable prevents annoying error messages when running
# the Jupyter notebook preprocessor
os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"


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

    # Fetch an Experiment object that houses all of the
    # experiment metadata
    experiment = Experiment(idnum)

    # Make sure the experiment is valid
    if experiment.validate_path("pathPP") is False:
        return render_template(
            "page-500.html", msg=f"Unable to reach {experiment.pathPP}."
        )

    # Get the requested analysis from the URL or provide user with
    # a menu of available diagnostics in MAR
    analysis = request.args.getlist("analysis")
    if analysis == []:

        year_range = experiment.year_range()
        avail_diags = glob.glob("/home/jpk/mar/**/*.ipynb", recursive=True)

        return render_template(
            "mar-start.html",
            avail_diags=avail_diags,
            idnum=idnum,
            experiment=experiment,
            year_range=year_range,
        )

    # Set parameter vars
    os.environ["MAR_PATHPP"] = experiment.pathPP
    os.environ["MAR_DORA_ID"] = idnum
    os.environ["MAR_STARTYR"] = str(request.args.get("startyr"))
    os.environ["MAR_ENDYR"] = str(request.args.get("endyr"))
    os.environ["DORA_EXECUTE"] = "1"

    # Initialize an empty list for output images
    images = []

    # Load the notebook
    notebook_filename = analysis[0]
    with open(notebook_filename, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    # See if the user acknowleged the need to pre-dmget the files
    validated = request.args.get("validated")

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

    # executor = CaptureFigurePreprocessor(timeout=600, kernel_name="python3")
    # res = executor.preprocess(nb, {"metadata": {"path": "/"}})

    # original code
    # try:
    #    executor = CaptureFigurePreprocessor(timeout=600, kernel_name="python3")
    #    res = executor.preprocess(nb, {"metadata": {"path": "/"}})
    # except Exception as exc:
    #    return render_template("page-500.html", msg=f"{exc}")

    # images = []
    # for cell in res[0]["cells"]:
    #     if cell["cell_type"] == "code":
    #         if len(cell["outputs"]) > 0:
    #             for output in cell["outputs"]:
    #                 if "data" in output.keys():
    #                     if "image/png" in output["data"].keys():
    #                         image = output["data"]["image/png"]
    #                         images.append(image)

    return render_template("mar-results.html", images=images, infiles=infiles)


@dora.route("/update-mar")
def update_mar():
    cmd = f"git -C /mar pull"
    output = subprocess.check_output(cmd.split(" "))
    output = output.decode()
    return Response(output, mimetype="text/plain")


