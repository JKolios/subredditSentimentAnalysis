FROM public.ecr.aws/lambda/python:3.8
RUN pip install praw textblob nltk
RUN pip install pytickersymbols
COPY app.py   ./
COPY nltk_data /nltk_data
CMD ["app.handler"]      