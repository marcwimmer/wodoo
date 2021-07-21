FROM postgres:12
ENTRYPOINT ["/run.sh"]
CMD ["postgres"]


ADD config* /
ADD run.sh /run.sh
COPY init/* /docker-entrypoint-initdb.d/
RUN chown -R postgres:postgres /docker-entrypoint-initdb.d && \
    chmod a+x /docker-entrypoint-initdb.d/*.sh /run.sh
