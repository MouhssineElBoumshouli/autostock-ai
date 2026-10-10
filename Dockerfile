FROM odoo:19.0

USER root

COPY ml/runtime-requirements.txt /tmp/autostock-ai-runtime-requirements.txt
RUN mkdir -p /opt/autostock-ai/ml \
    && python3 -m pip install --no-cache-dir --target=/opt/autostock-ai/python \
        -r /tmp/autostock-ai-runtime-requirements.txt \
    && rm /tmp/autostock-ai-runtime-requirements.txt

COPY ml/__init__.py ml/forecast.py ml/synthetic.py ml/inventory_risk.py /opt/autostock-ai/ml/

ENV PYTHONPATH="/opt/autostock-ai/python:/opt/autostock-ai"

USER odoo
