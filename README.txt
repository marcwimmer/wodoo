How to debug:
--------------

  ari/stasis:
    - run 
        ./manage.sh kill ari/stasis
        ./manage.sh runbash-with-ports ari/stasis
        <after machine is up and you are in the machine>
        /usr/local/bin/debug.sh
