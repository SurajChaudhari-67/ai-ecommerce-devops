FROM nginxinc/nginx-unprivileged:stable-alpine

USER root
RUN apk upgrade --no-cache

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY application/ /usr/share/nginx/html/

USER 101
EXPOSE 8080