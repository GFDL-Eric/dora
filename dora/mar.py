import base64
import glob
import io
from operator import itemgetter
import os
import traceback
import subprocess

import datetime
import om4labs
from flask import Response
from flask import render_template
from flask import request
from flask import send_file

from dora import dora
from .Experiment import Experiment

from .frepptools import Filegroup, in_daterange, optimize_filegroup_selection

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from io import BytesIO
import matplotlib.pyplot as plt

from IPython.display import display, Image
import base64

import os
os.environ['PYDEVD_DISABLE_FILE_VALIDATION'] = '1'

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
        for output in cell.get('outputs', []):
            if output.output_type == 'execute_result':
                for data in output.data.get('image/png', []):
                    img_data = BytesIO(base64.b64decode(data))
                    fig = plt.figure()
                    ax = fig.add_subplot(111)
                    ax.imshow(plt.imread(img_data))
                    ax.axis('off')  # Hide axes
                    self.captured_figures.append(fig)
        return outputs


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
        avail_diags = glob.glob("/mar/**/*.ipynb", recursive=True)

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

    # Load the notebook
    notebook_filename = analysis[0]
    with open(notebook_filename, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    
    # Execute the notebook
    try:
        executor = CaptureFigurePreprocessor(timeout=600, kernel_name='python3')
        res = executor.preprocess(nb, {'metadata': {'path': '/'}})
    except Exception as exc:
        return render_template("page-500.html", msg=f"{exc}")

    images = []
    for cell in res[0]["cells"]:
        if cell["cell_type"] == "code":
            if len(cell["outputs"]) > 0:
                for output in cell["outputs"]:
                    if "data" in output.keys():
                        if "image/png" in output["data"].keys():
                            image = output["data"]["image/png"]
                            images.append(image)
    
    return render_template("mar-results.html", images=images)


@dora.route("/update-mar")
def update_mar():
    cmd = f"git -C /mar pull"
    output = subprocess.check_output(cmd.split(" "))
    output = output.decode()
    return Response(output, mimetype="text/plain")



## 
##     # get the start and end years for the analysis
##     # (rely on browser to make sure user enters values)
##     startyr = int(request.args.get("startyr"))
##     endyr = int(request.args.get("endyr"))
## 
##     # default directories
##     default_dirs = {
##         "acc_drake": ("ocean_Drake_Passage", "ts", ["umo"]),
##         "depth_time_temperature_drift": ("ocean_annual_z", "ts", ["thetao_xyave"]),
##         "depth_time_salinity_drift": ("ocean_annual_z", "ts", ["so_xyave"]),
##         "enso": ("ocean_monthly_1x1deg", "ts", ["tos"]),
##         "heat_transport": ("ocean_monthly", "av", []),
##         "moc_z": ("ocean_annual_z", "av", []),
##         "moc_rho": ("ocean_annual_rho2", "av", []),
##         "seaice": ("ice_1x1deg", "av", []),
##         "section_transports": (None, None, []),
##         "so_yz_annual_bias_1x1deg": ("ocean_annual_z_1x1deg", "av", []),
##         "sss_annual_bias_1x1deg": ("ocean_annual_z_1x1deg", "av", []),
##         "sst_annual_bias_1x1deg": ("ocean_annual_z_1x1deg", "av", []),
##         "stress_curl": ("ocean_monthly", "av", []),
##         "thetao_yz_annual_bias_1x1deg": ("ocean_annual_z_1x1deg", "av", []),
##     }
## 
##     # Create a Diagnostic object for each requested analysis
##     diags = [
##         Diagnostic(
##             x, default_dirs[x][0], pptype=default_dirs[x][1], varlist=default_dirs[x][2]
##         )
##         for x in analysis
##     ]
## 
##     # Resolve the needed files for each diagostic
##     downsample = True if request.args.get("downsample") == "True" else False
##     diags = [
##         x.resolve_files(
##             experiment.pathPP, experiment.expName, startyr, endyr, downsample=downsample
##         )
##         for x in diags
##     ]
## 
##     # Separate into those that passed and failed file resolution
##     passed = [x for x in diags if x.success is True]
##     failed = [x for x in diags if x.success is False]
## 
##     # See if the user acknowleged the need to pre-dmget the files
##     validated = request.args.get("validated")
## 
##     # Handle special case when section transports do not need to be validated
##     validated = (
##         "True"
##         if (validated is None and analysis == ["section_transports"])
##         else validated
##     )
## 
##     # If the user has *not* validated the files, display a list
##     # of files that the user should dmget on their own
##     if validated is None:
##         infiles = [x.args["infile"] for x in passed]
##         infiles = [x for sublist in infiles for x in sublist]
##         infiles = [x.replace(experiment.pathPP, "") for x in infiles]
## 
##     elif validated == "True":
##         # set infiles to an empty list - Jinja template will see this
##         # and not display the dmget card
##         infiles = []
## 
##         # carry over diagnostics that failed the file resolution,
##         # do not attempt to run them
##         failed_resolve = failed
## 
##         # *** run the diagnostics ****
##         diags = [x.run() for x in diags if x.success is True]
## 
##         # separate into those that passed and those that failed
##         passed = [x for x in diags if x.success is True]
##         failed = [x for x in diags if x.success is False]
##         failed = failed + failed_resolve
## 
##     download_flag = False
##     return render_template(
##         "om4labs-results.html",
##         args=request.args,
##         analysis=analysis,
##         infiles=infiles,
##         experiment=experiment,
##         download_flag=download_flag,
##         passed=passed,
##         failed=failed,
##     )
