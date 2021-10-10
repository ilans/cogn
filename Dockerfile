FROM python:3.9-buster

RUN pip install pandas

WORKDIR /cogn

RUN bash -ic 'history -s python cogn.py'

ENTRYPOINT ["python", "cogn.py"]
