FROM python:3.12-slim
WORKDIR /lab
COPY app /lab/app
RUN mkdir -p /lab/state && useradd --uid 10001 --create-home lab && chown -R lab:lab /lab
USER lab
ENV LAB_BIND=0.0.0.0 LAB_PORT=8000
EXPOSE 8000
CMD ["python", "-u", "app/server.py"]
