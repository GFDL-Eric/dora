#!/bin/sh

# load environment variables 
`sed -e "s/^/export /g" .env`

# setup conda
source /root/miniforge3/etc/profile.d/conda.sh
conda activate env

# create an SSL certificate
mkdir -p /etc/certificates
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout /etc/certificates/key.pem \
  -out /etc/certificates/cert.pem \
  -config certs/req.conf \
  -extensions 'v3_req'

# start server
gunicorn -t 600 --preload \
  --certfile /etc/certificates/cert.pem \
  --keyfile /etc/certificates/key.pem \
  --config gunicorn/gunicorn-cfg.py \
  run:dora
