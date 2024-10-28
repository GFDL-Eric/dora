# Base Docker Container for Dora
# ==============================

FROM registry.access.redhat.com/ubi8/ubi
RUN yum -y update && yum -y install git bash mysql vim
RUN curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh" && bash Miniforge3-Linux-x86_64.sh -b 
ENV PATH /root/miniforge3/bin:$PATH 
RUN conda init

COPY envs envs
RUN mamba env create -f envs/env.prod.yml \
  && conda clean --all \
  && echo "conda activate env" >> ~/.bashrc

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

CMD ["/bin/bash", "/gunicorn/gunicorn-run.sh"]
