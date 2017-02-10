FROM ubuntu:16.04
RUN apt-get update && apt-get install -y nginx
ADD nginx.conf /etc/nginx/sites-available/
CMD \
{ [[ -z "$HOST" ]] && { echo 'HOST missing'; exit -1; }; } && \
{ [[ -z "$PORT" ]] && { echo 'PORT missing'; exit -1; }; } && \
sed -i "s/__HOST__/$HOST/g" /etc/nginx/sites-available/nginx.conf && \
sed -i "s/__PORT__/$PORT/g" /etc/nginx/sites-available/nginx.conf && \
/usr/sbin/nginx -g 'daemon off;'
