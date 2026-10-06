FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY application/ /usr/share/nginx/html/
EXPOSE 8080