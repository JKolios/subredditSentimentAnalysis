#! /bin/bash
docker build -t sentiment-test:latest .
docker run -it -p 9000:8080 --env-file ./test-env sentiment-test:latest 