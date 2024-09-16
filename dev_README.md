# DORA - Development-Oriented Real-Time Analysis Developer's Guide

This is the Developer's Guide for Dora. As more tools and methods become available, this document should be updated. This will hopefully be useful to anyone tasked with maintaining the Dora system. Anyone else is welcome to read the guide for fun.

> Running the CI/CD Pipeline:

In theory, this should only be available to git repo "maintainers" or higher. The idea is to go to the pipeline page: https://gitlab.gfdl.noaa.gov/john.krasting/dora/-/pipelines and click the "Run Pipeline" button in the upper right hand corner. On the next page, you will be presented with the option to change the branch in the dropdown menu on the upper left. You will also have the option to define one or more CI/CD variables. As of writing, the two variables of interest would be:

- dora_system
- use_podman_cache

The default value for dora_system is dora-dev, so if you do not define the dora_system variable, the pipeline will run on the dora-dev system (i.e. the test system). In order to update the production system, you must define the value for dora_system as "dora" (you do not need to use the quotes when inputting the value into the text box on the page). Please be sure that you actually want to update the dora production system when setting this variable. Note that the update shouldn't take longer than 10 minutes at an absolute maximum depending on changes you've made... it's usually less than a minute when the default option to use cache is enabled (more on that later). Also note that this will use "secret variables" as defined on the Gitlab repo settings for authenticating with Google. Hopefully those values won't need to be adjusted, but if they do, there will hopefully be further guidance in this document on how to do that.

The default value for use_podman_cache is an empty string (""). In the CI, this will tell podman to use the cache, so that we don't have to rebuild everything from scratch. We usually want this behavior (which is why it is the default)... however, there are occasions where we don't. For example, if one of the dependent git modules has changed (e.g. a push was made to the dependent om4labs branch that is used), the cache will still use the old "cached" version and that change won't be implemented for the build. In order to not use cache with the podman build, you must set the "use_podman_cache" variable to the value "--no-cache ". Note that the quotes are not needed for the text input box but the TRAILIING SPACE IS REQUIRED. This is, admittedly, probably not an ideal solution, and perhaps someone would like to find something more elegant for these types of changes, but given the infrequency with which this is required, the time investment may not be worthwhile. Note that a build without cache will usually take about 7 minutes to complete.

> Stuck Gitlab Runner

The gitlab runners often go stale on the systems. There does seem to be a particular magic to getting them to function again. In theory, the gitlab-runner status is "active" because it has been activated with systemctl (you can run systemctl status gitlab-runner with the podman user to test). That "active" status should survive system restarts, but sometimes it doesn't. Sometimes running "gitlab-runner run" or "gitlab-runner start" will kick things into gear. Note that you might have to put that process in the background to do anything else on the system (press Ctrl-z, then `bg %1`). The output will still show on the terminal. If anyone knows of a cleaner way to keep these runners active, that may be worth the time to implement.

> Podman containers "Created" Status

It appears that after a system restart, the podman containers are occasionally stuck in this "Created" state. I think this has something to do with podman not restarting properly as a service. We could investigate this further, but the quick fix is to login as the podman user (`dzdo su -l podman`), navigate to the "dora" directory (`cd dora`), and then run the following to put things back on line: (`podman-compose -f podman-compose.yml up -d`).
