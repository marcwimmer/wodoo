Evaluates mqtt messages and talks to asterisk
via ARI or AMI Interface.
Also sends events via the mqtt.


Get info in asterisk console:

http show status
HTTP Server Status:
Prefix: /asterisk      <= configure this in env
Server: Asterisk/13.22.0
Server Enabled and Bound to 0.0.0.0:8088

HTTPS Server Enabled and Bound to [::]:8089

Enabled URI's:
/asterisk/httpstatus => Asterisk HTTP General Status
/asterisk/amanager => HTML Manager Event Interface w/Digest authentication
/asterisk/arawman => Raw HTTP Manager Event Interface w/Digest authentication
/asterisk/manager => HTML Manager Event Interface
/asterisk/rawman => Raw HTTP Manager Event Interface
/asterisk/static/... => Asterisk HTTP Static Delivery
/asterisk/amxml => XML Manager Event Interface w/Digest authentication
/asterisk/mxml => XML Manager Event Interface
/asterisk/ari/... => Asterisk RESTful API
/asterisk/ws => Asterisk HTTP WebSocket

Enabled Redirects:
  None.
