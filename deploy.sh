#! /bin/bash
docker build -t sentiment:latest .
env AWS_PROFILE=personal aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 320707504410.dkr.ecr.eu-central-1.amazonaws.com
env AWS_PROFILE=personal docker tag sentiment:latest  320707504410.dkr.ecr.eu-central-1.amazonaws.com/subreddit-sentiment-analysis:latest
docker push 320707504410.dkr.ecr.eu-central-1.amazonaws.com/subreddit-sentiment-analysis:latest 