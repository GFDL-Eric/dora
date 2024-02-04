# Base Docker Container for Dora
# ==============================

FROM condaforge/miniforge3

# # Update OS packages
RUN apt update && apt install -y git bash mysql-client

# Create the environment:
COPY envs envs
RUN mamba env create -f envs/env.prod.yml \
  && conda clean --all \
  && echo "conda activate env" >> ~/.bashrc

ENV PATH /opt/conda/envs/env/bin:$PATH

# The code to run when container is started:
ENV FLASK_APP run.py
COPY run.py run.py
COPY certs certs
COPY gunicorn gunicorn
RUN chmod +x gunicorn/gunicorn-run.sh
EXPOSE 5050
COPY dora dora
COPY .env .env

# Download Model Analysis Repository (MAR)
RUN git clone https://github.com/jkrasting/mar.git

CMD ["/bin/bash", "gunicorn/gunicorn-run.sh"]
