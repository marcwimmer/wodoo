import vobject
import time
import sys
from datetime import datetime
import caldav
from caldav.elements import dav, cdav

PWD = '1'
USER = 'user1'

vcal = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:1234567890
DTSTAMP:20110510T182145Z
DTSTART:20110512T170000Z
DTEND:20110512T180000Z
SUMMARY:This is an event
END:VEVENT
END:VCALENDAR
"""

#caldav client and sync token
#http://sabre.io/dav/building-a-caldav-client/
client = caldav.DAVClient("http://localhost/calendars/caldav.php", username='test', password='test')
try:
    principal = client.principal()
except:
    import traceback
    msg = traceback.format_exc()
    print msg
    print 'error'
    time.sleep(5)
from pudb import set_trace
set_trace()
sys.exit(0)

from pudb import set_trace
set_trace()

client = caldav.DAVClient("http://calendar.example.net:8200/davical/caldav.php", username='user1', password='p1')
from pudb import set_trace
set_trace()
principal = client.principal()
calendars = principal.calendars()
from pudb import set_trace
set_trace()
for calendar in principal.calendars():
    for event in calendar.events():
        ical_text = event.data
        vo = vobject.readOne(event.data)
        print vo.prettyPrint()
from pudb import set_trace
set_trace()


    #cal = vobject.newFromBehavior('vcalendar')
    #cal.behavior
    #cal.add('vevent')
    #cal.vevent.add('uid').value = str(datetime.now())
    #cal.vevent.add('summary').value = 'This is an event'
    #from pudb import set_trace
    #set_trace()
    #cal.vevent.add('dtstart').value = datetime(1980, 4, 4, 20, 30, 0)
#
#    calendar.add_event(cal.serialize())
